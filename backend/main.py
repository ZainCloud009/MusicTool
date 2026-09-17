from pathlib import Path
import uuid
import re
import time
import mimetypes

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Social Video Downloader API")

# Enable CORS for all origins to allow browser requests from any local or remote port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DOWNLOAD_DIR = BACKEND_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_old_files(max_age_seconds: int = 3600):
    """Automatically remove downloaded files older than 1 hour."""
    now = time.time()
    try:
        for item in DOWNLOAD_DIR.iterdir():
            if item.is_file() and (now - item.stat().st_mtime) > max_age_seconds:
                try:
                    item.unlink()
                except Exception:
                    pass
    except Exception:
        pass


class DownloadRequest(BaseModel):
    url: str


@app.post("/api/download")
def download_video(request: DownloadRequest):
    # Run a quick cleanup of files older than 1 hour
    cleanup_old_files()

    url = request.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL. Please provide a full link starting with http:// or https://")

    job_id = uuid.uuid4().hex

    # Options optimized for social media platforms (YouTube, Instagram, TikTok, Facebook, Twitter/X, etc.)
    options = {
        "outtmpl": str(DOWNLOAD_DIR / f"{job_id}.%(ext)s"),
        # Try MP4 video + M4A audio first, then any best video + audio (ffmpeg merges to MP4), then best single stream or audio
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "extractor_retries": 3,
        "file_access_retries": 3,
        "fragment_retries": 3,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("Could not retrieve video information from the provided link.")

        # Find the downloaded file matching this job_id
        candidates = [
            f for f in DOWNLOAD_DIR.glob(f"{job_id}.*")
            if not f.name.endswith((".part", ".ytdl", ".temp", ".aria2"))
        ]

        if not candidates:
            raise RuntimeError("Downloaded file was not found on the server.")

        # Prefer .mp4 file if available
        mp4_candidates = [f for f in candidates if f.suffix.lower() == ".mp4"]
        target_file = mp4_candidates[0] if mp4_candidates else candidates[0]

        title = info.get("title") or "Downloaded Video"
        thumbnail = info.get("thumbnail")
        duration = info.get("duration")
        uploader = info.get("uploader") or info.get("channel") or info.get("extractor_key") or "Social Media"

        return {
            "success": True,
            "filename": target_file.name,
            "title": title,
            "thumbnail": thumbnail,
            "duration": duration,
            "uploader": uploader,
            "download_url": f"/api/file/{target_file.name}"
        }

    except Exception as exc:
        raw_msg = str(exc)
        # Strip ANSI escape codes
        clean_msg = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw_msg).strip()

        # Provide friendly translations for common platform errors
        if "Requested format is not available" in clean_msg:
            clean_msg = "Could not find a downloadable video format for this link."
        elif "Sign in to confirm you're not a bot" in clean_msg:
            clean_msg = "The platform is blocking automated requests. Try again in a minute or try another video."
        elif "Private video" in clean_msg:
            clean_msg = "This video is private or restricted."
        elif "Video unavailable" in clean_msg:
            clean_msg = "This video is unavailable or has been removed."

        raise HTTPException(status_code=400, detail=clean_msg[:300])


@app.api_route("/api/file/{filename}", methods=["GET", "HEAD"])
def get_file(filename: str):
    # Prevent path traversal
    safe_name = Path(filename).name
    path = DOWNLOAD_DIR / safe_name

    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired.")

    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "video/mp4"

    return FileResponse(
        path,
        media_type=mime_type,
        filename=safe_name,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'}
    )


# Serve frontend directly from the root so users can open freemusicdownload.site or http://localhost:8000
@app.get("/CNAME")
def serve_cname():
    cname_file = PROJECT_ROOT / "CNAME"
    if cname_file.exists():
        return FileResponse(cname_file, media_type="text/plain")
    raise HTTPException(status_code=404, detail="CNAME not found")

@app.get("/")
def serve_index():
    index_file = PROJECT_ROOT / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="index.html not found")


@app.get("/app.js")
def serve_app_js():
    js_file = PROJECT_ROOT / "app.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")


@app.get("/style.css")
def serve_style_css():
    css_file = PROJECT_ROOT / "style.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")


@app.get("/robots.txt")
def serve_robots():
    robots_file = PROJECT_ROOT / "robots.txt"
    if robots_file.exists():
        return FileResponse(robots_file, media_type="text/plain")
    raise HTTPException(status_code=404, detail="robots.txt not found")


@app.get("/sitemap.xml")
def serve_sitemap():
    sitemap_file = PROJECT_ROOT / "sitemap.xml"
    if sitemap_file.exists():
        return FileResponse(sitemap_file, media_type="application/xml")
    raise HTTPException(status_code=404, detail="sitemap.xml not found")
