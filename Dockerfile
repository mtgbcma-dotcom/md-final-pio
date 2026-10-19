FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
ENV SQLITE_DB_PATH=/data/db.sqlite3 MEDIA_ROOT=/media
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput && useradd --create-home app && mkdir -p /data /media && chown app:app /data /media
USER app
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && exec python manage.py runserver 0.0.0.0:8000 --noreload"]
