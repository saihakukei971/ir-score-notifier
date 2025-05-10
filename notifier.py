import json
from loguru import logger
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import csv
import os
from config import config
from scorer import ScoringResult
from pydantic import BaseModel

class NotificationResult(BaseModel):
    """通知結果クラス"""
    success: bool
    message: str
    timestamp: datetime = datetime.now()

class IRNotifier:
    """IRニュース通知クラス"""

    def __init__(self):
        self.webhook_url = config.slack.webhook_url
        self.threshold = config.slack.score_threshold

    async def notify_if_significant(self, result: ScoringResult) -> NotificationResult:
        """
        重要なIRニュースの場合に通知する
        Args:
            result: スコアリング結果
        Returns:
            NotificationResult: 通知結果
        """
        # スコアがしきい値を超えているか確認
        if result.score < self.threshold:
            logger.info(f"スコア({result.score})がしきい値({self.threshold})未満のため通知しません")
            notification_result = NotificationResult(
                success=False,
                message=f"スコア({result.score})がしきい値({self.threshold})未満のため通知しません"
            )

            # ログに記録
            self._log_result(result, notification_result)

            return notification_result

        # Slack通知を送信
        try:
            notification_result = await self._send_slack_notification(result)

            # ログに記録
            self._log_result(result, notification_result)

            return notification_result

        except Exception as e:
            error_msg = f"通知送信中にエラーが発生しました: {str(e)}"
            logger.error(error_msg)

            notification_result = NotificationResult(
                success=False,
                message=error_msg
            )

            # ログに記録
            self._log_result(result, notification_result)

            return notification_result

    async def _send_slack_notification(self, result: ScoringResult) -> NotificationResult:
        """
        Slackに通知を送信する
        Args:
            result: スコアリング結果
        Returns:
            NotificationResult: 通知結果
        """
        # ドキュメント情報の取得
        doc = result.document

        # 使用キーワードの上位5つ（スコア順）
        top_keywords = sorted(
            [(k, v) for k, v in result.used_keywords.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        keyword_text = ", ".join([f"{k} ({v}点)" for k, v in top_keywords])

        # タイトルを取得（30文字まで）
        title = doc.title[:30] + "..." if len(doc.title) > 30 else doc.title

        # シンボル情報
        symbol_text = f"（{doc.symbol}）" if doc.symbol else ""

        # Slack通知内容の構築
        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📢 重大IR検知 - {result.score}点",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*タイトル:*\n{title}{symbol_text}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*スコア:*\n{result.score}点 / 100点"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*検出キーワード:*\n{keyword_text}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*辞書タイプ:*\n{result.dictionary_type.upper()}"
                        }
                    ]
                }
            ]
        }

        # URLがある場合はリンクを追加
        if doc.url:
            message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{doc.url}|ソースを開く>"
                }
            })

        # 文書の先頭100文字をプレビュー表示
        content_preview = doc.content[:100].replace('\n', ' ') + "..." if len(doc.content) > 100 else doc.content

        message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*プレビュー:*\n```{content_preview}```"
            }
        })

        # フッターを追加
        message["blocks"].append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"IR Impact Notifier • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })

        # SlackのWebhook URLが設定されているか確認
        if not self.webhook_url or self.webhook_url.startswith("https://hooks.slack.com/services/XXXXX"):
            logger.warning("有効なSlack Webhook URLが設定されていません")
            return NotificationResult(
                success=False,
                message="Webhook URLが正しく設定されていないため、通知は送信されませんでした。config.jsonを確認してください。"
            )

        # Slackに通知を送信
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json=message,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                logger.success(f"Slack通知を送信しました: {title} ({result.score}点)")
                return NotificationResult(
                    success=True,
                    message=f"Slack通知を送信しました: {title} ({result.score}点)"
                )
            else:
                error_msg = f"Slack通知の送信に失敗しました: ステータスコード {response.status_code}, レスポンス: {response.text}"
                logger.error(error_msg)
                return NotificationResult(
                    success=False,
                    message=error_msg
                )

    def _log_result(self, scoring_result: ScoringResult, notification_result: NotificationResult) -> None:
        """
        結果をCSVログに記録する
        Args:
            scoring_result: スコアリング結果
            notification_result: 通知結果
        """
        try:
            # 現在の日付でログファイル名を生成
            log_filename = f"score_log_{datetime.now().strftime('%Y%m%d')}.csv"
            log_path = config.logs_dir / log_filename

            # ディレクトリがない場合は作成
            config.logs_dir.mkdir(exist_ok=True, parents=True)

            # 使用キーワードをカンマ区切りの文字列に変換
            keywords_str = ", ".join([f"{k} ({v}点)" for k, v in scoring_result.used_keywords.items()])

            # CSVに記録する行データを作成
            row_data = {
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": scoring_result.document.symbol,
                "title": scoring_result.document.title,
                "score": scoring_result.score,
                "notified": notification_result.success,
                "dictionary_type": scoring_result.dictionary_type,
                "keywords_used": keywords_str,
                "notification_message": notification_result.message
            }

            # CSVファイルが存在するか確認
            file_exists = log_path.exists()

            # CSVファイルに追記
            with open(log_path, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=row_data.keys())

                # ファイルが新規作成された場合はヘッダーを書き込む
                if not file_exists:
                    writer.writeheader()

                writer.writerow(row_data)

            logger.debug(f"ログに記録しました: {log_path}")

        except Exception as e:
            logger.error(f"ログの記録中にエラーが発生しました: {str(e)}")