FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --uid 1000 --create-home --shell /bin/bash docs

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Per-build secrets and flags (see gen_secrets.py). The app code is owned by
# root and read-only to the app user; only the search cache is writable.
RUN python gen_secrets.py /opt/lab / \
 && rm gen_secrets.py \
 && mkdir -p /app/static/cache \
 && chown -R root:root /app \
 && chown docs:docs /app/static/cache \
 && chmod -R a+rX /app

USER docs
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", \
     "--access-logfile", "-", "app:app"]
