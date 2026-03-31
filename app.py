import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse

from core.storage import StorageManager
from core.models import PodcastConfig, DownloadStatus, UploadStatus
from services.fetcher import PodcastFetcherService
from services.uploader import PodcastUploaderService
from config import config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # App startup logic: 自动载入旧系统的配置信息
    podcasts = StorageManager.load_all_podcasts()
    if not podcasts and config.podcast_rss_url:
        StorageManager.save_podcast(PodcastConfig(
            id="default_podcast",
            title="主频道同步器 (Default)",
            rss_url=config.podcast_rss_url,
            target_upload_url=config.target_upload_url
        ))
    yield

app = FastAPI(lifespan=lifespan)

# 如果本地想存放静态封面可启用这个，不过这次 MVP 暂直接渲染
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    podcasts = StorageManager.load_all_podcasts()
    
    stats = []
    for p in podcasts:
        eps = StorageManager.get_all_episodes(p.id)
        downloaded = sum(1 for e in eps if e.download_status == DownloadStatus.DOWNLOADED)
        uploaded = sum(1 for e in eps if e.upload_status == UploadStatus.UPLOADED)
        stats.append({
            "podcast": p,
            "total_eps": len(eps),
            "downloaded": downloaded,
            "uploaded": uploaded
        })
        
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"stats": stats}
    )

@app.get("/podcast/{podcast_id}", response_class=HTMLResponse)
async def podcast_detail(request: Request, podcast_id: str):
    podcast = StorageManager.get_podcast(podcast_id)
    if not podcast:
        return RedirectResponse("/")
        
    eps = StorageManager.get_all_episodes(podcast_id)
    return templates.TemplateResponse(
        request=request, 
        name="podcast.html", 
        context={"podcast": podcast, "episodes": eps}
    )

@app.post("/api/podcast/{podcast_id}/sync")
async def sync_podcast(podcast_id: str):
    podcast = StorageManager.get_podcast(podcast_id)
    if podcast:
        # NOTE: 只要没有 download 那么 parse 非常快，不需要 bg tasks
        PodcastFetcherService.sync_episodes(podcast)
        
    return HTMLResponse(
        "<div class='badge success'>✅ 成功解析数据！请按 F5 刷新网页显示最新。</div>"
    )

@app.post("/api/podcast/{podcast_id}/episodes/{episode_id}/download")
async def trigger_download(podcast_id: str, episode_id: str, background_tasks: BackgroundTasks, request: Request):
    meta = StorageManager.load_episode_metadata(podcast_id, episode_id)
    if not meta:
        return HTMLResponse("无法找到指定元数据", 404)
        
    # 丢后台异步执行，不卡网页 HTTP 请求
    background_tasks.add_task(PodcastFetcherService.download_episode, podcast_id, episode_id)
    
    # 将模型手动标记为 DOWNLOADING，并立即生成局部的 HTML HTMX 片段返回给浏览器顶替旧行
    # 在前端组件里该状态被识别后，会自动按照 hx-trigger 每 2 秒主动问我下面状态 API 轮询！
    meta.download_status = DownloadStatus.DOWNLOADING
    StorageManager.save_episode_metadata(podcast_id, meta)
    
    return templates.TemplateResponse(
        request=request, 
        name="components/episode_row.html", 
        context={"podcast": StorageManager.get_podcast(podcast_id), "ep": meta}
    )

@app.post("/api/podcast/{podcast_id}/episodes/{episode_id}/upload")
async def trigger_upload(podcast_id: str, episode_id: str, background_tasks: BackgroundTasks, request: Request):
    meta = StorageManager.load_episode_metadata(podcast_id, episode_id)
    if not meta:
        return HTMLResponse("不可定位模型元数据", 404)
        
    # 将 Playwright 唤起交给 fastapi 核心协程库的纯异步队列中，免得它挂起打断其他按钮响应
    background_tasks.add_task(PodcastUploaderService.upload_episode, podcast_id, episode_id)
    
    meta.upload_status = UploadStatus.UPLOADING
    meta.upload_error = None
    StorageManager.save_episode_metadata(podcast_id, meta)
    
    return templates.TemplateResponse(
        request=request, 
        name="components/episode_row.html", 
        context={"podcast": StorageManager.get_podcast(podcast_id), "ep": meta}
    )

# 被 HTMX 被动每隔几秒轮询使用的接口，一旦上面的 task 在幕后结束写了盘，这里扫到变化就会吐出最终的静态 html 按钮，并终止自己
@app.get("/api/podcast/{podcast_id}/episodes/{episode_id}/status")
async def episode_status(request: Request, podcast_id: str, episode_id: str):
    meta = StorageManager.load_episode_metadata(podcast_id, episode_id)
    return templates.TemplateResponse(
        request=request, 
        name="components/episode_row.html", 
        context={"podcast": StorageManager.get_podcast(podcast_id), "ep": meta}
    )

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
