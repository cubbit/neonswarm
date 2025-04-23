# syntax=docker/dockerfile:1

# ──── Builder stage ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# install system deps for Scapy & build tools
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential libpcap-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# install Poetry
ENV POETRY_VERSION=2.0.1
RUN pip install --no-cache-dir poetry=="$POETRY_VERSION"

# Copy service pyproject and lock (if any)
COPY storage-node/led_sniffer storage-node/led_sniffer

# Copy local utils library
COPY libs ./libs

RUN pip install -e libs

RUN pip install -e storage-node/led_sniffer

ENTRYPOINT ["/bin/bash"]
CMD []
