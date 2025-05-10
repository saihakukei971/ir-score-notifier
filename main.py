import flet as ft
import asyncio
import logging
from pathlib import Path
import sys

# 親ディレクトリをパスに追加（相対インポート用）
sys.path.append(str(Path(__file__).parent))

# ロガー設定を読み込む
from logger_config import setup_logger
from flet_ui import IRNotifierGUI
from config import config

def main():
    # アプリケーションの起動
    ft.app(target=app_main)

async def app_main(page: ft.Page):
    # GUIの初期化
    gui = IRNotifierGUI(page)

    # 起動メッセージ
    logging.info("IR Impact Notifier アプリケーションを起動しました")

if __name__ == "__main__":
    main()