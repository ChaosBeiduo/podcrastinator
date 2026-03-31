import json
import re
import datetime
import email.utils
from pathlib import Path
from typing import List, Optional
from core.models import PodcastConfig, EpisodeMetadata

DATA_DIR = Path("data")
PODCASTS_DIR = DATA_DIR / "podcasts"
CONFIG_FILE = DATA_DIR / "podcasts_config.json"

class StorageManager:
    """提供统一的持久层访问，所有依赖 `data/` 目录的读写均在这里抽象。"""
    
    @staticmethod
    def _sanitize_id(raw_id: str) -> str:
        # 移除不可用于文件夹名称的特殊字符，保留字母数字和服务符
        safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_id)
        # 防止名称过长
        return safe_id[-100:]

    @staticmethod
    def _get_podcast_dir(podcast_id: str) -> Path:
        return PODCASTS_DIR / StorageManager._sanitize_id(podcast_id)
        
    @staticmethod
    def _get_episode_dir(podcast_id: str, episode_id: str) -> Path:
        pod_dir = StorageManager._get_podcast_dir(podcast_id)
        safe_ep_id = StorageManager._sanitize_id(episode_id)
        return pod_dir / "episodes" / safe_ep_id
        
    # --- 播客级配置 CRUD ---
    
    @staticmethod
    def load_all_podcasts() -> List[PodcastConfig]:
        if not CONFIG_FILE.exists():
            return []
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [PodcastConfig(**item) for item in data]
        except Exception:
            return []

    @staticmethod
    def get_podcast(podcast_id: str) -> Optional[PodcastConfig]:
        for p in StorageManager.load_all_podcasts():
            if p.id == podcast_id:
                return p
        return None

    @staticmethod
    def save_podcast(podcast: PodcastConfig):
        podcasts = StorageManager.load_all_podcasts()
        # 更新或追加
        updated = False
        for i, p in enumerate(podcasts):
            if p.id == podcast.id:
                podcasts[i] = podcast
                updated = True
                break
        if not updated:
            podcasts.append(podcast)
            
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump([p.model_dump() for p in podcasts], f, ensure_ascii=False, indent=2)

    # --- 各分集级的 CRUD ---

    @staticmethod
    def get_all_episodes(podcast_id: str) -> List[EpisodeMetadata]:
        episodes_dir = StorageManager._get_podcast_dir(podcast_id) / "episodes"
        if not episodes_dir.exists():
            return []
            
        eps = []
        for ep_dir in episodes_dir.iterdir():
            if ep_dir.is_dir():
                meta_file = ep_dir / "metadata.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            eps.append(EpisodeMetadata(**json.load(f)))
                    except Exception as e:
                        print(f"Error loading {meta_file}: {e}")
                        
        def _parse_pub_date(date_str: str) -> datetime.datetime:
            if not date_str:
                return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
            try:
                return email.utils.parsedate_to_datetime(date_str)
            except Exception:
                # 兼容非常规时间的保底处理
                return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
                
        # 按照发布时间倒序排列（从最新到最旧）
        eps.sort(key=lambda x: _parse_pub_date(x.published_at), reverse=True)
        return eps

    @staticmethod
    def load_episode_metadata(podcast_id: str, episode_id: str) -> Optional[EpisodeMetadata]:
        meta_file = StorageManager._get_episode_dir(podcast_id, episode_id) / "metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    return EpisodeMetadata(**json.load(f))
            except Exception:
                pass
        return None

    @staticmethod
    def save_episode_metadata(podcast_id: str, metadata: EpisodeMetadata):
        ep_dir = StorageManager._get_episode_dir(podcast_id, metadata.id)
        ep_dir.mkdir(parents=True, exist_ok=True)
        
        # 为了可读性和以后其他平台可能需要，将正文纯文本单独写出来供核查
        if metadata.description_text:
            with open(ep_dir / metadata.local_description_file, "w", encoding="utf-8") as f:
                f.write(metadata.description_text)
                
        # 每次覆盖保存 metadata.json
        meta_file = ep_dir / "metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata.model_dump(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def get_episode_dir(podcast_id: str, episode_id: str) -> Path:
        """用于外部获取真实的下载存储基础路径"""
        return StorageManager._get_episode_dir(podcast_id, episode_id)
