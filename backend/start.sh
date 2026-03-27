#!/bin/bash
# Backend startup script

# Check FFmpeg availability (don't try apt-get - use static-ffmpeg pip package instead)
if command -v ffmpeg &> /dev/null; then
    echo "[STARTUP] FFmpeg available: $(which ffmpeg)"
else
    echo "[STARTUP] System FFmpeg not found - will use static-ffmpeg pip package"
fi

# Start uvicorn
exec /root/.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
