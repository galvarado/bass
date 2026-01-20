FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ✅ Asegura el directorio de logs (aunque luego lo montes como volumen)
RUN mkdir -p /app/logs

# ✅ Gunicorn: access + error a stdout/stderr para docker logs
CMD ["bash", "-lc", "\
  python manage.py migrate && \
  python manage.py collectstatic --noinput && \
  gunicorn core.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
"]
