import os
import shutil
import uuid
import re
import time
import mimetypes
import json
import sys
import threading
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

# Ensure pytubefix uses working system node if wheel node is missing or non-executable
try:
    import pytubefix.botGuard.bot_guard as bg
    if not (os.path.exists(bg.NODE_PATH) and os.access(bg.NODE_PATH, os.X_OK)):
        sys_node = shutil.which("node") or shutil.which("nodejs") or "/usr/bin/node"
        if sys_node and os.path.exists(sys_node):
            bg.NODE_PATH = sys_node
except Exception:
    pass

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
COOKIES_FILE = BACKEND_DIR / "cookies.txt"


def background_upgrade_ytdlp():
    """Ensure yt-dlp and pytubefix stay on the latest release to seamlessly handle platform/API updates."""
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--upgrade", "yt-dlp", "pytubefix"],
            timeout=120,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


@app.on_event("startup")
def on_startup():
    threading.Thread(target=background_upgrade_ytdlp, daemon=True).start()


def has_valid_cookies() -> bool:
    """Check if cookies.txt exists and contains actual authenticated user session tokens."""
    if not COOKIES_FILE.exists() or COOKIES_FILE.stat().st_size < 50:
        return False
    try:
        content = COOKIES_FILE.read_text(encoding="utf-8", errors="ignore")
        return any(k in content for k in ("LOGIN_INFO", "SAPISID", "SID", "SSID", "__Secure-3PAPISID"))
    except Exception:
        return False


@app.get("/api/health")
def api_health():
    return {
        "status": "online",
        "version": "2.3.0-pytubefix",
        "ytdlp_version": getattr(yt_dlp.version, "__version__", "unknown"),
        "has_cookies": has_valid_cookies(),
        "time": time.time(),
    }


@app.get("/api/debug_yt")
def debug_yt(url: str = "https://youtu.be/3j7bhOvW6jw"):
    log = []
    log.append(f"sys.executable: {sys.executable}")
    log.append(f"shutil.which('node'): {shutil.which('node')}")
    log.append(f"shutil.which('ffmpeg'): {shutil.which('ffmpeg')}")
    try:
        import pytubefix
        log.append(f"pytubefix version: {getattr(pytubefix, '__version__', 'unknown')}")
        import pytubefix.botGuard.bot_guard as bg
        log.append(f"bg.NODE_PATH: {bg.NODE_PATH} exists={os.path.exists(bg.NODE_PATH)}")
        try:
            token = bg.generate_po_token("3j7bhOvW6jw")
            log.append(f"token: {token[:25]}... (len={len(token)})")
        except Exception as te:
            log.append(f"generate_po_token error: {te}")
    except Exception as pe:
        log.append(f"pytubefix import error: {pe}")

    for client in ["WEB", "ANDROID"]:
        try:
            from pytubefix import YouTube
            yt = YouTube(url, client=client)
            log.append(f"client {client} title: {yt.title}")
            v = yt.streams.filter(type="video", file_extension="mp4").order_by("resolution").desc().first()
            log.append(f"client {client} best video stream: {v}")
        except Exception as ce:
            log.append(f"client {client} error: {ce}")

    return {"log": log}


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


def is_youtube_url(url: str) -> bool:
    low = url.lower()
    return "youtube.com" in low or "youtu.be" in low


def normalize_youtube_url(url: str) -> str:
    """Normalize YouTube links (shorts, youtu.be, mobile, live, music) into standard watch URLs, stripping extraneous query params."""
    m = re.search(r'(?:youtu\.be/|(?:[a-zA-Z0-9_-]+\.)?youtube\.com/(?:watch\?.*?v=|embed/|v/|shorts/|live/))([a-zA-Z0-9_-]{11})', url)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    return url


def expand_short_url(url: str) -> str:
    """Expand short URLs like vt.tiktok.com, vm.tiktok.com, youtu.be, etc."""
    if is_youtube_url(url):
        return normalize_youtube_url(url)
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


