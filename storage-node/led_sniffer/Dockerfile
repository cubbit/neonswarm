# syntax=docker/dockerfile:1
FROM python:3.11-slim

# ── Install system deps for Scapy & build tools ────────────────────────────────
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential libpcap-dev \
 && pip install --upgrade pip setuptools wheel \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Copy & install your shared utils lib ──────────────────────────────────────
COPY libs /app/libs
RUN pip install --no-cache-dir -e libs

# ── Copy & install the led_sniffer service ────────────────────────────────────
COPY storage-node/led_sniffer /app/storage-node/led_sniffer
WORKDIR /app/storage-node/led_sniffer
RUN pip install --no-cache-dir -e .

# ── Final entrypoint ───────────────────────────────────────────────────────────
# 
# Now that pip has installed led-sniffer, the 'led-sniffer' script will
# live in /usr/local/bin and be on $PATH.
ENTRYPOINT ["/bin/bash"]
CMD []
