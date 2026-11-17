import argparse

import uvicorn

from .app import create_app
from .config import Config


def main():
    parser = argparse.ArgumentParser(description='Wattline 算力监控')
    parser.add_argument('--config', required=True, help='监控服务 JSON 配置')
    args = parser.parse_args()
    config = Config.read(args.config)
    uvicorn.run(create_app(config), host='127.0.0.1', port=config.port, workers=1, proxy_headers=False, access_log=False)


if __name__ == '__main__':
    main()
