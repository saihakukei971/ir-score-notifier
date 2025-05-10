from pathlib import Path
from typing import Dict, Any, Optional, List
import json
from pydantic import BaseModel, validator
from loguru import logger

# プロジェクトルートディレクトリの取得
ROOT_DIR = Path(__file__).parent

class SlackConfig(BaseModel):
    webhook_url: str
    score_threshold: int = 80

    @validator('score_threshold')
    def threshold_must_be_valid(cls, v):
        if v < 0 or v > 100:
            raise ValueError('score_thresholdは0から100の間で設定してください')
        return v

class Config(BaseModel):
    slack: SlackConfig
    auto_dictionary_path: Path = ROOT_DIR / "auto_keywords" / "auto_keywords.json"
    custom_dictionary_path: Path = ROOT_DIR / "custom_keywords" / "keywords.xlsx"
    backup_dir: Path = ROOT_DIR / "backup"
    logs_dir: Path = ROOT_DIR / "logs"
    watch_dir: Optional[Path] = None

    class Config:
        arbitrary_types_allowed = True

def load_config() -> Config:
    """設定ファイルを読み込む"""
    config_path = ROOT_DIR / "config.json"
    
    if not config_path.exists():
        # デフォルト設定を作成
        default_config = {
            "slack": {
                "webhook_url": "https://hooks.slack.com/services/XXXXX",
                "score_threshold": 80
            },
            "watch_dir": None
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        
        logger.info(f"デフォルト設定ファイルを作成しました: {config_path}")
    
    # 設定ファイル読み込み
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    # 文字列形式のパスをPathオブジェクトに変換
    if 'watch_dir' in config_data and config_data['watch_dir']:
        config_data['watch_dir'] = Path(config_data['watch_dir'])
    
    return Config(**config_data)

# 設定の初期化
config = load_config()

# ディレクトリ作成
for dir_path in [config.backup_dir, config.logs_dir, 
                 config.auto_dictionary_path.parent, 
                 config.custom_dictionary_path.parent]:
    dir_path.mkdir(exist_ok=True, parents=True)