# Tasks

## 1. Persist and expose the assigned user

- [x] 1.1 Add the optional trimmed single-line `assigned_user` field to machine settings, load it with existing settings under the stable machine identity, keep it out of the immutable machine/config model, and include it in the snapshot view. Verify with pytest coverage for set, replace, clear, restart, per-machine isolation, legacy settings without the key, and removal.
- [x] 1.2 Preserve failure atomicity and existing input/access protection: reject control characters and over-length values, save only after the settings write succeeds, and omit the key when cleared. Verify with pytest cases for 422 validation, cross-origin/non-JSON rejection, failed-write 503 with unchanged snapshot, and old-database readability.

## 2. Show and edit the assignment

- [x] 2.1 Add the localized settings input and the detail/list display of the recorded value, escaped as user text, with Chinese and English resources; keep process accounts and SSH users unchanged. Verify with `node --check wattline/static/monitor.js`, `node tools/test_i18n.cjs`, and the synthetic API browser check for both locales, list/detail display, edit/clear, narrow width, and untrusted text.
- [x] 2.2 Document the field and its advisory semantics in README and verify the documented commands still match the repository layout.

## 3. Integration verification

- [x] 3.1 Run the full suite, JavaScript and locale checks, the synthetic API browser check, OpenSpec 1.14.2 strict validation, and diff checks; record commands, outputs, base/implementation SHAs, coverage and limitations in [verification.md](verification.md).

## Workflow follow-up

- Independent review runs in AN-103 against the implementation commit and records its outcome in verification.md.
- Mika syncs the `machine-registry` delta, archives the change after review, and verifies the remote main commit.
