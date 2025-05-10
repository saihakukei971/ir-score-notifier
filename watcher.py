import asyncio
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from loguru import logger
from typing import Callable, Optional, Awaitable, List, Any
import os

class IRFileHandler(FileSystemEventHandler):
    """IRファイル監視ハンドラクラス"""

    def __init__(self, callback: Callable[[Path], Awaitable[Any]], extensions: List[str] = None):
        """
        初期化
        Args:
            callback: ファイル検出時のコールバック関数
            extensions: 監視対象の拡張子リスト（デフォルトは.txt, .html, .csv）
        """
        self.callback = callback
        self.extensions = extensions or ['.txt', '.html', '.csv']
        self.loop = asyncio.get_event_loop()

    def on_created(self, event):
        """ファイル作成イベントハンドラ"""
        if not event.is_directory:
            file_path = Path(event.src_path)

            # 拡張子チェック
            if file_path.suffix.lower() in self.extensions:
                logger.info(f"新しいファイルを検出しました: {file_path}")

                # メインループでコールバックを実行
                asyncio.run_coroutine_threadsafe(self.callback(file_path), self.loop)

class IRWatcher:
    """IRファイル監視クラス"""

    def __init__(self, callback: Callable[[Path], Awaitable[Any]]):
        """
        初期化
        Args:
            callback: ファイル検出時のコールバック関数
        """
        self.callback = callback
        self.observer = None
        self.watch_dir = None
        self.is_watching = False

    def start_watching(self, directory: Path) -> bool:
        """
        ディレクトリの監視を開始する
        Args:
            directory: 監視するディレクトリ
        Returns:
            bool: 監視開始に成功したかどうか
        """
        if self.is_watching:
            logger.warning(f"すでに監視中です: {self.watch_dir}")
            return False

        try:
            if not directory.exists():
                logger.error(f"監視対象ディレクトリが存在しません: {directory}")
                return False

            # ディレクトリであることを確認
            if not directory.is_dir():
                logger.error(f"監視対象がディレクトリではありません: {directory}")
                return False

            self.watch_dir = directory
            self.observer = Observer()

            # イベントハンドラの設定
            handler = IRFileHandler(self.callback)
            self.observer.schedule(handler, str(directory), recursive=False)

            # 監視開始
            self.observer.start()
            self.is_watching = True

            logger.info(f"ディレクトリの監視を開始しました: {directory}")
            return True

        except Exception as e:
            logger.error(f"監視開始中にエラーが発生しました: {str(e)}")
            return False

    def stop_watching(self) -> bool:
        """
        ディレクトリの監視を停止する
        Returns:
            bool: 監視停止に成功したかどうか
        """
        if not self.is_watching or not self.observer:
            logger.warning("監視が開始されていません")
            return False

        try:
            self.observer.stop()
            self.observer.join()
            self.is_watching = False

            logger.info(f"ディレクトリの監視を停止しました: {self.watch_dir}")
            return True

        except Exception as e:
            logger.error(f"監視停止中にエラーが発生しました: {str(e)}")
            return False

    def is_active(self) -> bool:
        """
        監視が有効かどうかを返す
        Returns:
            bool: 監視が有効かどうか
        """
        return self.is_watching

    def get_watch_dir(self) -> Optional[Path]:
        """
        監視中のディレクトリを返す
        Returns:
            Optional[Path]: 監視中のディレクトリまたはNone
        """
        return self.watch_dir if self.is_watching else None