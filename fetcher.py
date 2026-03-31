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

    def fetch_pending_episode(self, state_manager) -> Optional[PodcastEpisode]:
        """抓取并解析最新的播客数据。如果最新已上传，就接着往下顺延，直到找到一条新的。"""
        logger.info(f"正在获取 RSS 源: {self.rss_url}")
        feed = feedparser.parse(self.rss_url)
        
        if not feed.entries:
            logger.error("RSS 源中未找到任何内容。请检查 URL。")
            return None
        
        # 按照 RSS 提供的时间顺序（通常是从最新到最旧）遍历
        for entry in feed.entries:
            # 1. 解析音频 URL
            audio_url = None
            for link in entry.get("links", []):
                if link.get("type", "").startswith("audio/") or link.get("href", "").endswith((".mp3", ".m4a")):
                    audio_url = link.get("href")
                    break
                    
            if not audio_url:
                continue

            episode_id = entry.get("id", entry.get("link", audio_url))
            
            # 2. 从 feedparser 或者 itunes 标签中获取季/集信息
            season_num = entry.get("itunes_season", "")
            episode_num = entry.get("itunes_episode", "")
            original_title = entry.get("title", "未命名播客")
            
            prefix = ""
            if season_num and episode_num:
                prefix = f"S{season_num}E{episode_num} - "
            elif episode_num:
                prefix = f"E{episode_num} - "
                
            # 拼接作为最终用于展示与排重用的 Title
            if prefix and not original_title.startswith(prefix.replace(" -", "")):
                final_title = f"{prefix}{original_title}"
            else:
                final_title = original_title

            # 3. 询问排重中心这集是否发过（双重校验 id 与拼装过的标题）
            if state_manager.is_uploaded(episode_id, final_title):
                continue
                
            # === 如果顺利走到这里，证明我们找到了“第一个还没搬过的全新播客” ===
            
            # 4. 获取封面（从集 或者 顶层）
            cover_url = None
            if "image" in entry and "href" in entry.image:
                cover_url = entry.image.href
            elif "image" in feed.feed and "href" in feed.feed.image:
                cover_url = feed.feed.image.href
                
            episode = PodcastEpisode(
                id=episode_id,
                title=final_title,
                description=clean_description(entry.get("description", "")),
                audio_url=audio_url,
                cover_url=cover_url,
                published_date=entry.get("published", "")
            )
            
            logger.info(f"成功锁定未搬运的分集: {episode.title}")
            return episode

        logger.info("🎉 检查完毕，最新与过往播客均已存在搬运记录，暂无新内容！")
        return None

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

    def _download_file(self, url: str, path: Path, referer: str | None = None) -> None:
        """分块下载大文件的工具方法"""
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
