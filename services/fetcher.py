import feedparser
import requests
import datetime
from pathlib import Path
from typing import List, Optional
from core.models import PodcastConfig, EpisodeMetadata, DownloadStatus
from core.storage import StorageManager
from utils import logger, clean_description

class PodcastFetcherService:
    @staticmethod
    def sync_episodes(podcast: PodcastConfig) -> List[EpisodeMetadata]:
        """静默向 DB 中批量同步全部未存储过的播客数据（但不真正下载媒体文件）"""
        logger.info(f"Syncing RSS feed from: {podcast.rss_url}")
        feed = feedparser.parse(podcast.rss_url)
        
        if not feed.entries:
            logger.error("No entries found in RSS feed.")
            return []
            
        new_episodes = []
        for entry in feed.entries:
            audio_url = None
            for link in entry.get("links", []):
                if link.get("type", "").startswith("audio/") or link.get("href", "").endswith((".mp3", ".m4a")):
                    audio_url = link.get("href")
                    break
                    
            if not audio_url:
                continue

            # 使用获取到的 RSS 唯一标示（退化到 audio url）
            episode_id = entry.get("id", entry.get("link", audio_url))
            
            # --- 拼装集数信息 SxEx ---
            season_num = entry.get("itunes_season", "")
            episode_num = entry.get("itunes_episode", "")
            original_title = entry.get("title", "未命名播客")
            
            prefix = ""
            if season_num and episode_num:
                prefix = f"S{season_num}E{episode_num} - "
            elif episode_num:
                prefix = f"E{episode_num} - "
                
            if prefix and not original_title.startswith(prefix.replace(" -", "")):
                final_title = f"{prefix}{original_title}"
            else:
                final_title = original_title

            cover_url = None
            if "image" in entry and "href" in entry.image:
                cover_url = entry.image.href
            elif "image" in feed.feed and "href" in feed.feed.image:
                cover_url = feed.feed.image.href

            # 如果本地 metadata 已经存在它，就算旧的，我们目前 MVP 不强求每次同步更正它
            existing_meta = StorageManager.load_episode_metadata(podcast.id, episode_id)
            if existing_meta:
                continue

            episode = EpisodeMetadata(
                id=episode_id,
                title=final_title,
                description_html=entry.get("description", ""),
                description_text=clean_description(entry.get("description", "")),
                audio_url=audio_url,
                cover_url=cover_url,
                published_at=entry.get("published", "")
            )
            
            StorageManager.save_episode_metadata(podcast.id, episode)
            new_episodes.append(episode)
            
        logger.info(f"为播客 {podcast.title} 获取到 {len(new_episodes)} 条全新入库集数。")
        return new_episodes

    @staticmethod
    def _download_file(url: str, path: Path, referer: str | None = None) -> bool:
        """带请求头的物理文件分块下载器"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if referer:
            headers["Referer"] = referer

        try:
            response = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=(10, 120),
                allow_redirects=True,
            )
            response.raise_for_status()
            
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"媒体文件下载失败 {url}: {e}")
            return False

    @staticmethod
    def download_episode(podcast_id: str, episode_id: str) -> None:
        """异步服务：单独将某个具体的分集下载到本地 data 专用文件夹下面"""
        meta = StorageManager.load_episode_metadata(podcast_id, episode_id)
        if not meta:
            return

        meta.download_status = DownloadStatus.DOWNLOADING
        StorageManager.save_episode_metadata(podcast_id, meta)

        success = True
        ep_dir = StorageManager.get_episode_dir(podcast_id, episode_id)

        try:
            # 下载主录音
            audio_filename = "media.mp3"
            audio_path = ep_dir / audio_filename
            logger.info(f"开始存储录音到: {audio_path}")
            if PodcastFetcherService._download_file(meta.audio_url, audio_path):
                meta.local_audio_file = audio_filename
            else:
                success = False

            # 下载封面图如果存在
            if meta.cover_url:
                cover_filename = "cover.jpg"
                cover_path = ep_dir / cover_filename
                logger.info(f"开始存储封面图到: {cover_path}")
                if PodcastFetcherService._download_file(meta.cover_url, cover_path):
                    meta.local_cover_file = cover_filename
                else:
                    success = False

        except Exception as e:
            logger.error(f"下载集数时遭遇灾难性中断 {episode_id}: {e}")
            success = False

        # === 回写结果进 Metadata ===
        if success:
            meta.download_status = DownloadStatus.DOWNLOADED
            meta.downloaded_at = datetime.datetime.now().isoformat()
        else:
            meta.download_status = DownloadStatus.DOWNLOAD_FAILED

        StorageManager.save_episode_metadata(podcast_id, meta)
