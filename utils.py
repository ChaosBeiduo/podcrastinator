import re
import logging
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

# 配置基础日志记录
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("podcrastinator")

@dataclass
class PodcastEpisode:
    """定义播客数据结构"""
    id: str
    title: str
    description: str
    audio_url: str
    cover_url: Optional[str]
    published_date: str
    
    # 下载后保存到本地的路径
    local_audio_path: Optional[Path] = None
    local_cover_path: Optional[Path] = None

def clean_description(html_text: str, max_length: int = 1000) -> str:
    """清理 HTML 标签并处理为纯文本，保留基本换行"""
    if not html_text:
        return ""
    
    # 将段落和换行标签替换为换行符
    html_text = re.sub(r'</p>|<br\s*/?>|</div>', '\n', html_text, flags=re.IGNORECASE)
    
    # 使用 BeautifulSoup 去除剩余的 HTML 标签
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text()
    
    # 处理过多空行
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    
    # 截断长度
    if len(text) > max_length:
        text = text[:max_length] + "..."
        
    return text
