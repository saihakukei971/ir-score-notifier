from pathlib import Path
import json
import shutil
from datetime import datetime
import pandas as pd
from loguru import logger
from typing import Dict, List, Union, Tuple, Optional
from config import config

class KeywordDictionary:
    """キーワード辞書クラス"""

    def __init__(self):
        self.keywords = {}  # word -> score
        self.source_type = None  # "user" または "auto"
        self.source_path = None

    def load(self) -> Tuple[bool, str]:
        """
        キーワード辞書をロードする
        Returns:
            Tuple[bool, str]: 成功したかどうかとメッセージ
        """
        # まずユーザー辞書を探す
        user_dict_path = config.custom_dictionary_path
        if user_dict_path.exists():
            try:
                self._load_user_dictionary(user_dict_path)
                self.source_type = "user"
                self.source_path = user_dict_path
                logger.info(f"ユーザー辞書を読み込みました: {user_dict_path}")
                return True, f"ユーザー辞書を読み込みました: {user_dict_path}"
            except Exception as e:
                logger.error(f"ユーザー辞書の読み込みに失敗しました: {str(e)}")
                # ユーザー辞書の読み込みに失敗した場合は自動辞書に移る

        # 次に自動辞書を探す
        auto_dict_path = config.auto_dictionary_path
        if auto_dict_path.exists():
            try:
                self._load_auto_dictionary(auto_dict_path)
                self.source_type = "auto"
                self.source_path = auto_dict_path
                logger.info(f"自動辞書を読み込みました: {auto_dict_path}")
                return True, f"自動辞書を読み込みました: {auto_dict_path}"
            except Exception as e:
                logger.error(f"自動辞書の読み込みに失敗しました: {str(e)}")
                return False, f"両方の辞書の読み込みに失敗しました"

        # どちらも存在しない場合
        logger.warning("辞書ファイルが見つかりません。自動辞書の生成が必要です。")
        return False, "辞書ファイルが見つかりません。自動辞書の生成が必要です。"

    def _load_user_dictionary(self, path: Path) -> None:
        """
        ユーザー辞書(Excel/CSV)を読み込む
        Args:
            path: 辞書ファイルのパス
        """
        if path.suffix.lower() == '.xlsx':
            df = pd.read_excel(path)
        elif path.suffix.lower() == '.csv':
            df = pd.read_csv(path)
        else:
            raise ValueError(f"サポートされていないファイル形式: {path.suffix}")

        # 必要なカラムがあるか確認
        required_columns = ['word', 'score']
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            raise ValueError(f"必要なカラムがありません: {', '.join(missing)}")

        # 辞書に読み込み
        self.keywords = {}
        for _, row in df.iterrows():
            word = str(row['word']).strip()
            if not word:  # 空白行をスキップ
                continue

            score = int(row['score'])
            self.keywords[word] = score

    def _load_auto_dictionary(self, path: Path) -> None:
        """
        自動辞書(JSON)を読み込む
        Args:
            path: 辞書ファイルのパス
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 辞書形式のチェック
        if not isinstance(data, dict):
            raise ValueError("自動辞書の形式が不正です。辞書形式が必要です。")

        # 辞書に読み込み
        self.keywords = {}
        for word, score in data.items():
            word = str(word).strip()
            if not word:  # 空白キーをスキップ
                continue

            if not isinstance(score, (int, float)):
                logger.warning(f"スコアが数値ではありません: {word} -> {score}")
                continue

            self.keywords[word] = int(score)

    def backup_current_dictionary(self) -> Optional[Path]:
        """
        現在の辞書をバックアップする
        Returns:
            Optional[Path]: バックアップファイルのパス、またはNone
        """
        if not self.source_path or not self.source_path.exists():
            return None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{self.source_path.stem}_{timestamp}{self.source_path.suffix}"
        backup_path = config.backup_dir / backup_filename

        # バックアップディレクトリが存在しない場合は作成
        config.backup_dir.mkdir(exist_ok=True, parents=True)

        # ファイルをコピー
        shutil.copy2(self.source_path, backup_path)
        logger.info(f"辞書をバックアップしました: {backup_path}")

        return backup_path

    def get_word_score(self, word: str) -> int:
        """
        単語のスコアを取得する
        Args:
            word: 単語
        Returns:
            int: スコア
        """
        return self.keywords.get(word, 0)

    def get_all_keywords(self) -> Dict[str, int]:
        """
        すべてのキーワードとスコアを取得する
        Returns:
            Dict[str, int]: キーワードとスコアの辞書
        """
        return self.keywords.copy()

    def get_source_info(self) -> Dict[str, str]:
        """
        辞書のソース情報を取得する
        Returns:
            Dict[str, str]: ソース情報
        """
        return {
            "type": self.source_type,
            "path": str(self.source_path) if self.source_path else None
        }

# シングルトンインスタンス
keyword_dict = KeywordDictionary()