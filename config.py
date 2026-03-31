import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel

# 加载 .env 环境变量
load_dotenv()

class AppConfig(BaseModel):
    podcast_rss_url: str = os.getenv("PODCAST_RSS_URL", "")
    target_upload_url: str = os.getenv("TARGET_UPLOAD_URL", "")
    playwright_headless: bool = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"
    
    # 路径配置
    storage_state_path: Path = Path(os.getenv("STORAGE_STATE_PATH", "data/.auth/state.json"))
    download_dir: Path = Path(os.getenv("DOWNLOAD_DIR", "data/downloads"))
    state_file: Path = Path(os.getenv("STATE_FILE", "data/state.json"))

    # Web 元素选择器 (Selector)
    title_selector: str = os.getenv("TITLE_SELECTOR", "input[name='title']")
    desc_selector: str = os.getenv("DESC_SELECTOR", "textarea[name='description']")
    audio_upload_selector: str = os.getenv("AUDIO_UPLOAD_SELECTOR", "input[type='file'][accept='audio/*']")
    cover_upload_selector: str = os.getenv("COVER_UPLOAD_SELECTOR", "input[type='file'][accept='image/*']")
    next_button_selector: str = os.getenv("NEXT_BUTTON_SELECTOR", "button:has-text('下一步')")
    if_read_checkbox_selector: str = os.getenv("IF_READ_CHECKBOX_SELECTOR", "input[type='checkbox']")
    submit_button_selector: str = os.getenv("SUBMIT_BUTTON_SELECTOR", "button[type='submit']")

config = AppConfig()

# 确保必要的目录存在
config.download_dir.mkdir(parents=True, exist_ok=True)
config.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
config.state_file.parent.mkdir(parents=True, exist_ok=True)