def extract_youtube_pytube(url: str, job_id: str):
    """
    Primary YouTube extraction engine using pytubefix.
    Automatically generates PO (Proof of Origin) tokens via Node.js
    and bypasses SABR ad gates and bot checks completely on datacenter IPs.
    """
    for client in ["WEB", "ANDROID"]:
        try:
            from pytubefix import YouTube
            yt = YouTube(url, client=client)
            raw_title = yt.title or "YouTube Video"
            thumbnail = yt.thumbnail_url
            duration = yt.length
            uploader = yt.author or "YouTube Creator"
            target_file = DOWNLOAD_DIR / f"{job_id}.mp4"

            # Prefer 720p or 1080p MP4 adaptive stream merged with AAC audio for crisp HD quality
            v = (
                yt.streams.filter(type="video", file_extension="mp4", res="720p").first()
                or yt.streams.filter(type="video", file_extension="mp4", res="1080p").first()
                or yt.streams.filter(type="video", file_extension="mp4").order_by("resolution").desc().first()
                or yt.streams.filter(type="video").order_by("resolution").desc().first()
            )
            a = yt.streams.get_audio_only()

            if v and a:
                v_tmp = DOWNLOAD_DIR / f"{job_id}_v.mp4"
                a_tmp = DOWNLOAD_DIR / f"{job_id}_a.mp4"
                v.download(output_path=str(DOWNLOAD_DIR), filename=f"{job_id}_v.mp4")
                a.download(output_path=str(DOWNLOAD_DIR), filename=f"{job_id}_a.mp4")

                try:
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(v_tmp),
                        "-i", str(a_tmp),
                        "-c:v", "copy",
                        "-c:a", "copy",
                        str(target_file)
                    ]
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(v_tmp),
                        "-i", str(a_tmp),
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        "-preset", "veryfast",
                        str(target_file)
                    ]
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                finally:
                    for tmp in (v_tmp, a_tmp):
                        try:
                            tmp.unlink()
                        except Exception:
                            pass
            elif v:
                v_tmp = DOWNLOAD_DIR / f"{job_id}_v.mp4"
                v.download(output_path=str(DOWNLOAD_DIR), filename=f"{job_id}_v.mp4")
                v_tmp.rename(target_file)
            else:
                prog = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc().first()
                if prog:
                    prog.download(output_path=str(DOWNLOAD_DIR), filename=f"{job_id}.mp4")

            if target_file.exists() and target_file.stat().st_size > 5000:
                clean_name = re.sub(r'[^\w\s-]', '', raw_title).strip()
                clean_name = re.sub(r'\s+', '_', clean_name)[:60] or "youtube_video"
                quoted_name = urllib.parse.quote(f"{clean_name}.mp4")
                return {
                    "success": True,
                    "filename": f"{clean_name}.mp4",
                    "title": raw_title,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "uploader": uploader,
                    "preview_url": f"/api/file/{target_file.name}?name={quoted_name}&dl=0",
                    "download_url": f"/api/file/{target_file.name}?name={quoted_name}&dl=1"
                }
        except Exception as exc:
            print(f"[pytubefix] client={client} error: {exc}", flush=True)
            for f in DOWNLOAD_DIR.glob(f"{job_id}*"):
                try:
                    f.unlink()
                except Exception:
                    pass
            continue

    return None


class DownloadRequest(BaseModel):
    url: str


