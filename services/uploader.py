from playwright.sync_api import sync_playwright
import datetime
from pathlib import Path
from config import config
from core.models import PodcastConfig, EpisodeMetadata, UploadStatus, DownloadStatus
from core.storage import StorageManager
from utils import logger

class PodcastUploaderService:
    @staticmethod
    def upload_episode(podcast_id: str, episode_id: str) -> None:
        """异步服务：控制真实后台拉起浏览器负责处理单一分集的发布行为"""
        podcast = StorageManager.get_podcast(podcast_id)
        meta = StorageManager.load_episode_metadata(podcast_id, episode_id)
        
        if not podcast or not meta:
            logger.error("Podcast or metadata not found.")
            return

        # 强门槛：非下载成功状态不可点击上传
        if meta.download_status != DownloadStatus.DOWNLOADED or not meta.local_audio_file:
            logger.error(f"Audio for {meta.title} not downloaded fully, abort.")
            meta.upload_status = UploadStatus.UPLOAD_FAILED
            meta.upload_error = "必须下载完对应本地文件后才可进行上传校验"
            StorageManager.save_episode_metadata(podcast_id, meta)
            return

        ep_dir = StorageManager.get_episode_dir(podcast_id, episode_id)
        audio_path = ep_dir / meta.local_audio_file
        cover_path = ep_dir / meta.local_cover_file if meta.local_cover_file else None

        if not audio_path.exists():
            meta.upload_status = UploadStatus.UPLOAD_FAILED
            meta.upload_error = "物理路径中丢失底层录音资源无法推进上传。"
            StorageManager.save_episode_metadata(podcast_id, meta)
            return

        meta.upload_status = UploadStatus.UPLOADING
        meta.upload_error = None  # 重置错误状态
        StorageManager.save_episode_metadata(podcast_id, meta)

        success = False
        error_msg = None
        
        # NOTE: 此为主流阻塞过程
        try:
            with sync_playwright() as p:
                logger.info(f"启动浏览器引擎，即将登录目标面板发布: {meta.title}")
                # 使用老版预设好的是否弹出框体策略
                browser = p.chromium.launch(headless=config.playwright_headless)
                
                # 读取与预加载登录鉴权 (此处延用了旧代码理念，未来可以对多 Podcast 抽象不同 state_file)
                if config.storage_state_path.exists():
                    logger.info("已读取历史登录态继续服役。")
                    context = browser.new_context(storage_state=config.storage_state_path)
                else:
                    logger.warning("并未发现该系统环境下的登录鉴权文件，可能发生卡死让您扫码...")
                    context = browser.new_context()

                page = context.new_page()
                
                # ====== 填报行为控制逻辑 ======
                target_url = podcast.target_upload_url
                page.goto(target_url)
                page.wait_for_load_state("networkidle")
                
                # 音频预交火
                page.locator(config.audio_upload_selector).set_input_files(str(audio_path))
                page.wait_for_timeout(10000)
                page.locator(config.next_button_selector).click()
                
                # 进入子页面
                page.wait_for_load_state("networkidle")
                page.locator(config.title_selector).fill(meta.title)
                
                # 展开子页面折叠配置属性信息
                desc_area = page.locator(".add_channel_textarea_last")
                expand_btn = page.locator(".arrow_header.articleInfo").first
                try:
                    expand_btn.wait_for(state="attached", timeout=5000)
                    if not desc_area.is_visible():
                        expand_btn.click(force=True)
                        page.wait_for_timeout(1500)
                except Exception:
                    pass
                
                # 表单信息交火
                page.locator(config.desc_selector).fill(meta.description_text)
                if cover_path and cover_path.exists():
                    page.locator(config.cover_upload_selector).set_input_files(str(cover_path))
                    page.wait_for_timeout(3000)
                    
                page.locator(config.if_read_checkbox_selector).click(force=True)
                
                submit_btn = page.locator(config.submit_button_selector)
                
                # 挂接防劫持弹窗回调
                page.once("dialog", lambda dialog: dialog.accept())
                
                submit_btn.click()
                page.wait_for_timeout(10000) 
                
                success = True
                
                context.close()
                browser.close()
                
        except Exception as e:
            logger.error(f"网页填报与爬虫在处理 {episode_id} 时触发阻断事故: {str(e)}")
            error_msg = str(e)
            
        # 写盘最终结论
        if success:
            meta.upload_status = UploadStatus.UPLOADED
            meta.uploaded_at = datetime.datetime.now().isoformat()
        else:
            meta.upload_status = UploadStatus.UPLOAD_FAILED
            meta.upload_error = error_msg
            
        StorageManager.save_episode_metadata(podcast_id, meta)
