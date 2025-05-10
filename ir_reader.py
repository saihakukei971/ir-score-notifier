import httpx
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from parsel import Selector
from loguru import logger
from typing import Dict, List, Union, Optional, Any
from pydantic import BaseModel
import re
import urllib.parse

class IRDocument(BaseModel):
    """IRドキュメントクラス"""
    symbol: str = ""
    title: str = ""
    content: str = ""
    url: Optional[str] = None
    source: str = "direct"  # "direct", "url", "csv", "file"

class IRReader:
    """IR文書の読み込みクラス"""

    async def read_from_url(self, url: str) -> IRDocument:
        """
        URLからIR文書を読み込む
        Args:
            url: IR文書のURL
        Returns:
            IRDocument: 読み込んだIR文書
        """
        try:
            logger.info(f"URLからIR文書を読み込み中: {url}")

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

                # レスポンスヘッダーからエンコーディングを取得（デフォルトはUTF-8）
                encoding = response.encoding or 'utf-8'

                # コンテンツタイプを取得
                content_type = response.headers.get('content-type', '').lower()

                # HTMLの場合
                if 'text/html' in content_type:
                    return self._parse_html(response.text, url)

                # プレーンテキストの場合
                elif 'text/plain' in content_type:
                    return IRDocument(
                        symbol=self._extract_symbol_from_url(url),
                        title=self._extract_title_from_url(url),
                        content=response.text,
                        url=url,
                        source="url"
                    )

                # PDFなど未対応の形式
                else:
                    logger.warning(f"未対応のコンテンツタイプ: {content_type}")
                    return IRDocument(
                        symbol=self._extract_symbol_from_url(url),
                        title=f"[未対応形式] {self._extract_title_from_url(url)}",
                        content="",
                        url=url,
                        source="url"
                    )

        except Exception as e:
            logger.error(f"URLからの読み込みに失敗しました: {url}, エラー: {str(e)}")
            return IRDocument(
                title=f"[エラー] {url}",
                content=f"読み込みに失敗しました: {str(e)}",
                url=url,
                source="url"
            )

    def _parse_html(self, html: str, url: str) -> IRDocument:
        """
        HTML形式のIR文書をパースする
        Args:
            html: HTML本文
            url: 元のURL
        Returns:
            IRDocument: パースしたIR文書
        """
        # BeautifulSoupを使用してHTMLをパース
        soup = BeautifulSoup(html, 'html.parser')

        # タイトルを取得
        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else self._extract_title_from_url(url)

        # メタディスクリプションがあれば取得
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_content = meta_desc['content'] if meta_desc and 'content' in meta_desc.attrs else ""

        # Parselを使用して本文から不要な要素を除外
        selector = Selector(text=html)

        # ナビゲーション、ヘッダー、フッター、広告などを除外
        for tag in selector.css('nav, header, footer, aside, .ad, .advertisement, .banner, script, style'):
            tag.remove()

        # 本文の抽出（主要コンテンツエリアを推定）
        content_areas = selector.css('article, .content, .main, main, .article, #content, #main')

        if content_areas:
            # 最も内容が多そうなエリアを選択
            content = max([area.css('::text').getall() for area in content_areas],
                          key=lambda x: sum(len(text.strip()) for text in x if text.strip()))
            content_text = ' '.join([text.strip() for text in content if text.strip()])
        else:
            # 特定のコンテンツエリアが見つからない場合は全体から抽出
            paragraphs = selector.css('p::text').getall()
            content_text = ' '.join([p.strip() for p in paragraphs if p.strip()])

            # 本文が短すぎる場合はより広範囲から取得
            if len(content_text) < 200:
                body_texts = selector.css('body ::text').getall()
                content_text = ' '.join([text.strip() for text in body_texts if text.strip()])

        # 本文の前にメタディスクリプションを追加
        if meta_content and len(meta_content) > 50:
            content_text = meta_content + "\n\n" + content_text

        # 余分な空白や改行を整理
        content_text = re.sub(r'\s+', ' ', content_text).strip()

        # 証券コードを抽出
        symbol = self._extract_symbol_from_url(url)

        # URLから証券コードが取れない場合は本文から探す
        if not symbol:
            symbol = self._extract_symbol_from_text(content_text) or ""

        return IRDocument(
            symbol=symbol,
            title=title,
            content=content_text,
            url=url,
            source="url"
        )

    def _extract_symbol_from_url(self, url: str) -> str:
        """URLから証券コードを抽出"""
        # URLから証券コードを抽出する正規表現パターン
        patterns = [
            r'[/=]([\d]{4})[/\.]',  # /1234/ or =1234. など
            r'code=([\d]{4})',       # code=1234
            r'stock=([\d]{4})',      # stock=1234
            r'[/=]([\d]{4,5})[/\.]', # 5桁の証券コードも考慮
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return ""

    def _extract_title_from_url(self, url: str) -> str:
        """URLからタイトルを抽出"""
        try:
            # URLの最後のパスコンポーネントを取得
            parsed = urllib.parse.urlparse(url)
            path = parsed.path

            if not path or path == '/':
                return url.split('//')[1].split('/')[0]  # ドメイン名を返す

            # パスの最後の部分を取得
            last_part = path.rstrip('/').split('/')[-1]

            # ファイル拡張子があれば削除
            last_part = re.sub(r'\.[^.]+$', '', last_part)

            # URLエンコードされた文字をデコード
            last_part = urllib.parse.unquote(last_part)

            # ハイフンやアンダースコアをスペースに置換
            last_part = re.sub(r'[-_]', ' ', last_part)

            return last_part.title()  # 先頭文字を大文字にする

        except Exception:
            return url  # 何か問題があった場合はURLをそのまま返す

    def _extract_symbol_from_text(self, text: str) -> Optional[str]:
        """本文から証券コードを抽出"""
        # 証券コードのパターン
        patterns = [
            r'証券コード[：:]\s*([\d]{4})',
            r'コード[：:]\s*([\d]{4})',
            r'[\(（]([\d]{4})[\)）]',
            r'株式会社.{0,10}?([\d]{4})'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return None

    def read_from_text(self, text: str, title: str = "直接入力されたテキスト", symbol: str = "") -> IRDocument:
        """
        テキストから直接IR文書を読み込む
        Args:
            text: IR文書の本文
            title: IR文書のタイトル
            symbol: 証券コード
        Returns:
            IRDocument: 読み込んだIR文書
        """
        if not symbol:
            # テキストから証券コードを抽出
            symbol = self._extract_symbol_from_text(text) or ""

        return IRDocument(
            symbol=symbol,
            title=title,
            content=text,
            source="direct"
        )

    def read_from_file(self, file_path: Path) -> IRDocument:
        """
        ファイルからIR文書を読み込む
        Args:
            file_path: ファイルパス
        Returns:
            IRDocument: 読み込んだIR文書
        """
        try:
            logger.info(f"ファイルからIR文書を読み込み: {file_path}")

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # ファイル名を取得
            file_name = file_path.stem

            # ファイル名から証券コードを抽出
            symbol = ""
            match = re.search(r'([\d]{4})', file_name)
            if match:
                symbol = match.group(1)

            return IRDocument(
                symbol=symbol,
                title=file_name,
                content=content,
                source="file"
            )

        except Exception as e:
            logger.error(f"ファイルからの読み込みに失敗しました: {file_path}, エラー: {str(e)}")
            return IRDocument(
                title=f"[エラー] {file_path.name}",
                content=f"読み込みに失敗しました: {str(e)}",
                source="file"
            )

    def read_from_csv(self, file_path: Path) -> List[IRDocument]:
        """
        CSVファイルから複数のIR文書を読み込む
        Args:
            file_path: CSVファイルのパス
        Returns:
            List[IRDocument]: 読み込んだIR文書のリスト
        """
        try:
            logger.info(f"CSVからIR文書を読み込み: {file_path}")

            df = pd.read_csv(file_path)

            # 必要なカラムが存在するか確認
            required_columns = ['content']
            if not all(col in df.columns for col in required_columns):
                missing = [col for col in required_columns if col not in df.columns]
                raise ValueError(f"必要なカラムがCSVにありません: {', '.join(missing)}")

            documents = []

            for _, row in df.iterrows():
                content = row['content']

                # オプションのカラム
                symbol = str(row['symbol']) if 'symbol' in df.columns and pd.notna(row['symbol']) else ""
                title = str(row['title']) if 'title' in df.columns and pd.notna(row['title']) else f"CSV行 {_ + 1}"

                documents.append(IRDocument(
                    symbol=symbol,
                    title=title,
                    content=content,
                    source="csv"
                ))

            logger.info(f"CSVから{len(documents)}件のIR文書を読み込みました")
            return documents

        except Exception as e:
            logger.error(f"CSVからの読み込みに失敗しました: {file_path}, エラー: {str(e)}")
            return [IRDocument(
                title=f"[エラー] {file_path.name}",
                content=f"読み込みに失敗しました: {str(e)}",
                source="csv"
            )]