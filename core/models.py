import enum
from typing import Optional
from pydantic import BaseModel

class DownloadStatus(str, enum.Enum):
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    DOWNLOAD_FAILED = "download_failed"

class UploadStatus(str, enum.Enum):
    NOT_UPLOADED = "not_uploaded"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    UPLOAD_FAILED = "upload_failed"

class EpisodeMetadata(BaseModel):
    id: str  # 唯一标识符，通常是 RSS guid
    title: str
    published_at: str
    audio_url: str
    cover_url: Optional[str] = None
    description_html: str = ""
    description_text: str = ""
    
    # 跟踪状态机
    download_status: DownloadStatus = DownloadStatus.NOT_DOWNLOADED
    upload_status: UploadStatus = UploadStatus.NOT_UPLOADED
    
    # 追溯时间节点
    downloaded_at: Optional[str] = None
    uploaded_at: Optional[str] = None
    upload_error: Optional[str] = None
    
    # 本地相对文件路径（相对于当前 metadata.json 的目录）
    local_audio_file: Optional[str] = None
    local_cover_file: Optional[str] = None
    local_description_file: str = "description.txt"

class PodcastConfig(BaseModel):
    id: str
    title: str
    rss_url: str
    target_upload_url: str
