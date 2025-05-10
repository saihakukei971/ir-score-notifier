import unittest
import tempfile
import os
import pandas as pd
from pathlib import Path
from ir_reader import IRReader, IRDocument
import asyncio

class TestIRReader(unittest.TestCase):

    def setUp(self):
        # テスト用のIRリーダーインスタンス
        self.ir_reader = IRReader()

        # 一時ディレクトリを作成
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # テスト用のテキストファイルを作成
        self.test_file_path = self.temp_path / "1234_test.txt"
        with open(self.test_file_path, 'w', encoding='utf-8') as f:
            f.write("これはテスト用のIR文書です。証券コード：1234、当社は本日、業績予想の修正をお知らせします。")

        # テスト用のCSVファイルを作成
        self.test_csv_path = self.temp_path / "ir_data.csv"
        test_data = {
            'symbol': ['1234', '5678'],
            'title': ['業績予想の修正', '配当に関するお知らせ'],
            'content': [
                '当社は本日、業績予想の修正をお知らせします。当期の営業利益は10億円増加する見込みです。',
                '当社は本日、配当金を1株あたり20円とすることを決定いたしました。'
            ]
        }
        pd.DataFrame(test_data).to_csv(self.test_csv_path, index=False)

    def tearDown(self):
        # 一時ディレクトリを削除
        self.temp_dir.cleanup()

    def test_read_from_text(self):
        """テキストからの読み込みテスト"""
        text = "当社は本日、業績予想の修正をお知らせします。当期の営業利益は10億円増加する見込みです。"
        title = "業績予想の修正"
        symbol = "1234"

        doc = self.ir_reader.read_from_text(text, title, symbol)

        # 結果を確認
        self.assertEqual(doc.symbol, symbol)
        self.assertEqual(doc.title, title)
        self.assertEqual(doc.content, text)
        self.assertEqual(doc.source, "direct")

    def test_read_from_file(self):
        """ファイルからの読み込みテスト"""
        doc = self.ir_reader.read_from_file(self.test_file_path)

        # 結果を確認
        self.assertEqual(doc.symbol, "1234")
        self.assertEqual(doc.title, "1234_test")
        self.assertEqual(doc.content, "これはテスト用のIR文書です。証券コード：1234、当社は本日、業績予想の修正をお知らせします。")
        self.assertEqual(doc.source, "file")

    def test_read_from_csv(self):
        """CSVからの読み込みテスト"""
        docs = self.ir_reader.read_from_csv(self.test_csv_path)

        # 結果を確認
        self.assertEqual(len(docs), 2)

        # 1つ目のドキュメント
        self.assertEqual(docs[0].symbol, "1234")
        self.assertEqual(docs[0].title, "業績予想の修正")
        self.assertEqual(docs[0].content, "当社は本日、業績予想の修正をお知らせします。当期の営業利益は10億円増加する見込みです。")
        self.assertEqual(docs[0].source, "csv")

        # 2つ目のドキュメント
        self.assertEqual(docs[1].symbol, "5678")
        self.assertEqual(docs[1].title, "配当に関するお知らせ")
        self.assertEqual(docs[1].content, "当社は本日、配当金を1株あたり20円とすることを決定いたしました。")
        self.assertEqual(docs[1].source, "csv")

    def test_extract_symbol_from_text(self):
        """テキストからの証券コード抽出テスト"""
        texts = [
            "証券コード：1234、当社は本日...",
            "当社（証券コード：5678）は...",
            "コード：9012 当社は...",
            "株式会社テスト（3456）は...",
            "何も含まれていないテキスト"
        ]

        expected_symbols = ["1234", "5678", "9012", "3456", None]

        for text, expected in zip(texts, expected_symbols):
            result = self.ir_reader._extract_symbol_from_text(text)
            self.assertEqual(result, expected)

    @unittest.skip("実際のURL接続が必要なためCIでスキップ")
    def test_read_from_url(self):
        """URLからの読み込みテスト（実際のURL接続が必要なためオプション）"""
        # このテストは実際にURLに接続する必要があるため、CIでは実行しない
        # また、外部依存のあるテストは不安定になる可能性があるため注意が必要

        # テスト用のURL（例として公式な企業IR情報サイトなど安定したURLを使用するべき）
        url = "https://example.com/ir/test.html"

        # 非同期テスト用のヘルパー関数
        async def run_test():
            doc = await self.ir_reader.read_from_url(url)

            # 結果を確認
            self.assertIsNotNone(doc.title)
            self.assertNotEqual(doc.title, "")
            self.assertIsNotNone(doc.content)
            self.assertNotEqual(doc.content, "")
            self.assertEqual(doc.url, url)
            self.assertEqual(doc.source, "url")

        # 非同期関数を実行
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()