@app.post("/api/download")
def download_video(request: DownloadRequest):
    cleanup_old_files()

    url = request.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL. Please provide a full link starting with http:// or https://")

    # 1. URL detection & expansion
    is_yt = is_youtube_url(url)
    if is_yt:
        expanded_url = normalize_youtube_url(url)
    else:
        expanded_url = expand_short_url(url)
        if is_youtube_url(expanded_url):
            is_yt = True
            expanded_url = normalize_youtube_url(expanded_url)

    # 2. Ultra-fast TikTok engine with zero-watermark and bypass of age/login blocks
    if not is_yt and ("tiktok.com" in expanded_url.lower() or "tiktok.com" in url.lower()):
        tiktok_res = extract_tiktok_fast(expanded_url)
        if not tiktok_res and expanded_url != url:
            tiktok_res = extract_tiktok_fast(url)
        if tiktok_res:
            return tiktok_res

    # 3. Universal engine with YouTube multi-tiered client fallbacks
    job_id = uuid.uuid4().hex

    if is_yt:
        # Step 3a: Primary PyTubeFix engine with automated PO-tokens & SABR bypass
        yt_res = extract_youtube_pytube(expanded_url, job_id)
        if not yt_res and expanded_url != url:
            yt_res = extract_youtube_pytube(url, job_id)
        if yt_res:
            return yt_res

        # Step 3b: Multi-strategy yt-dlp fallback (visionos, android, android_vr)
        yt_strategies = [
            {"player_client": ["visionos"]},
            {"player_client": ["android"]},
            {"player_client": ["android_vr"]},
            {"player_client": ["visionos", "android"]},
        ]
        if has_valid_cookies():
            yt_strategies.insert(0, None)

        info = None
        last_error = None

        for strategy in yt_strategies:
            yt_opts = {
                "outtmpl": str(DOWNLOAD_DIR / f"{job_id}.%(ext)s"),
                "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/18/bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
                "concurrent_fragment_downloads": 4,
                "buffersize": 1024 * 64,
                "extractor_retries": 3,
                "file_access_retries": 2,
                "fragment_retries": 2,
                "js_runtimes": {
                    "node": {},
                    "nodejs": {},
                    "deno": {},
                },
            }
            if strategy:
                yt_opts["extractor_args"] = {"youtube": strategy}
            if has_valid_cookies():
                yt_opts["cookiefile"] = str(COOKIES_FILE)

            try:
                with yt_dlp.YoutubeDL(yt_opts) as ydl:
                    info = ydl.extract_info(expanded_url, download=True)
                    if info:
                        break
            except Exception as exc:
                last_error = exc
                for f in DOWNLOAD_DIR.glob(f"{job_id}.*"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
                continue

        if not info:
            raw_msg = str(last_error or "Could not extract YouTube video.")
            clean_msg = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw_msg).strip()
            clean_msg_normalized = clean_msg.replace("’", "'").replace("“", '"').replace("”", '"').lower()
            if "private video" in clean_msg_normalized:
                clean_msg = "This YouTube video is private or restricted by the creator."
            elif "video unavailable" in clean_msg_normalized:
                clean_msg = "This YouTube video is unavailable or has been removed."
            elif "not a bot" in clean_msg_normalized or "sign in to confirm" in clean_msg_normalized or "failed to extract any player response" in clean_msg_normalized:
                clean_msg = "YouTube temporarily limited this request. Please try again in a few moments."
            elif "requested format is not available" in clean_msg_normalized:
                clean_msg = "Could not find a downloadable format for this YouTube video."
            raise HTTPException(status_code=400, detail=clean_msg[:300])

    else:
        # Non-YouTube platforms (Instagram, Facebook, Twitter/X, Snapchat, etc.)
        options = {
            "outtmpl": str(DOWNLOAD_DIR / f"{job_id}.%(ext)s"),
            "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "concurrent_fragment_downloads": 4,
            "buffersize": 1024 * 64,
            "extractor_args": {
                "tiktok": {
                    "app_version": "34.1.2"
                }
            },
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            "extractor_retries": 3,
            "file_access_retries": 2,
            "fragment_retries": 2,
            "js_runtimes": {
                "node": {},
                "nodejs": {},
                "deno": {},
            },
        }
        if has_valid_cookies():
            options["cookiefile"] = str(COOKIES_FILE)


        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(expanded_url, download=True)
                if not info:
                    raise RuntimeError("Could not retrieve media information from the provided link.")
        except Exception as exc:
            raw_msg = str(exc)
            clean_msg = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw_msg).strip()
            clean_msg_normalized = clean_msg.replace("’", "'").replace("“", '"').replace("”", '"').lower()

            if "requested format is not available" in clean_msg_normalized:
                clean_msg = "Could not find a downloadable format for this link."
            elif "not a bot" in clean_msg_normalized or "sign in to confirm" in clean_msg_normalized:
                clean_msg = "The platform is temporarily limiting requests. Please try another video or wait 1 minute."
            elif "private video" in clean_msg_normalized:
                clean_msg = "This video is private or restricted by the creator."
            elif "video unavailable" in clean_msg_normalized:
                clean_msg = "This video is unavailable or has been removed."
            elif "this post may not be comfortable" in clean_msg_normalized or "log in for access" in clean_msg_normalized:
                clean_msg = "This post is age-restricted or restricted by the platform."

            raise HTTPException(status_code=400, detail=clean_msg[:300])

    candidates = [
        f for f in DOWNLOAD_DIR.glob(f"{job_id}.*")
        if not f.name.endswith((".part", ".ytdl", ".temp", ".aria2"))
    ]

    if not candidates:
        raise HTTPException(status_code=400, detail="Downloaded media file was not found on the server.")

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

