# audctl + Chromium for `audctl serve` (optional Docker path).
# Playback uses the browser inside this image; mount your real X11 + audctl state from the host.
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY pyproject.toml README.md LICENSE /src/
COPY src /src/src
RUN pip install --no-cache-dir /src

ENV AUDCTL_CHROMIUM_BINARY=/usr/bin/chromium
EXPOSE 8765

# 0.0.0.0 so other Docker containers can reach this via the host IP (e.g. host.docker.internal).
CMD ["audctl", "serve", "--host", "0.0.0.0", "--port", "8765"]
