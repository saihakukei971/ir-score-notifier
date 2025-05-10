import sys
from datetime import datetime
from pathlib import Path
from loguru import logger
from config import config

# ロガー設定
def setup_logger():
    # ログフォーマット
    log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

    # ログファイルのパス
    log_file = config.logs_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"

    # ロガー設定をクリア
    logger.remove()

    # コンソール出力の設定
    logger.configure(handlers=[
        {"sink": sys.stderr, "format": log_format, "level": "INFO"},
        {"sink": str(log_file), "format": log_format, "rotation": "00:00", "retention": "30 days", "level": "DEBUG"}
    ])

    logger.info(f"ログ設定を初期化しました - ログファイル: {log_file}")

setup_logger()