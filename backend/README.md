# Backend

## Install

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

## Start

### Quick Start (Windows):
Simply double-click `start.bat` in the root folder, which starts the server and opens `http://localhost:8000` automatically!

### Manual Start:
```bash
# Windows
venv\Scripts\activate
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Now open in your browser:
**http://localhost:8000**

(Frontend and backend are served together seamlessly, and CORS is also enabled for any local port like 5500 or direct file view).

## Production

For a real public service, add:
- HTTPS
- rate limiting
- file-size limits
- automatic deletion/cleanup of downloaded files
- domain/origin restrictions
- authentication if needed
- queue/background workers
- platform/terms compliance
- proper CORS configuration
- storage such as S3 instead of local disk
