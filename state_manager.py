import json
from pathlib import Path
from typing import Dict, Any
from utils import logger, PodcastEpisode

class StateManager:
    """负责管理本地记录，防止播客重复上传"""
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state: Dict[str, Any] = self._load_state()
        self._migrate_state()

    def _migrate_state(self):
        """兼容旧版数据，将原本单条记录转换为列表"""
        modified = False
        if "uploaded_ids" not in self.state:
            self.state["uploaded_ids"] = []
            if "last_uploaded_id" in self.state:
                self.state["uploaded_ids"].append(self.state["last_uploaded_id"])
                modified = True
                
        if modified:
            self.save_state()

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

    def is_uploaded(self, episode_id: str, title: str = "") -> bool:
        """检查给定的播客 ID 或标题是否已上传过"""
        if episode_id in self.state.get("uploaded_ids", []):
            return True
            
        # 根据用户的需求，有时 ID 会变或者不准，我们辅助用集数 Title 来排重
        if title and title in self.state.get("uploaded_titles", []):
            return True
            
        return False

    def mark_uploaded(self, episode: PodcastEpisode) -> None:
        """记录该播客已经搬运完成"""
        if "uploaded_ids" not in self.state:
            self.state["uploaded_ids"] = []
        if "uploaded_titles" not in self.state:
            self.state["uploaded_titles"] = []
            
        if episode.id not in self.state["uploaded_ids"]:
            self.state["uploaded_ids"].append(episode.id)
            
        if episode.title not in self.state["uploaded_titles"]:
            self.state["uploaded_titles"].append(episode.title)
            
        # 兼容保留一份最后一次的记录给外部（如果有的话）
        self.state["last_uploaded_id"] = episode.id
        self.state["last_uploaded_title"] = episode.title
        self.state["last_uploaded_date"] = episode.published_date
        
        self.save_state()
