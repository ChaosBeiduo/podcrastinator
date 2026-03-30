import feedparser
import requests
from pathlib import Path
from typing import Optional
from utils import logger, PodcastEpisode, clean_description

class PodcastFetcher:
    """负责从 RSS 源解析最新的播客，并下载媒体文件"""
    
    def __init__(self, rss_url: str, download_dir: Path):
        self.rss_url = rss_url
        self.download_dir = download_dir

    def fetch_latest_episode(self) -> Optional[PodcastEpisode]:
        """抓取并解析最新的播客数据"""
        logger.info(f"正在获取 RSS 源: {self.rss_url}")
        feed = feedparser.parse(self.rss_url)
        
        if not feed.entries:
            logger.error("RSS 源中未找到任何内容。请检查 URL。")
            return None
        
        # 取最新的一条
        latest_entry = feed.entries[0]
        
        # 解析音频 URL
        audio_url = None
        for link in latest_entry.get("links", []):
            if link.get("type", "").startswith("audio/") or link.get("href", "").endswith((".mp3", ".m4a")):
                audio_url = link.get("href")
                break
                
        if not audio_url:
            logger.warning("未能从 RSS 中直接找到音频链接字段，尝试其他解析方式。")
            return None

        # 解析封面 URL (尝试从 entry 中获取，如果失败则尝试源的通用封面)
        cover_url = None
        if "image" in latest_entry and "href" in latest_entry.image:
            cover_url = latest_entry.image.href
        elif "image" in feed.feed and "href" in feed.feed.image:
            cover_url = feed.feed.image.href
            
        episode = PodcastEpisode(
            id=latest_entry.get("id", latest_entry.get("link", audio_url)),
            title=latest_entry.get("title", "未命名播客"),
            description=clean_description(latest_entry.get("description", "")),
            audio_url=audio_url,
            cover_url=cover_url,
            published_date=latest_entry.get("published", "")
        )
        
        logger.info(f"成功解析到最新播客: {episode.title}")
        return episode

    def download_assets(self, episode: PodcastEpisode) -> bool:
        """下载音频和图片封面到本地目录"""
        try:
            logger.info("开始下载音频文件...")
            # 从 URL 中获取文件名（去掉 Query strings）
            audio_filename = episode.audio_url.split("?")[0].split("/")[-1]
            if not audio_filename.endswith((".mp3", ".m4a")):
                audio_filename = "podcast.mp3"
            
            audio_path = self.download_dir / audio_filename
            self._download_file(episode.audio_url, audio_path)
            episode.local_audio_path = audio_path
            logger.info(f"音频下载完成: {audio_path}")

            if episode.cover_url:
                logger.info("开始下载封面图片...")
                cover_filename = episode.cover_url.split("?")[0].split("/")[-1]
                if not cover_filename.endswith((".jpg", ".png", ".jpeg", ".webp")):
                    cover_filename = "cover.jpg"
                    
                cover_path = self.download_dir / cover_filename
                self._download_file(episode.cover_url, cover_path)
                episode.local_cover_path = cover_path
                logger.info(f"封面下载完成: {cover_path}")
            else:
                logger.info("该播客未附带特殊的封面，已跳过下载。")
            
            return True
        except Exception as e:
            logger.error(f"下载媒体素材时失败: {e}")
            return False

    def _download_file(self, url: str, path: Path) -> None:
        """分块下载大文件的工具方法"""
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
