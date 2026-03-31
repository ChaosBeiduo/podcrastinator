# Podcrastinator

Recently I fell in love with [Made by Google Podcast](https://www.youtube.com/playlist?list=PL590L5WQmH8d8QFM4FvihXlU2EBtjdZIp).

I like listening while walking.  
I like transcripts.  
I like being able to tap a sentence and jump back to that exact moment.

What I do not like is manually downloading, sorting, and uploading podcast episodes one by one.

So I made Podcrastinator — a tiny tool that helps me upload one episode at a time, slowly, and listen at my own pace.

---

## 🌟 What it does

Podcrastinator has evolved into a local Web Console built to track, manage, download, and automatically transport RSS podcast episodes into private web platforms that lack public APIs.

- **Manage Subscriptions**: Add and track multiple RSS feeds from a single console.
- **Download Media Locally**: Fetch MP3 files and cover images reliably into a neatly organized folder structure.
- **Automated Web Uploading**: Leverages browser automation (Playwright) to emulate human actions—filling titles, expanding panels, waiting for dynamic uploads, and checking boxes.
- **Track Progress**: A persistent async state machine tracks every episode visually (`Pending`, `Downloading`, `Uploaded`, etc.).

## 🏗 Tech Stack
- **Backend**: FastAPI (Python 3) handling background async tasks.
- **Frontend**: Jinja2 Templates, HTMX (for fast, reactive UI interactions without writing JS), and Pico CSS (for a pure, clean, native-feeling UI).
- **Automation**: Playwright (Python).
- **Storage**: Directory & JSON-based tracking (`metadata.json`). Highly transparent and portable.

## 🚀 Setup & Running

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure Platform Selectors**
   Copy `.env.example` to `.env` and map the CSS selectors corresponding to the upload form of your target platform.

3. **Start the Web Console**
   ```bash
   python app.py
   ```
   Open `http://127.0.0.1:8000` in your browser. Add your first podcast channel, sync the latest feed, and hit "Download" or "Upload" to watch the magic happen!

## 📂 Data Structure
Locally downloaded episodes are kept meticulously clean:
```text
data/
└── podcasts/
    └── [podcast_id]/
        └── episodes/
            └── [episode_id]/
                ├── metadata.json     # The source of truth state tracker
                ├── description.txt
                ├── cover.jpg
                └── media.mp3
```