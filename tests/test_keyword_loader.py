import unittest
import tempfile
import pandas as pd
import json
import os
from pathlib import Path
from keyword_loader import KeywordDictionary

class TestKeywordLoader(unittest.TestCase):

    def setUp(self):
        # 一時ディレクトリを作成
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # テスト用のキーワード辞書インスタンス
        self.keyword_dict = KeywordDictionary()

        # テスト用のディレクトリ構造を作成
        self.custom_dir = self.temp_path / "custom_keywords"
        self.auto_dir = self.temp_path / "auto_keywords"
        self.backup_dir = self.temp_path / "backup"

        self.custom_dir.mkdir(exist_ok=True)
        self.auto_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)

        # テスト用のユーザー辞書を作成
        self.user_dict_path = self.custom_dir / "keywords.xlsx"
        user_dict_data = {
            'word': ['赤字', '黒字', '増益', '減益', '合併'],
            'score': [8, 5, 6, 7, 6],
            'note': ['重要度高', '好材料', '好材料', '重要度高', '重要度中']
        }
        pd.DataFrame(user_dict_data).to_excel(self.user_dict_path, index=False)

        # テスト用の自動辞書を作成
        self.auto_dict_path = self.auto_dir / "auto_keywords.json"
        auto_dict_data = {
            "上場廃止": 9,
            "減損": 8,
            "訴訟": 7
        }
        with open(self.auto_dict_path, 'w', encoding='utf-8') as f:
            json.dump(auto_dict_data, f, ensure_ascii=False, indent=2)

    def tearDown(self):
        # 一時ディレクトリを削除
        self.temp_dir.cleanup()

    def test_load_user_dictionary(self):
        """ユーザー辞書の読み込みテスト"""
        # 辞書のソースパスを設定
        self.keyword_dict.source_path = self.user_dict_path

        # ユーザー辞書をロード
        self.keyword_dict._load_user_dictionary(self.user_dict_path)

        # 辞書が正しく読み込まれたか確認
        self.assertEqual(len(self.keyword_dict.keywords), 5)
        self.assertEqual(self.keyword_dict.keywords["赤字"], 8)
        self.assertEqual(self.keyword_dict.keywords["黒字"], 5)
        self.assertEqual(self.keyword_dict.keywords["増益"], 6)
        self.assertEqual(self.keyword_dict.keywords["減益"], 7)
        self.assertEqual(self.keyword_dict.keywords["合併"], 6)

    def test_load_auto_dictionary(self):
        """自動辞書の読み込みテスト"""
        # 辞書のソースパスを設定
        self.keyword_dict.source_path = self.auto_dict_path

        # 自動辞書をロード
        self.keyword_dict._load_auto_dictionary(self.auto_dict_path)

        # 辞書が正しく読み込まれたか確認
        self.assertEqual(len(self.keyword_dict.keywords), 3)
        self.assertEqual(self.keyword_dict.keywords["上場廃止"], 9)
        self.assertEqual(self.keyword_dict.keywords["減損"], 8)
        self.assertEqual(self.keyword_dict.keywords["訴訟"], 7)

    def test_load_priority(self):
        """ユーザー辞書優先度テスト"""
        # テスト用の設定
        from config import config

        # 一時的に設定を変更
        orig_custom = config.custom_dictionary_path
        orig_auto = config.auto_dictionary_path

        config.custom_dictionary_path = self.user_dict_path
        config.auto_dictionary_path = self.auto_dict_path

        try:
            # 辞書をロード（ユーザー辞書が優先されるはず）
            success, message = self.keyword_dict.load()

            # ロードが成功したか確認
            self.assertTrue(success)
            self.assertIn("ユーザー辞書を読み込みました", message)

            # ソースタイプが正しいか確認
            self.assertEqual(self.keyword_dict.source_type, "user")

            # 辞書の内容が正しいか確認
            self.assertEqual(len(self.keyword_dict.keywords), 5)
            self.assertEqual(self.keyword_dict.keywords["赤字"], 8)

        finally:
            # 設定を元に戻す
            config.custom_dictionary_path = orig_custom
            config.auto_dictionary_path = orig_auto

    def test_fallback_to_auto(self):
        """ユーザー辞書がない場合に自動辞書にフォールバックするテスト"""
        # テスト用の設定
        from config import config

        # 一時的に設定を変更
        orig_custom = config.custom_dictionary_path
        orig_auto = config.auto_dictionary_path

        # ユーザー辞書を存在しないパスに設定
        non_existent_path = self.temp_path / "non_existent.xlsx"
        config.custom_dictionary_path = non_existent_path
        config.auto_dictionary_path = self.auto_dict_path

        try:
            # 辞書をロード（自動辞書にフォールバックするはず）
            success, message = self.keyword_dict.load()

            # ロードが成功したか確認
            self.assertTrue(success)
            self.assertIn("自動辞書を読み込みました", message)

            # ソースタイプが正しいか確認
            self.assertEqual(self.keyword_dict.source_type, "auto")

            # 辞書の内容が正しいか確認
            self.assertEqual(len(self.keyword_dict.keywords), 3)
            self.assertEqual(self.keyword_dict.keywords["上場廃止"], 9)

        finally:
            # 設定を元に戻す
            config.custom_dictionary_path = orig_custom
            config.auto_dictionary_path = orig_auto

    def test_backup_dictionary(self):
        """辞書のバックアップテスト"""
        # テスト用の設定
        from config import config

        # 一時的に設定を変更
        orig_backup = config.backup_dir
        config.backup_dir = self.backup_dir

        try:
            # 辞書のソース設定
            self.keyword_dict.source_type = "user"
            self.keyword_dict.source_path = self.user_dict_path

            # バックアップを作成
            backup_path = self.keyword_dict.backup_current_dictionary()

            # バックアップが作成されたか確認
            self.assertIsNotNone(backup_path)
            self.assertTrue(backup_path.exists())

            # バックアップの名前が正しいか確認
            self.assertTrue("keywords_" in backup_path.name)
            self.assertTrue(backup_path.name.endswith(".xlsx"))

        finally:
            # 設定を元に戻す
            config.backup_dir = orig_backup

if __name__ == '__main__':
    unittest.main()