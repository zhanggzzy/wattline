$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Read-NvidiaXml($Timeout) {
    $tool = Get-Command nvidia-smi.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (!$tool) {
        $path = Join-Path $env:ProgramFiles 'NVIDIA Corporation\NVSMI\nvidia-smi.exe'
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { return }
    } else {
        $path = $tool.Source
    }

    $process = [Diagnostics.Process]::new()
    $output = [IO.MemoryStream]::new()
    try {
        $process.StartInfo.FileName = $path
        $process.StartInfo.Arguments = '-q -x'
        $process.StartInfo.UseShellExecute = $false
        $process.StartInfo.RedirectStandardOutput = $true
        $process.StartInfo.RedirectStandardError = $true
        $process.StartInfo.CreateNoWindow = $true
        if (!$process.Start()) { return }
        $copy = $process.StandardOutput.BaseStream.CopyToAsync($output)
        $null = $process.StandardError.BaseStream.CopyToAsync([IO.Stream]::Null)
        $timer = [Diagnostics.Stopwatch]::StartNew()
        if (!$process.WaitForExit([int][Math]::Ceiling($Timeout * 1000))) {
            try { $process.Kill() } catch {}
            return
        }
        $remaining = [Math]::Max(0, [int][Math]::Ceiling($Timeout * 1000 - $timer.ElapsedMilliseconds))
        if (!$copy.Wait($remaining) -or $output.Length -gt 700000) { return }
        $bytes = $output.ToArray()
        if ($process.ExitCode -in @(0, 6) -and
            [Text.Encoding]::ASCII.GetString($bytes).Trim() -eq 'No devices were found') {
            return @{ empty = $true }
        }
        if ($process.ExitCode -eq 0 -and $bytes.Length) {
            return @{ xml = [Convert]::ToBase64String($bytes) }
        }
    } catch {
        # Driver, executable and subprocess errors leave inventory unverified.
    } finally {
        $process.Dispose()
        $output.Dispose()
    }
}

function Read-ProcessEvidence($Xml, $Cutoff) {
    $stream = [IO.MemoryStream]::new([Convert]::FromBase64String($Xml))
    $settings = [Xml.XmlReaderSettings]::new()
    $settings.DtdProcessing = [Xml.DtdProcessing]::Ignore
    $settings.XmlResolver = $null
    $reader = [Xml.XmlReader]::Create($stream, $settings)
    try {
        $doc = [Xml.XmlDocument]::new()
        $doc.XmlResolver = $null
        $doc.Load($reader)
        $ids = @{}
        foreach ($node in $doc.SelectNodes('/nvidia_smi_log/gpu/processes/process_info/pid')) {
            [uint32]$processId = 0
            if ([uint32]::TryParse($node.InnerText, [ref]$processId) -and $processId -gt 0) {
                $ids[$processId] = $true
            }
        }
    } finally {
        $reader.Dispose()
        $stream.Dispose()
    }
    if (!$ids.Count) { return }

    $timer = [Diagnostics.Stopwatch]::StartNew()
    $evidence = @{}
    foreach ($entry in (Get-CimInstance Win32_Process -Property ProcessId, Name, CreationDate -OperationTimeoutSec 2)) {
        $processId = [uint32]$entry.ProcessId
        if (!$ids.ContainsKey($processId) -or !$entry.CreationDate) { continue }
        $created = $entry.CreationDate.ToUniversalTime()
        if ($created -ge $Cutoff) { continue }
        $row = @{
            name = $entry.Name
            started_at = ([DateTimeOffset]$created).ToUnixTimeMilliseconds()
        }
        if ($timer.ElapsedMilliseconds -lt 1200) {
            try {
                $owner = Invoke-CimMethod -InputObject $entry -MethodName GetOwner -OperationTimeoutSec 2
                if ($owner.ReturnValue -eq 0 -and $owner.User) {
                    $row.user = if ($owner.Domain) { "$($owner.Domain)\$($owner.User)" } else { $owner.User }
                }
            } catch {}
        }
        $evidence[$processId] = @{ creation = $created; row = $row }
    }
    if (!$evidence.Count) { return }
    # Recheck creation times after account lookup to reject exited or reused PIDs.
    $verified = @{}
    foreach ($entry in (Get-CimInstance Win32_Process -Property ProcessId, CreationDate -OperationTimeoutSec 2)) {
        $processId = [uint32]$entry.ProcessId
        $previous = $evidence[$processId]
        if ($previous -and $entry.CreationDate -and $entry.CreationDate.ToUniversalTime() -eq $previous.creation) {
            $verified[[string]$processId] = $previous.row
        }
    }
    return $verified
}

