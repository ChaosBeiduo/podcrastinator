import sys
from config import config
from utils import logger
from fetcher import PodcastFetcher
from state_manager import StateManager
from uploader import PodcastUploader

def main() -> None:
    logger.info("=== 🚀 开始播客自动搬运流程 ===")
    
    if not config.podcast_rss_url:
        logger.error("未发现 PODCAST_RSS_URL 配置。请在 .env 中进行配置后重试。")
        sys.exit(1)

    # 1. 检查状态记录
    state_manager = StateManager(config.state_file)
    
    # 2. 抓取 RSS 最新分集
    fetcher = PodcastFetcher(config.podcast_rss_url, config.download_dir)
    episode = fetcher.fetch_latest_episode()
    
    if not episode:
        logger.error("获取博客失败，流程终止。")
        sys.exit(1)

    # 3. 避免重复上传判定
    if state_manager.is_uploaded(episode.id):
        logger.info(f"⏭️ 播客 '{episode.title}' 已存在上传记录，跳过本次执行。")
        sys.exit(0)
        
    # 4. 下载本地需要的素材
    if not fetcher.download_assets(episode):
        logger.error("媒体资源下载失败，流程终止。")
        sys.exit(1)
        
    # 5. 打开 Playwright 自动化浏览器操作上传
    with PodcastUploader() as uploader:
        # 如果不存在已保存的登录态，那么开启一个强制的互动窗口，请用户手动登录一次
        if not config.storage_state_path.exists():
            logger.info("🔧 检测到缺少浏览器 Session (首次执行)，将进入引导登录逻辑。")
            uploader.ensure_login(config.target_upload_url)
            
        success = uploader.upload_episode(episode)
        
    # 6. 后置处理与记录
    if success:
        state_manager.mark_uploaded(episode)
        logger.info("=== 🎉 恭喜，全部流程执行成功 ===")
    else:
        logger.error("=== 💥 错误：上传流程中断，未修改成功状态记录。 ===")
        sys.exit(1)

if __name__ == "__main__":
    main()
