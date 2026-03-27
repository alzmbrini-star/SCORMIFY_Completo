#!/bin/bash
# Backend startup script

# Check FFmpeg availability (use static-ffmpeg pip package as fallback)
if command -v ffmpeg &> /dev/null; then
    echo "[STARTUP] FFmpeg available: $(which ffmpeg)"
else
    echo "[STARTUP] System FFmpeg not found - will use static-ffmpeg pip package"
fi

# Start uvicorn with extended timeout-keep-alive to prevent K8s Ingress 502 during video export
exec /root/.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1 --timeout-keep-alive 300
