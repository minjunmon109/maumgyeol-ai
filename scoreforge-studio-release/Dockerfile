FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/mpl NUMBA_CACHE_DIR=/tmp/numba USER_DATA_DIR=/app/data HOME=/tmp SCOREFORGE_LOW_MEMORY=1 MAX_UPLOAD_MB=25 MAX_DURATION_SECONDS=180 MAX_RUNNING_JOBS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 xz-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY source.b64 /tmp/source.b64
COPY patch_build.py /app/patch_build.py
RUN base64 -d /tmp/source.b64 | tar -xJ -C /app && rm -f /tmp/source.b64 && python patch_build.py && python -m pip install --no-cache-dir -r requirements-web.txt
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin scoreforge && mkdir -p /app/data && chown -R scoreforge:scoreforge /app
USER scoreforge
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers"]
