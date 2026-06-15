FROM python:3.12-slim

# faster-whisper decodes audio via PyAV (bundles ffmpeg), so no system ffmpeg needed.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Model cache lives in a mounted volume; CPU threading tuned for Ryzen 7 8840U.
ENV HF_HOME=/cache \
    OMP_NUM_THREADS=8 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"

CMD ["python", "-m", "uvicorn", "main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
