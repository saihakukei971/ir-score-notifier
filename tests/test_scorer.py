import unittest
from pathlib import Path
from ir_reader import IRDocument
from scorer import IRScorer
from keyword_loader import KeywordDictionary, keyword_dict

class TestScorer(unittest.TestCase):

    def setUp(self):
        # テスト用キーワード辞書を設定
        self.test_dict = KeywordDictionary()
        self.test_dict.keywords = {
            "赤字": 8,
            "黒字": 5,
            "増益": 6,
            "減益": 7,
            "合併": 6,
            "上場廃止": 9,
            "減損": 8
        }
        self.test_dict.source_type = "test"
        self.test_dict.source_path = Path("test_dict.json")

        # 元のキーワード辞書を保持
        self.original_dict = keyword_dict.keywords
        self.original_source_type = keyword_dict.source_type
        self.original_source_path = keyword_dict.source_path

        # テスト用辞書を設定
        keyword_dict.keywords = self.test_dict.keywords
        keyword_dict.source_type = self.test_dict.source_type
        keyword_dict.source_path = self.test_dict.source_path

        # スコアラーのインスタンス化
        self.scorer = IRScorer()

    def tearDown(self):
        # 元のキーワード辞書を復元
        keyword_dict.keywords = self.original_dict
        keyword_dict.source_type = self.original_source_type
        keyword_dict.source_path = self.original_source_path

    def test_calculate_score_high(self):
        """高スコアケースのテスト"""
        doc = IRDocument(
            symbol="1234",
            title="当社の今期業績に関する重要なお知らせ",
            content="当社は本日、2023年3月期の業績予想について、営業利益が大幅な赤字となる見込みであることをお知らせします。"
                    "主な要因は、市場環境の悪化と為替変動の影響により、約100億円の減損処理を行うことによるものです。"
                    "これにより、上場来初の最終赤字に転落する見通しです。株主の皆様には深くお詫び申し上げます。",
            source="test"
        )

        result = self.scorer.calculate_score(doc)

        # 赤字が2回、減損が1回含まれるので高スコアになるはず
        self.assertGreaterEqual(result.score, 70)
        self.assertIn("赤字", result.used_keywords)
        self.assertIn("減損", result.used_keywords)
        self.assertEqual(result.dictionary_type, "test")

    def test_calculate_score_medium(self):
        """中スコアケースのテスト"""
        doc = IRDocument(
            symbol="1234",
            title="業績予想の修正に関するお知らせ",
            content="当社は本日、2023年3月期の業績予想について、前回発表予想から修正することをお知らせします。"
                    "主に海外事業の伸長により、営業利益は前回予想を10%上回る見込みとなりました。"
                    "引き続き黒字基調を維持し、増益となる見通しです。",
            source="test"
        )

        result = self.scorer.calculate_score(doc)

        # 黒字が1回、増益が1回含まれるので中程度のスコアになるはず
        self.assertGreaterEqual(result.score, 30)
        self.assertLessEqual(result.score, 60)
        self.assertIn("黒字", result.used_keywords)
        self.assertIn("増益", result.used_keywords)

    def test_calculate_score_low(self):
        """低スコアケースのテスト"""
        doc = IRDocument(
            symbol="1234",
            title="役員人事に関するお知らせ",
            content="当社は本日開催の取締役会において、下記のとおり役員人事を決議いたしましたのでお知らせいたします。"
                    "新任取締役候補：山田太郎（現 営業本部長）"
                    "退任取締役：佐藤次郎（現 管理本部担当）",
            source="test"
        )

        result = self.scorer.calculate_score(doc)

        # キーワードが含まれていないので低スコアになるはず
        self.assertLessEqual(result.score, 10)
        self.assertEqual(len(result.used_keywords), 0)

    def test_empty_content(self):
        """空のコンテンツのテスト"""
        doc = IRDocument(
            symbol="1234",
            title="空のお知らせ",
            content="",
            source="test"
        )

        result = self.scorer.calculate_score(doc)

        # 空コンテンツは0点になるはず
        self.assertEqual(result.score, 0)
        self.assertEqual(len(result.used_keywords), 0)

if __name__ == '__main__':
    unittest.main()