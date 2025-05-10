import flet as ft
from flet import (
    Page, AppBar, Text, TextField, ElevatedButton, Row, Column, Container,
    ListView, Card, IconButton, icons, ProgressBar, Tab, Tabs, AlertDialog,
    Switch, FilePickerResultEvent, FilePicker, PopupMenuButton, PopupMenuItem,
    TextButton, Checkbox, VerticalDivider, DataTable, DataColumn, DataRow, DataCell,
    Dropdown, dropdown, MainAxisAlignment, CrossAxisAlignment, colors, padding
)
from typing import List, Dict, Optional, Any, Callable, Awaitable
import os
import asyncio
import webbrowser
import subprocess
from datetime import datetime
from pathlib import Path
import csv
from loguru import logger

from config import config
from ir_reader import IRReader, IRDocument
from scorer import IRScorer
from notifier import IRNotifier
from auto_keywords_generator import AutoKeywordGenerator
from keyword_loader import keyword_dict
from watcher import IRWatcher

class IRNotifierGUI:
    """IR Impact Notifier GUIクラス"""

    def __init__(self, page: Page):
        self.page = page
        self.setup_page()

        # コンポーネントの初期化
        self.ir_reader = IRReader()
        self.ir_scorer = IRScorer()
        self.ir_notifier = IRNotifier()
        self.keyword_generator = AutoKeywordGenerator()
        self.ir_watcher = IRWatcher(self.process_new_file)

        # UIコンポーネント
        self.loading = False
        self.setup_ui_components()

        # 初期データのロード
        self.load_initial_data()

    def setup_page(self) -> None:
        """ページ設定"""
        self.page.title = "IR Impact Notifier"
        self.page.window_width = 1200
        self.page.window_height = 900
        self.page.window_min_width = 800
        self.page.window_min_height = 600
        self.page.theme_mode = ft.ThemeMode.SYSTEM
        self.page.padding = 20
        self.page.fonts = {
            "Noto Sans JP": "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap"
        }
        self.page.theme = ft.Theme(font_family="Noto Sans JP")

    def setup_ui_components(self) -> None:
        """UIコンポーネントの設定"""
        # ロード中インジケータ
        self.progress_bar = ProgressBar(visible=False)

        # ファイルピッカー
        self.file_picker = FilePicker(on_result=self.on_file_picked)
        self.page.overlay.append(self.file_picker)

        # 入力セクション
        self.input_tabs = Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                Tab(
                    text="テキスト入力",
                    icon=icons.TEXT_FIELDS,
                    content=self.build_text_input_section()
                ),
                Tab(
                    text="URL入力",
                    icon=icons.LINK,
                    content=self.build_url_input_section()
                ),
                Tab(
                    text="ファイル読込",
                    icon=icons.FILE_UPLOAD,
                    content=self.build_file_input_section()
                )
            ],
        )

        # スコア結果セクション
        self.result_section = Container(
            visible=False,
            content=Card(
                content=Container(
                    padding=20,
                    content=Column(
                        controls=[
                            Text("スコア結果", size=20, weight="bold"),
                            self.build_result_content(),
                        ],
                        spacing=10,
                    )
                )
            )
        )

        # 辞書管理セクション
        self.dictionary_section = Card(
            content=Container(
                padding=20,
                content=Column(
                    controls=[
                        Row(
                            controls=[
                                Text("辞書管理", size=20, weight="bold"),
                                IconButton(
                                    icon=icons.REFRESH,
                                    tooltip="辞書をリロード",
                                    on_click=self.reload_dictionary
                                )
                            ],
                            alignment=MainAxisAlignment.SPACE_BETWEEN
                        ),
                        self.build_dictionary_content(),
                    ],
                    spacing=10,
                )
            )
        )

        # 自動監視セクション
        self.watcher_section = Card(
            content=Container(
                padding=20,
                content=Column(
                    controls=[
                        Row(
                            controls=[
                                Text("自動監視", size=20, weight="bold"),
                                Switch(
                                    label="監視を有効化",
                                    value=False,
                                    on_change=self.toggle_watcher
                                )
                            ],
                            alignment=MainAxisAlignment.SPACE_BETWEEN
                        ),
                        self.build_watcher_content(),
                    ],
                    spacing=10,
                )
            )
        )

        # ログセクション
        self.log_section = Card(
            content=Container(
                padding=20,
                content=Column(
                    controls=[
                        Row(
                            controls=[
                                Text("最近のログ", size=20, weight="bold"),
                                IconButton(
                                    icon=icons.REFRESH,
                                    tooltip="ログをリロード",
                                    on_click=self.load_logs
                                )
                            ],
                            alignment=MainAxisAlignment.SPACE_BETWEEN
                        ),
                        self.build_log_content(),
                    ],
                    spacing=10,
                )
            )
        )

        # エラーダイアログ
        self.error_dialog = AlertDialog(
            title=Text("エラー"),
            content=Text(""),
            actions=[
                TextButton("OK", on_click=self.close_dialog),
            ],
        )

        # ページコンテンツの構築
        self.page.add(
            AppBar(
                title=Text("IR Impact Notifier"),
                center_title=True,
                bgcolor=colors.LIGHT_BLUE_700,
            ),
            self.progress_bar,
            Column(
                controls=[
                    Row(
                        controls=[
                            Container(
                                content=self.input_tabs,
                                expand=True,
                            ),
                        ],
                        alignment=MainAxisAlignment.START,
                    ),
                    self.result_section,
                    Row(
                        controls=[
                            Container(
                                content=self.dictionary_section,
                                expand=True,
                            ),
                            Container(
                                content=self.watcher_section,
                                expand=True,
                            ),
                        ],
                        alignment=MainAxisAlignment.START,
                    ),
                    self.log_section,
                ],
                spacing=20,
            ),
        )

    def build_text_input_section(self) -> Container:
        """テキスト入力セクションを構築"""
        self.text_input = TextField(
            label="IRニュース本文",
            multiline=True,
            min_lines=10,
            max_lines=15,
            value="",
            hint_text="ここにIRニュースの本文を貼り付けてください。",
        )

        self.text_title_input = TextField(
            label="タイトル（任意）",
            value="",
            hint_text="IRニュースのタイトルを入力してください。",
        )

        self.text_symbol_input = TextField(
            label="証券コード（任意）",
            value="",
            hint_text="証券コードを入力してください（例: 1234）",
        )

        return Container(
            padding=20,
            content=Column(
                controls=[
                    self.text_title_input,
                    self.text_symbol_input,
                    self.text_input,
                    Row(
                        controls=[
                            ElevatedButton(
                                "スコア計算",
                                icon=icons.CALCULATE,
                                on_click=self.calculate_score_from_text,
                            ),
                            ElevatedButton(
                                "クリア",
                                icon=icons.CLEAR,
                                on_click=self.clear_text_input,
                            ),
                        ],
                        alignment=MainAxisAlignment.END,
                    ),
                ],
                spacing=10,
            ),
        )

    def build_url_input_section(self) -> Container:
        """URL入力セクションを構築"""
        self.url_input = TextField(
            label="URL",
            value="",
            hint_text="IRニュースのURLを入力してください。",
        )

        return Container(
            padding=20,
            content=Column(
                controls=[
                    self.url_input,
                    Row(
                        controls=[
                            ElevatedButton(
                                "URLからスコア計算",
                                icon=icons.CALCULATE,
                                on_click=self.calculate_score_from_url,
                            ),
                            ElevatedButton(
                                "クリア",
                                icon=icons.CLEAR,
                                on_click=lambda e: setattr(self.url_input, "value", "") or self.page.update(),
                            ),
                        ],
                        alignment=MainAxisAlignment.END,
                    ),
                ],
                spacing=10,
            ),
        )

    def build_file_input_section(self) -> Container:
        """ファイル入力セクションを構築"""
        return Container(
            padding=20,
            content=Column(
                controls=[
                    Text("IRニュースファイルを選択してください："),
                    Row(
                        controls=[
                            ElevatedButton(
                                "テキストファイル選択",
                                icon=icons.UPLOAD_FILE,
                                on_click=lambda _: self.file_picker.pick_files(
                                    allowed_extensions=["txt", "html"],
                                    dialog_title="IRニュースファイルを選択"
                                ),
                            ),
                            ElevatedButton(
                                "CSVファイル選択 (複数処理)",
                                icon=icons.TABLE_CHART,
                                on_click=lambda _: self.file_picker.pick_files(
                                    allowed_extensions=["csv"],
                                    dialog_title="IR情報のCSVファイルを選択"
                                ),
                            ),
                        ],
                        alignment=MainAxisAlignment.CENTER,
                    ),
                ],
                spacing=10,
            ),
        )

    def build_result_content(self) -> Column:
        """結果表示部分を構築"""
        self.result_score = Text("", size=60, weight="bold")
        self.result_title = Text("", size=16, weight="bold")
        self.result_keywords = Text("", size=14)
        self.result_dictionary = Text("", size=14)
        self.result_notified = Text("", size=14)

        return Column(
            controls=[
                Row(
                    controls=[
                        Container(
                            content=self.result_score,
                            padding=10,
                            border_radius=10,
                            bgcolor=colors.BLUE_50,
                        ),
                        Column(
                            controls=[
                                self.result_title,
                                self.result_dictionary,
                                self.result_notified,
                            ],
                            spacing=5,
                            expand=True,
                        ),
                    ],
                    vertical_alignment=CrossAxisAlignment.CENTER,
                ),
                Container(
                    content=self.result_keywords,
                    padding=10,
                    border_radius=5,
                    bgcolor=colors.GREY_50,
                ),
            ],
            spacing=10,
        )

    def build_dictionary_content(self) -> Column:
        """辞書管理部分を構築"""
        self.dictionary_info = Text("", size=14)

        return Column(
            controls=[
                self.dictionary_info,
                Row(
                    controls=[
                        ElevatedButton(
                            "辞書再構築",
                            icon=icons.BUILD,
                            on_click=self.rebuild_dictionary,
                        ),
                        ElevatedButton(
                            "辞書をExcelで開く",
                            icon=icons.EDIT_DOCUMENT,
                            on_click=self.open_dictionary_excel,
                        ),
                    ],
                    alignment=MainAxisAlignment.CENTER,
                ),
            ],
            spacing=10,
        )

    def build_watcher_content(self) -> Column:
        """自動監視部分を構築"""
        self.watcher_info = Text("監視は無効です", size=14)
        self.watcher_dir_input = TextField(
            label="監視フォルダ",
            value=str(config.watch_dir) if config.watch_dir else "",
            hint_text="監視するフォルダのパスを入力",
            expand=True,
        )

        return Column(
            controls=[
                self.watcher_info,
                Row(
                    controls=[
                        self.watcher_dir_input,
                        IconButton(
                            icon=icons.FOLDER_OPEN,
                            tooltip="フォルダを選択",
                            on_click=lambda _: self.file_picker.get_directory_path(
                                dialog_title="監視フォルダを選択"
                            ),
                        ),
                    ],
                ),
            ],
            spacing=10,
        )

    def build_log_content(self) -> Column:
        """ログ表示部分を構築"""
        self.log_table = DataTable(
            columns=[
                DataColumn(Text("日時")),
                DataColumn(Text("証券コード")),
                DataColumn(Text("タイトル")),
                DataColumn(Text("スコア")),
                DataColumn(Text("通知")),
            ],
            rows=[],
        )

        return Column(
            controls=[
                Container(
                    content=self.log_table,
                    height=200,
                    border_radius=5,
                    border=ft.border.all(1, colors.GREY_400),
                ),
            ],
            spacing=10,
        )

    def load_initial_data(self) -> None:
        """初期データのロード"""
        # 辞書のロード
        self.reload_dictionary()

        # ログのロード
        self.load_logs()

        # 監視ディレクトリが設定されている場合は監視を開始
        if config.watch_dir and config.watch_dir.exists():
            watcher_switch = self.watcher_section.content.content.controls[0].controls[1]
            watcher_switch.value = True
            self.toggle_watcher(None)
            self.page.update()

    def reload_dictionary(self, e=None) -> None:
        """辞書をリロード"""
        success, message = keyword_dict.load()

        if success:
            source_info = keyword_dict.get_source_info()
            dict_type = source_info["type"].upper() if source_info["type"] else "不明"
            dict_path = source_info["path"] or "不明"
            keyword_count = len(keyword_dict.keywords)

            self.dictionary_info.value = f"辞書タイプ: {dict_type}\n辞書パス: {dict_path}\nキーワード数: {keyword_count}個"
        else:
            self.dictionary_info.value = f"辞書のロードに失敗しました: {message}"

        self.page.update()

    async def rebuild_dictionary(self, e) -> None:
        """辞書を再構築"""
        self.set_loading(True)

        # 辞書を自動生成
        try:
            keywords = await self.keyword_generator.generate_dictionary()

            if keywords:
                # 辞書をリロード
                self.reload_dictionary()

                # 成功ダイアログを表示
                self.show_dialog(
                    "辞書生成完了",
                    f"{len(keywords)}個のキーワードを生成して保存しました。",
                    is_error=False
                )
            else:
                self.show_dialog(
                    "辞書生成失敗",
                    "キーワードの生成に失敗しました。ログを確認してください。",
                    is_error=True
                )

        except Exception as ex:
            logger.error(f"辞書再構築中にエラーが発生しました: {ex}")
            self.show_dialog(
                "エラー",
                f"辞書の再構築中にエラーが発生しました: {str(ex)}",
                is_error=True
            )

        finally:
            self.set_loading(False)

    def open_dictionary_excel(self, e) -> None:
        """辞書をExcelで開く"""
        excel_path = config.custom_dictionary_path

        # 辞書ディレクトリが存在しない場合は作成
        excel_dir = excel_path.parent
        excel_dir.mkdir(exist_ok=True, parents=True)

        # ファイルが存在しない場合は新規作成
        if not excel_path.exists():
            try:
                import pandas as pd

                # テンプレート辞書を作成
                df = pd.DataFrame({
                    'word': ['赤字', '黒字', '増益', '減益', '合併', '上場廃止', '減損'],
                    'score': [8, 5, 6, 7, 6, 9, 8],
                    'note': ['重要度高', '好材料', '好材料', '重要度高', '重要度中', '最重要', '重要度高']
                })

                # Excelに保存
                df.to_excel(excel_path, index=False)
                logger.info(f"テンプレート辞書を作成しました: {excel_path}")

            except Exception as ex:
                logger.error(f"テンプレート辞書の作成に失敗しました: {ex}")
                self.show_dialog(
                    "エラー",
                    f"テンプレート辞書の作成に失敗しました: {str(ex)}",
                    is_error=True
                )
                return

        # Excelを開く
        try:
            if os.name == 'nt':  # Windows
                os.startfile(excel_path)
            elif os.name == 'posix':  # Mac/Linux
                subprocess.run(['open', excel_path] if os.uname().sysname == 'Darwin' else ['xdg-open', excel_path])

            logger.info(f"辞書をExcelで開きました: {excel_path}")

        except Exception as ex:
            logger.error(f"辞書をExcelで開けませんでした: {ex}")
            self.show_dialog(
                "エラー",
                f"辞書をExcelで開けませんでした: {str(ex)}",
                is_error=True
            )

    def load_logs(self, e=None) -> None:
        """ログを読み込む"""
        try:
            log_rows = []

            # 今日の日付でログファイル名を生成
            log_filename = f"score_log_{datetime.now().strftime('%Y%m%d')}.csv"
            log_path = config.logs_dir / log_filename

            if log_path.exists():
                with open(log_path, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        log_rows.append(
                            DataRow(
                                cells=[
                                    DataCell(Text(row.get('datetime', ''))),
                                    DataCell(Text(row.get('symbol', ''))),
                                    DataCell(Text(row.get('title', '')[:30] + "..." if len(row.get('title', '')) > 30 else row.get('title', ''))),
                                    DataCell(Text(row.get('score', ''))),
                                    DataCell(Text("✓" if row.get('notified', '').lower() == "true" else "✗")),
                                ]
                            )
                        )

            # 最大10行に制限
            self.log_table.rows = log_rows[-10:] if len(log_rows) > 10 else log_rows

            self.page.update()

        except Exception as e:
            logger.error(f"ログの読み込みに失敗しました: {e}")

    def toggle_watcher(self, e) -> None:
        """自動監視の切り替え"""
        switch = self.watcher_section.content.content.controls[0].controls[1]
        enabled = switch.value

        if enabled:
            # 監視を開始
            dir_path = Path(self.watcher_dir_input.value) if self.watcher_dir_input.value else None

            if not dir_path:
                self.show_dialog(
                    "エラー",
                    "監視フォルダを指定してください。",
                    is_error=True
                )
                switch.value = False
                self.page.update()
                return

            success = self.ir_watcher.start_watching(dir_path)

            if success:
                self.watcher_info.value = f"監視中: {dir_path}"
                # 設定を保存
                self.save_watch_dir_config(dir_path)
            else:
                switch.value = False
                self.watcher_info.value = "監視の開始に失敗しました"
                self.show_dialog(
                    "エラー",
                    f"監視の開始に失敗しました: {dir_path}",
                    is_error=True
                )
        else:
            # 監視を停止
            success = self.ir_watcher.stop_watching()

            if success:
                self.watcher_info.value = "監視は無効です"
            else:
                self.watcher_info.value = "監視の停止に失敗しました"

        self.page.update()

    def save_watch_dir_config(self, dir_path: Path) -> None:
        """監視ディレクトリ設定を保存"""
        try:
            import json

            config_path = Path(__file__).parent / "config.json"

            # 現在の設定を読み込む
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 監視ディレクトリを更新
            config_data['watch_dir'] = str(dir_path)

            # 設定を保存
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)

            logger.info(f"監視ディレクトリ設定を保存しました: {dir_path}")

        except Exception as e:
            logger.error(f"監視ディレクトリ設定の保存に失敗しました: {e}")

    def on_file_picked(self, e: FilePickerResultEvent) -> None:
        """ファイル選択時の処理"""
        if e.files and len(e.files) > 0:
            file_path = Path(e.files[0].path)
            self.process_file(file_path)
        elif e.path:  # ディレクトリ選択の場合
            dir_path = Path(e.path)
            self.watcher_dir_input.value = str(dir_path)
            self.page.update()

    def process_file(self, file_path: Path) -> None:
        """ファイルを処理"""
        asyncio.create_task(self._process_file_async(file_path))

    async def _process_file_async(self, file_path: Path) -> None:
        """ファイルを非同期処理"""
        self.set_loading(True)

        try:
            # ファイル拡張子によって処理を分岐
            suffix = file_path.suffix.lower()

            if suffix == '.csv':
                # CSV処理
                documents = self.ir_reader.read_from_csv(file_path)

                # 複数ドキュメントの処理
                results = []

                for doc in documents:
                    # スコア計算
                    scoring_result = self.ir_scorer.calculate_score(doc)

                    # スコアがしきい値を超えていれば通知
                    notification_result = await self.ir_notifier.notify_if_significant(scoring_result)

                    results.append((scoring_result, notification_result))

                # 最後の結果を表示
                if results:
                    self.display_result(results[-1][0], results[-1][1])

                # サマリーダイアログを表示
                notify_count = sum(1 for _, n in results if n.success)
                self.show_dialog(
                    "CSV処理完了",
                    f"{len(results)}件中{notify_count}件が通知しきい値を超えました。",
                    is_error=False
                )

            else:
                # テキストファイル処理
                doc = self.ir_reader.read_from_file(file_path)

                # スコア計算
                scoring_result = self.ir_scorer.calculate_score(doc)

                # スコアがしきい値を超えていれば通知
                notification_result = await self.ir_notifier.notify_if_significant(scoring_result)

                # 結果表示
                self.display_result(scoring_result, notification_result)

        except Exception as e:
            logger.error(f"ファイル処理中にエラーが発生しました: {e}")
            self.show_dialog(
                "エラー",
                f"ファイル処理中にエラーが発生しました: {str(e)}",
                is_error=True
            )

        finally:
            self.set_loading(False)

    async def process_new_file(self, file_path: Path) -> None:
        """新しいファイルを処理（監視モード用）"""
        try:
            logger.info(f"新しいファイルを処理します: {file_path}")

            # ファイル拡張子によって処理を分岐
            suffix = file_path.suffix.lower()

            if suffix == '.csv':
                # CSV処理
                documents = self.ir_reader.read_from_csv(file_path)

                # 複数ドキュメントの処理
                for doc in documents:
                    # スコア計算
                    scoring_result = self.ir_scorer.calculate_score(doc)

                    # スコアがしきい値を超えていれば通知
                    await self.ir_notifier.notify_if_significant(scoring_result)

            else:
                # テキストファイル処理
                doc = self.ir_reader.read_from_file(file_path)

                # スコア計算
                scoring_result = self.ir_scorer.calculate_score(doc)

                # スコアがしきい値を超えていれば通知
                await self.ir_notifier.notify_if_significant(scoring_result)

            # ログをリロード
            self.load_logs()

        except Exception as e:
            logger.error(f"ファイル監視処理中にエラーが発生しました: {e}")

    def clear_text_input(self, e) -> None:
        """テキスト入力をクリア"""
        self.text_input.value = ""
        self.text_title_input.value = ""
        self.text_symbol_input.value = ""
        self.page.update()

    def calculate_score_from_text(self, e) -> None:
        """テキストからスコアを計算"""
        content = self.text_input.value

        if not content:
            self.show_dialog(
                "エラー",
                "IRニュース本文を入力してください。",
                is_error=True
            )
            return

        asyncio.create_task(self._calculate_score_from_text_async())

    async def _calculate_score_from_text_async(self) -> None:
        """テキストからのスコア計算（非同期）"""
        self.set_loading(True)

        try:
            content = self.text_input.value
            title = self.text_title_input.value or "直接入力されたテキスト"
            symbol = self.text_symbol_input.value or ""

            # IRドキュメント作成
            doc = self.ir_reader.read_from_text(content, title, symbol)

            # スコア計算
            scoring_result = self.ir_scorer.calculate_score(doc)

            # スコアがしきい値を超えていれば通知
            notification_result = await self.ir_notifier.notify_if_significant(scoring_result)

            # 結果表示
            self.display_result(scoring_result, notification_result)

        except Exception as e:
            logger.error(f"スコア計算中にエラーが発生しました: {e}")
            self.show_dialog(
                "エラー",
                f"スコア計算中にエラーが発生しました: {str(e)}",
                is_error=True
            )

        finally:
            self.set_loading(False)

    def calculate_score_from_url(self, e) -> None:
        """URLからスコアを計算"""
        url = self.url_input.value

        if not url:
            self.show_dialog(
                "エラー",
                "URLを入力してください。",
                is_error=True
            )
            return

        asyncio.create_task(self._calculate_score_from_url_async())

    async def _calculate_score_from_url_async(self) -> None:
        """URLからのスコア計算（非同期）"""
        self.set_loading(True)

        try:
            url = self.url_input.value

            # URLからIRドキュメント読み込み
            doc = await self.ir_reader.read_from_url(url)

            # スコア計算
            scoring_result = self.ir_scorer.calculate_score(doc)

            # スコアがしきい値を超えていれば通知
            notification_result = await self.ir_notifier.notify_if_significant(scoring_result)

            # 結果表示
            self.display_result(scoring_result, notification_result)

        except Exception as e:
            logger.error(f"URLからのスコア計算中にエラーが発生しました: {e}")
            self.show_dialog(
                "エラー",
                f"URLからのスコア計算中にエラーが発生しました: {str(e)}",
                is_error=True
            )

        finally:
            self.set_loading(False)

    def display_result(self, scoring_result, notification_result) -> None:
        """結果を表示"""
        # スコア
        score = scoring_result.score
        self.result_score.value = f"{score}"

        # スコアによって色を変更
        if score >= 80:
            self.result_score.color = colors.RED_500
        elif score >= 60:
            self.result_score.color = colors.ORANGE_500
        elif score >= 40:
            self.result_score.color = colors.YELLOW_700
        else:
            self.result_score.color = colors.GREEN_500

        # タイトル
        self.result_title.value = f"タイトル: {scoring_result.document.title}"

        # 辞書タイプ
        self.result_dictionary.value = f"辞書タイプ: {scoring_result.dictionary_type.upper()}"

        # 使用キーワード
        if scoring_result.used_keywords:
            keyword_list = ", ".join([f"{k} ({v}点)" for k, v in scoring_result.used_keywords.items()])
            self.result_keywords.value = f"使用キーワード: {keyword_list}"
        else:
            self.result_keywords.value = "使用キーワード: なし"

        # 通知結果
        if notification_result.success:
            self.result_notified.value = "Slack通知: 送信済み"
            self.result_notified.color = colors.GREEN_600
        else:
            self.result_notified.value = f"Slack通知: 未送信（{notification_result.message}）"
            self.result_notified.color = colors.GREY_500

        # 結果セクションを表示
        self.result_section.visible = True

        # ページを更新
        self.page.update()

        # ログをリロード
        self.load_logs()

    def set_loading(self, loading: bool) -> None:
        """ロード状態の設定"""
        self.loading = loading
        self.progress_bar.visible = loading
        self.page.update()

    def show_dialog(self, title: str, message: str, is_error: bool = True) -> None:
        """ダイアログを表示"""
        self.error_dialog.title = Text(title)
        self.error_dialog.content = Text(message)

        if is_error:
            self.error_dialog.title.color = colors.RED_500
        else:
            self.error_dialog.title.color = colors.GREEN_600

        self.page.dialog = self.error_dialog
        self.error_dialog.open = True
        self.page.update()

    def close_dialog(self, e) -> None:
        """ダイアログを閉じる"""
        self.error_dialog.open = False
        self.page.update()