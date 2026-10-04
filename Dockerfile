FROM python:3.10-slim

# Install ffmpeg for video/audio merging and nodejs for yt-dlp JS player deciphering
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg nodejs \
    && (command -v node >/dev/null 2>&1 || ln -s /usr/bin/nodejs /usr/bin/node) \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies with latest yt-dlp
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy backend code
COPY backend/ backend/

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