try {
    $config = ConvertFrom-Json -InputObject ([Console]::ReadLine())
    $product = Get-CimInstance Win32_ComputerSystemProduct -Property UUID
    $os = Get-CimInstance Win32_OperatingSystem -Property LastBootUpTime, SystemDrive, TotalVisibleMemorySize, FreePhysicalMemory
    $uuid = [Guid]$product.UUID
    $hostId = $uuid.ToString('N')
    if ($hostId -in @('00000000000000000000000000000000', 'ffffffffffffffffffffffffffffffff') -or !$os.LastBootUpTime) {
        throw 'Unverified Windows identity'
    }
    if (!$config.identity_only -and $hostId -cne $config.expected_host_id) {
        [Console]::WriteLine('{"error":"windows_identity_mismatch"}')
        exit 1
    }
    $boot = $os.LastBootUpTime.ToUniversalTime()
    $sample = [DateTime]::UtcNow
    if ($boot -gt $sample) { throw 'Invalid Windows boot time' }
    $data = @{ host_id = $hostId; boot_id = $boot.ToString('o') }
    if (!$config.identity_only) {
        $data.source_observed_at = ([DateTimeOffset]$sample).ToUnixTimeMilliseconds() / 1000
        if ('cpu' -in $config.checks) {
            try {
                $data.cpu_count = (Get-CimInstance Win32_ComputerSystem -Property NumberOfLogicalProcessors).NumberOfLogicalProcessors
                $data.cpu_samples = @(Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation -Property Name, PercentProcessorTime |
                    Where-Object { $_.Name -match '^\d+,\d+$' } |
                    ForEach-Object { @{ name = $_.Name; percent = $_.PercentProcessorTime } })
            } catch {}
        }
        if ('memory' -in $config.checks -and $null -ne $os.TotalVisibleMemorySize -and $null -ne $os.FreePhysicalMemory) {
            $data.memory = @{ total_bytes = [long]$os.TotalVisibleMemorySize * 1024; available_bytes = [long]$os.FreePhysicalMemory * 1024 }
        }
        if ('system' -in $config.checks) {
            $data.uptime_seconds = [long][Math]::Floor(($sample - $boot).TotalSeconds)
            try {
                $drive = $os.SystemDrive
                if ($drive -match '^[a-zA-Z]:$') {
                    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID = '$drive'" -Property Size, FreeSpace
                    if ($null -ne $disk.Size -and $null -ne $disk.FreeSpace) {
                        $data.root_disk = @{ volume = $drive; total_bytes = [long]$disk.Size; available_bytes = [long]$disk.FreeSpace }
                    }
                }
            } catch {}
        }
        if ('gpu' -in $config.checks) {
            $gpuCutoff = [DateTime]::UtcNow
            $data.nvidia = Read-NvidiaXml $config.gpu_timeout
            $gpuAt = [DateTime]::UtcNow
            $data.gpu_observed_at = ([DateTimeOffset]$gpuAt).ToUnixTimeMilliseconds()
            if ('processes' -in $config.checks -and $data.nvidia.xml) {
                try { $data.process_evidence = Read-ProcessEvidence $data.nvidia.xml $gpuCutoff } catch {}
            }
        }
    }
    [Console]::WriteLine((ConvertTo-Json -InputObject @{ data = $data } -Depth 8 -Compress))
} catch {
    [Console]::WriteLine('{"error":"windows_probe_failed"}')
    exit 1
}
