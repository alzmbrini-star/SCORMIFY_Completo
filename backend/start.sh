#!/bin/bash
# Backend startup script - ensures FFmpeg is available before starting uvicorn

# Install FFmpeg if not present
if ! command -v ffmpeg &> /dev/null; then
    echo "[STARTUP] FFmpeg not found, installing..."
    apt-get update -qq && apt-get install -y -qq ffmpeg 2>&1 | tail -2
    echo "[STARTUP] FFmpeg installed: $(which ffmpeg)"
else
    echo "[STARTUP] FFmpeg already available: $(which ffmpeg)"
fi

# Start uvicorn
exec /root/.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
