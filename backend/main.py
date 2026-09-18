from pathlib import Path
import uuid
import re
import time
import mimetypes
import json
import urllib.request
import urllib.parse

import yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
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


def expand_short_url(url: str) -> str:
    """Expand short URLs like vt.tiktok.com, vm.tiktok.com, youtu.be, etc."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.geturl()
    except Exception:
        return url


def extract_tiktok_fast(url: str):
    """
    Fast extraction for TikTok videos without watermark.
    Bypasses age restrictions, mature content filters, and login/cookies blocks!
    """
    try:
        api_url = "https://www.tikwm.com/api/"
        post_data = urllib.parse.urlencode({"url": url, "hd": 1}).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=post_data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("code") == 0 and "data" in data:
            d = data["data"]
            video_url = d.get("play") or d.get("wmplay")
            if not video_url:
                return None

            raw_title = d.get("title") or "TikTok Video"
            # Strip special characters for safe filenames
            clean_name = re.sub(r'[^\w\s-]', '', raw_title).strip()
            clean_name = re.sub(r'\s+', '_', clean_name)[:60] or "tiktok_video"

            author = d.get("author", {}).get("nickname") or "TikTok Creator"
            thumbnail = d.get("cover")
            duration = d.get("duration")
            music_url = d.get("music")

            encoded_video = urllib.parse.quote(video_url, safe="")
            download_url = f"/api/stream?url={encoded_video}&name={clean_name}.mp4&dl=1"
            preview_url = f"/api/stream?url={encoded_video}&name={clean_name}.mp4&dl=0"

            music_download_url = None
            if music_url:
                encoded_music = urllib.parse.quote(music_url, safe="")
                music_download_url = f"/api/stream?url={encoded_music}&name={clean_name}_audio.mp3&dl=1"

            return {
                "success": True,
                "filename": f"{clean_name}.mp4",
                "title": raw_title,
                "thumbnail": thumbnail,
                "duration": duration,
                "uploader": author,
                "preview_url": preview_url,
                "download_url": download_url,
                "music_url": music_download_url
            }
    except Exception:
        return None
    return None


class DownloadRequest(BaseModel):
    url: str


@app.post("/api/download")
def download_video(request: DownloadRequest):
    cleanup_old_files()

    url = request.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL. Please provide a full link starting with http:// or https://")

    # 1. Expand shortened links (e.g. vt.tiktok.com, vm.tiktok.com, youtu.be)
    expanded_url = expand_short_url(url)

    # 2. Ultra-fast TikTok engine with zero-watermark and bypass of age/login blocks
    if "tiktok.com" in expanded_url.lower() or "tiktok.com" in url.lower():
        tiktok_res = extract_tiktok_fast(expanded_url)
        if not tiktok_res and expanded_url != url:
            tiktok_res = extract_tiktok_fast(url)
        if tiktok_res:
            return tiktok_res

    # 3. Universal engine (YouTube, Instagram, Facebook, Twitter/X, Snapchat, etc.) via optimized yt-dlp
    job_id = uuid.uuid4().hex

    options = {
        "outtmpl": str(DOWNLOAD_DIR / f"{job_id}.%(ext)s"),
        # Prefer ready MP4 or pre-merged stream first for lightning-fast download without CPU heavy muxing
        "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "concurrent_fragment_downloads": 4,
        "buffersize": 1024 * 64,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
                "skip": ["hls"]
            },
            "tiktok": {
                "app_version": "34.1.2"
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "extractor_retries": 2,
        "file_access_retries": 2,
        "fragment_retries": 2,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(expanded_url, download=True)
            if not info:
                raise RuntimeError("Could not retrieve media information from the provided link.")

        candidates = [
            f for f in DOWNLOAD_DIR.glob(f"{job_id}.*")
            if not f.name.endswith((".part", ".ytdl", ".temp", ".aria2"))
        ]

        if not candidates:
            raise RuntimeError("Downloaded media file was not found on the server.")

        mp4_candidates = [f for f in candidates if f.suffix.lower() == ".mp4"]
        target_file = mp4_candidates[0] if mp4_candidates else candidates[0]

        raw_title = info.get("title") or "Downloaded Media"
        clean_name = re.sub(r'[^\w\s-]', '', raw_title).strip()
        clean_name = re.sub(r'\s+', '_', clean_name)[:60] or "downloaded_video"

        thumbnail = info.get("thumbnail")
        duration = info.get("duration")
        uploader = info.get("uploader") or info.get("channel") or info.get("extractor_key") or "Social Media"

        quoted_name = urllib.parse.quote(clean_name + target_file.suffix)
        return {
            "success": True,
            "filename": f"{clean_name}{target_file.suffix}",
            "title": raw_title,
            "thumbnail": thumbnail,
            "duration": duration,
            "uploader": uploader,
            "preview_url": f"/api/file/{target_file.name}?name={quoted_name}&dl=0",
            "download_url": f"/api/file/{target_file.name}?name={quoted_name}&dl=1"
        }

    except Exception as exc:
        raw_msg = str(exc)
        clean_msg = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw_msg).strip()

        if "Requested format is not available" in clean_msg:
            clean_msg = "Could not find a downloadable format for this link."
        elif "Sign in to confirm you're not a bot" in clean_msg:
            clean_msg = "The platform is temporarily limiting requests. Please try another video or wait 1 minute."
        elif "Private video" in clean_msg:
            clean_msg = "This video is private or restricted by the creator."
        elif "Video unavailable" in clean_msg:
            clean_msg = "This video is unavailable or has been removed."
        elif "This post may not be comfortable" in clean_msg or "Log in for access" in clean_msg:
            clean_msg = "This post is age-restricted or restricted by the platform."

        raise HTTPException(status_code=400, detail=clean_msg[:300])


@app.get("/api/stream")
def stream_media(request: Request, url: str, name: str = "video.mp4", dl: int = 1):
    """High-speed real-time streaming endpoint for direct CDN downloads and video preview."""
    try:
        decoded_url = urllib.parse.unquote(url)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.tiktok.com/"
        }

        client_range = request.headers.get("range")
        if client_range:
            headers["Range"] = client_range

        req = urllib.request.Request(decoded_url, headers=headers)
        remote_resp = urllib.request.urlopen(req, timeout=30)

        clean_name = re.sub(r'[^\w\s.-]', '_', urllib.parse.unquote(name)).strip()
        if not clean_name:
            clean_name = "download.mp4"

        mime_type, _ = mimetypes.guess_type(clean_name)
        if not mime_type:
            mime_type = "video/mp4"

        disposition = "attachment" if int(dl) == 1 else "inline"

        def iter_stream():
            try:
                while True:
                    chunk = remote_resp.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                remote_resp.close()

        status_code = remote_resp.status if remote_resp.status in (200, 206) else 200

        response_headers = {
            "Content-Disposition": f'{disposition}; filename="{clean_name}"',
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*"
        }
        for hdr in ("Content-Length", "Content-Range", "Content-Type"):
            if hdr in remote_resp.headers:
                response_headers[hdr] = remote_resp.headers[hdr]

        if "Content-Type" not in response_headers:
            response_headers["Content-Type"] = mime_type

        return StreamingResponse(
            iter_stream(),
            status_code=status_code,
            media_type=response_headers.get("Content-Type", mime_type),
            headers=response_headers
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Streaming error: {str(exc)[:150]}")


@app.api_route("/api/file/{filename}", methods=["GET", "HEAD"])
def get_file(filename: str, name: str = None, dl: int = 1):
    safe_name = Path(filename).name
    path = DOWNLOAD_DIR / safe_name

    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired.")

    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "video/mp4"

    out_name = urllib.parse.unquote(name) if name else safe_name
    clean_name = re.sub(r'[^\w\s.-]', '_', out_name).strip()

    disposition = "attachment" if int(dl) == 1 else "inline"

    return FileResponse(
        path,
        media_type=mime_type,
        filename=clean_name,
        headers={
            "Content-Disposition": f'{disposition}; filename="{clean_name}"',
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*"
        }
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


@app.get("/{page}.html")
def serve_html_page(page: str):
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', page)
    target_file = PROJECT_ROOT / f"{safe_name}.html"
    if target_file.exists():
        return FileResponse(target_file, media_type="text/html")
    raise HTTPException(status_code=404, detail=f"{page}.html not found")

