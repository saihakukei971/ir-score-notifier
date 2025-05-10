import json
import httpx
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
from tqdm import tqdm
from loguru import logger
from typing import List, Dict, Any, Set, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from bs4 import BeautifulSoup
import sudachipy
from sudachipy import tokenizer, dictionary
from parsel import Selector
from config import config
from keyword_loader import keyword_dict

class AutoKeywordGenerator:
    """IR関連のキーワードを自動的に生成するクラス"""

    def __init__(self):
        self.tokenizer = dictionary.Dictionary().create()
        self.mode = tokenizer.Tokenizer.SplitMode.C  # デフォルトは連結モード

        # ストップワードの設定（一般的な単語で重要度が低いもの）
        self.stop_words = set([
            'の', 'に', 'は', 'を', 'た', 'が', 'で', 'て', 'と', 'し', 'れ', 'さ',
            'ある', 'いる', 'する', 'なる', 'できる', 'こと', 'もの', 'これ', 'それ',
            '当社', '株式会社', '会社', '企業', '開示', '適時開示', 'お知らせ', '発表',
            '月', '年', '日', '平成', '令和', '上場', '証券', '報告', '公開'
        ])

        # TF-IDFベクトライザ
        self.vectorizer = TfidfVectorizer(
            analyzer='word',
            tokenizer=self._tokenize,
            min_df=2,  # 少なくとも2つの文書に出現する単語を対象
            max_df=0.85  # 85%以上の文書に出現する単語は無視
        )

    def _tokenize(self, text: str) -> List[str]:
        """
        テキストをトークン化する
        Args:
            text: 処理するテキスト
        Returns:
            List[str]: トークンのリスト
        """
        tokens = []
        for token in self.tokenizer.tokenize(text, self.mode):
            # 基本形を取得
            base_form = token.dictionary_form()
            # 品詞情報を取得
            pos = token.part_of_speech()

            # 名詞、動詞、形容詞のみを抽出
            if (pos[0] == '名詞' or pos[0] == '動詞' or pos[0] == '形容詞') and len(base_form) > 1:
                if base_form not in self.stop_words:
                    tokens.append(base_form)

        return tokens

    async def fetch_ir_news(self, limit: int = 50) -> List[str]:
        """
        IR情報を取得する（PR TIMES, 東証サイトなど）
        Args:
            limit: 取得するニュースの最大数
        Returns:
            List[str]: IR本文のリスト
        """
        ir_texts = []

        # PR TIMESからIR関連ニュースを取得
        try:
            logger.info("PR TIMESからIRニュースを取得中...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = "https://prtimes.jp/main/html/searchrlp/key/%E6%B1%BA%E7%AE%97"
                response = await client.get(url)
                response.raise_for_status()

                selector = Selector(text=response.text)
                news_links = selector.css('h3.list-title a::attr(href)').getall()

                for i, link in enumerate(tqdm(news_links[:limit // 2], desc="PR TIMES記事")):
                    if not link.startswith('http'):
                        link = f"https://prtimes.jp{link}"

                    try:
                        news_response = await client.get(link)
                        news_response.raise_for_status()

                        news_selector = Selector(text=news_response.text)

                        # 記事本文を抽出
                        paragraphs = news_selector.css('.prtimes-article-body p::text').getall()
                        text = ' '.join(paragraphs)

                        if text and len(text) > 100:  # 十分な長さのテキストのみ
                            ir_texts.append(text)
                    except Exception as e:
                        logger.error(f"記事の取得に失敗しました: {link}, エラー: {str(e)}")

        except Exception as e:
            logger.error(f"PR TIMESからのニュース取得に失敗しました: {str(e)}")

        # 東証ウェブサイトからIR情報を取得（TDnetのRSS）
        try:
            logger.info("東証からIRニュースを取得中...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = "https://www.release.tdnet.info/inbs/I_list_001_20230518.html"
                response = await client.get(url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.select('table.tablelist-mid a')

                for i, link in enumerate(tqdm(links[:limit // 2], desc="東証IR情報")):
                    if 'href' not in link.attrs:
                        continue

                    href = link['href']
                    if not href.startswith('http'):
                        base_url = "https://www.release.tdnet.info/inbs/"
                        href = f"{base_url}{href}"

                    try:
                        news_response = await client.get(href)
                        news_response.raise_for_status()

                        news_soup = BeautifulSoup(news_response.text, 'html.parser')
                        # PDFへのリンクから情報を抽出
                        title = news_soup.select_one('title')
                        if title:
                            ir_texts.append(title.text)
                    except Exception as e:
                        logger.error(f"IR情報の取得に失敗しました: {href}, エラー: {str(e)}")

        except Exception as e:
            logger.error(f"東証からのIR情報取得に失敗しました: {str(e)}")

        logger.info(f"合計 {len(ir_texts)} 件のIRテキストを取得しました")
        return ir_texts

    def generate_keywords(self, texts: List[str], max_keywords: int = 200) -> Dict[str, int]:
        """
        TEXTからキーワードを生成する
        Args:
            texts: IR本文のリスト
            max_keywords: 生成するキーワードの最大数
        Returns:
            Dict[str, int]: キーワードとスコアの辞書
        """
        if not texts:
            logger.error("キーワード生成に必要なテキストがありません")
            return {}

        try:
            # TF-IDF行列を計算
            X = self.vectorizer.fit_transform(texts)

            # 特徴量名（単語）を取得
            feature_names = np.array(self.vectorizer.get_feature_names_out())

            # 各単語のTF-IDFスコアの平均を計算
            tfidf_mean = np.array(X.mean(axis=0)).flatten()

            # スコア順にソート
            sorted_indices = np.argsort(tfidf_mean)[::-1]

            # 上位のキーワードを抽出
            keywords = {}

            for idx in sorted_indices[:max_keywords]:
                word = feature_names[idx]

                # 単語の長さチェック（短すぎる単語を除外）
                if len(word) < 2:
                    continue

                # TF-IDFスコアをIRインパクトスコア（0-10）に変換
                # スコアの正規化: 0.01-0.5程度の範囲を0-10に変換
                score_normalized = min(10, max(1, int(tfidf_mean[idx] * 20)))

                # 特殊なIR単語は重みづけ
                if word in ["赤字", "損失", "減損", "訴訟", "倒産", "廃業", "解散", "上場廃止"]:
                    score_normalized = max(8, score_normalized)  # 最低8点
                elif word in ["黒字", "増益", "好調", "拡大", "成長", "提携", "買収"]:
                    score_normalized = max(6, score_normalized)  # 最低6点

                keywords[word] = score_normalized

            logger.info(f"{len(keywords)}個のキーワードを生成しました")
            return keywords

        except Exception as e:
            logger.error(f"キーワード生成中にエラーが発生しました: {str(e)}")
            return {}

    async def generate_dictionary(self) -> Dict[str, int]:
        """
        辞書を生成してファイルに保存する
        Returns:
            Dict[str, int]: 生成されたキーワード辞書
        """
        try:
            # 現在の辞書をバックアップ
            if keyword_dict.source_path and keyword_dict.source_path.exists():
                keyword_dict.backup_current_dictionary()

            # IR情報を取得
            ir_texts = await self.fetch_ir_news(limit=100)

            if not ir_texts:
                logger.warning("IR情報が取得できませんでした。辞書を生成できません。")
                return {}

            # キーワードを生成
            keywords = self.generate_keywords(ir_texts)

            if not keywords:
                logger.warning("キーワードが生成できませんでした。")
                return {}

            # 自動辞書ディレクトリが存在しない場合は作成
            auto_dict_dir = config.auto_dictionary_path.parent
            auto_dict_dir.mkdir(exist_ok=True, parents=True)

            # ファイルに保存
            with open(config.auto_dictionary_path, 'w', encoding='utf-8') as f:
                json.dump(keywords, f, ensure_ascii=False, indent=2)

            logger.success(f"自動辞書を生成しました: {config.auto_dictionary_path}")
            return keywords

        except Exception as e:
            logger.error(f"辞書生成中にエラーが発生しました: {str(e)}")
            return {}