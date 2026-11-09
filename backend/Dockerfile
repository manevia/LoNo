FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# ffmpeg relays live broadcasts to social destinations and assembles recordings
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m lono && mkdir -p /app/data/uploads /app/data/recordings && chown -R lono /app/data
USER lono
EXPOSE 8001
# Single process: live relays and the media monitor run in this process. Proxy headers are
# trusted from any address because the API is only reachable inside the Docker network.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips", "*"]
