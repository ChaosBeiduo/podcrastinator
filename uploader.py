from playwright.sync_api import sync_playwright
from config import config
from utils import logger, PodcastEpisode

class PodcastUploader:
    """使用 Playwright 通过浏览器自动化将播客上传到目标平台"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    def __enter__(self):
        self.playwright = sync_playwright().start()
        logger.info(f"启动浏览器 (headless={config.playwright_headless})...")
        
        # 默认启动 Chromium
        self.browser = self.playwright.chromium.launch(headless=config.playwright_headless)
        
        # 尝试复用用户的登录态 (Storage State)
        if config.storage_state_path.exists():
            logger.info(f"检测到历史登录态: {config.storage_state_path}，正在加载...")
            self.context = self.browser.new_context(storage_state=config.storage_state_path)
        else:
            logger.info("未发现登录态历史，创建一个全新上下文。")
            self.context = self.browser.new_context()
            
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 退出并清理资源
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def ensure_login(self, target_url: str):
        """如果用户并未登录，要求用户手动完成首次登录并保存登录态"""
        page = self.context.new_page()
        logger.info(f"正在访问目标平台以检查登录记录: {target_url}")
        page.goto(target_url)
        
        # NOTE: 此处你可以实现一个校验是否存在的逻辑。
        # 如果存在登录相关的元素（比如 "Login" 按钮），代表未登录
        # if page.locator("text=Login").is_visible():
        
        logger.info("⚠️ 请在浏览器窗口中完成手动登录操作！")
        logger.info("等待您进行登录... 倒计时 60 秒 (若已登录可无视直接等待)...")
        
        try:
            # 给出充足时间进行扫码或密码登录，实际使用可使用 page.wait_for_selector(某登入后元素)
            page.wait_for_timeout(60000) 
            
            # 手动登录结束后保存 Session
            logger.info("保存当前的登录鉴权态...")
            self.context.storage_state(path=config.storage_state_path)
            logger.info(f"登录态已成功保存至 {config.storage_state_path}")
            
        except Exception as e:
            logger.warning(f"在等待登录或保存态时发生了超时（这通常是正常的，如果您已经手动关闭了）: {e}")
        finally:
            page.close()

    def upload_episode(self, episode: PodcastEpisode) -> bool:
        """自动化执行网页表单填报与上传流程"""
        if not episode.local_audio_path:
            logger.error("音频路径不存在，立刻停止上传。")
            return False
            
        page = self.context.new_page()
        try:
            # 步骤 1：进入初始的音频上传页面
            logger.info(f"正在前往音频上传页面: {config.target_upload_url}")
            page.goto(config.target_upload_url)
            page.wait_for_load_state("networkidle")
            
            logger.info(f"上传音频文件: {episode.local_audio_path.name}")
            page.locator(config.audio_upload_selector).set_input_files(str(episode.local_audio_path))
            
            # TODO: 有些平台音频在真正上传完之前是不让点击下一步的，这里可以额外判断特定类的显隐状态
            logger.info("等待音频读取/上传就绪 (保守设定等待 10 秒，可视平台自行修改)...")
            page.wait_for_timeout(10000)
            
            logger.info("点击【下一步】按钮...")
            page.locator(config.next_button_selector).click()
            
            # 步骤 2：进入信息编辑页面
            logger.info("等待进入信息编辑页面...")
            page.wait_for_load_state("networkidle")
            # 可选：等待标题输入框出现，确认页面已经切换成功
            # page.wait_for_selector(config.title_selector, state="visible")
            
            logger.info(f"填写标题: {episode.title}")
            page.locator(config.title_selector).fill(episode.title)
            
            logger.info("填写描述...")
            page.locator(config.desc_selector).fill(episode.description)
            
            if episode.local_cover_path:
                logger.info(f"上传封面文件: {episode.local_cover_path.name}")
                page.locator(config.cover_upload_selector).set_input_files(str(episode.local_cover_path))
                # 等待封面上传完毕
                page.wait_for_timeout(3000)
            
            logger.info("点击【提交/完成】发布按钮！")
            page.locator(config.submit_button_selector).click()
            
            # TODO: 判断成功的特征标识，比如等待“上传成功”元素的出现
            # page.wait_for_selector("text='Upload Successful'", timeout=120000)
            page.wait_for_timeout(5000) 
            
            logger.info("✅ 自动化分步上传流程顺利完成！")
            return True
            
        except Exception as e:
            logger.error(f"❌ 上传失败，遇到异常: {e}")
            # 如果处于 Headless=False 模式，可以在此断点，方便你在控制台看到浏览器到底卡在哪了
            return False
        finally:
            page.close()
