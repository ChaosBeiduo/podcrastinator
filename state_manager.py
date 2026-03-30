import json
from pathlib import Path
from typing import Dict, Any
from utils import logger, PodcastEpisode

class StateManager:
    """负责管理本地记录，防止播客重复上传"""
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """读取本地状态文件"""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"无法读取状态文件 {self.state_file}: {e}")
        return {}

    def save_state(self) -> None:
        """保存状态到本地"""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            logger.info("状态已保存至本地")
        except Exception as e:
            logger.error(f"无法保存状态文件: {e}")

    def is_uploaded(self, episode_id: str) -> bool:
        """检查给定的播客 ID 是否已上传过"""
        return self.state.get("last_uploaded_id") == episode_id

    def mark_uploaded(self, episode: PodcastEpisode) -> None:
        """标记当前播客已被成功上传记录"""
        self.state["last_uploaded_id"] = episode.id
        self.state["last_uploaded_title"] = episode.title
        self.state["last_uploaded_date"] = episode.published_date
        self.save_state()
