FROM python:3.13.18-slim-bookworm

# Print Python output right away and skip writing .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /code

# Install packages first, so Docker can reuse this layer when only code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app into the image, so a fresh clone runs even without the
# development mount in docker-compose.yml.
COPY app ./app

EXPOSE 8000

# --reload restarts gunicorn when a file under app/ changes. With the
# ./app mount in docker-compose.yml, edits show up without a rebuild.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--reload", "app:create_app()"]
