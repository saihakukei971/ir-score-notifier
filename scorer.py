from typing import Dict, List, Tuple, Set, Optional
import re
from collections import Counter
from loguru import logger
from pydantic import BaseModel
from keyword_loader import keyword_dict
from ir_reader import IRDocument

class ScoringResult(BaseModel):
    """スコアリング結果クラス"""
    score: int
    used_keywords: Dict[str, int]  # 単語 -> スコア
    document: IRDocument
    dictionary_type: str  # "user" または "auto"

class IRScorer:
    """IRスコア計算クラス"""

    def __init__(self):
        self.min_score = 0
        self.max_score = 100

    def calculate_score(self, document: IRDocument) -> ScoringResult:
        """
        IR文書のスコアを計算する
        Args:
            document: IR文書
        Returns:
            ScoringResult: スコアリング結果
        """
        # 辞書が読み込まれているか確認
        if not keyword_dict.keywords:
            success, message = keyword_dict.load()
            if not success:
                logger.error(f"辞書の読み込みに失敗しました: {message}")
                return ScoringResult(
                    score=0,
                    used_keywords={},
                    document=document,
                    dictionary_type="none"
                )

        content = document.content
        if not content:
            logger.warning("スコアリング対象のコンテンツが空です")
            return ScoringResult(
                score=0,
                used_keywords={},
                document=document,
                dictionary_type=keyword_dict.source_type or "none"
            )

        # 使用したキーワードとスコアを格納する辞書
        used_keywords = {}

        # コンテンツ内のキーワードをカウント
        word_counts = self._count_keywords(content)

        # 合計スコアを計算
        total_score = 0
        content_length = len(content)

        for word, count in word_counts.items():
            # 辞書からスコアを取得
            keyword_score = keyword_dict.get_word_score(word)

            if keyword_score > 0:
                # 出現回数によるスコア調整
                adjusted_score = self._adjust_score_by_frequency(keyword_score, count, content_length)

                # 使用したキーワードに追加
                used_keywords[word] = adjusted_score

                # 合計スコアに加算
                total_score += adjusted_score

        # 最終スコアを0-100に正規化
        normalized_score = min(100, max(0, min(100, total_score)))

        # 四捨五入して整数に
        final_score = round(normalized_score)

        logger.info(f"スコア計算結果: {final_score}, 使用キーワード: {len(used_keywords)}個")

        return ScoringResult(
            score=final_score,
            used_keywords=used_keywords,
            document=document,
            dictionary_type=keyword_dict.source_type or "none"
        )

    def _count_keywords(self, text: str) -> Dict[str, int]:
        """
        テキスト内のキーワード出現回数をカウント
        Args:
            text: 対象テキスト
        Returns:
            Dict[str, int]: キーワードと出現回数の辞書
        """
        word_counts = Counter()

        # 辞書の全キーワードをチェック
        for keyword in keyword_dict.keywords.keys():
            # キーワードが複合語の場合（スペースを含む）
            if ' ' in keyword:
                parts = keyword.split()
                # すべての部分が含まれているかチェック
                all_parts_present = all(part in text for part in parts)

                if all_parts_present:
                    # 正規表現を使って完全一致をカウント
                    pattern = re.compile(r'\b' + re.escape(keyword) + r'\b')
                    matches = pattern.findall(text)
                    word_counts[keyword] = len(matches)
            else:
                # 単一語の場合は単純に出現回数をカウント
                pattern = re.compile(r'\b' + re.escape(keyword) + r'\b')
                matches = pattern.findall(text)
                word_counts[keyword] = len(matches)

        return word_counts

    def _adjust_score_by_frequency(self, base_score: int, count: int, text_length: int) -> int:
        """
        出現頻度に基づいてスコアを調整
        Args:
            base_score: 基本スコア
            count: 出現回数
            text_length: テキスト長
        Returns:
            int: 調整後のスコア
        """
        # 頻度補正係数 (回数が増えるほど補正係数は上がるが、上限あり)
        frequency_factor = min(2.0, 1.0 + (count - 1) * 0.2)

        # 文書長による正規化 (長すぎる文書は希釈効果があるため)
        length_factor = min(1.0, 1000 / max(500, text_length))

        # スコア調整（基本スコア × 頻度補正 × 長さ補正)
        adjusted_score = round(base_score * frequency_factor * length_factor)

        return adjusted_score