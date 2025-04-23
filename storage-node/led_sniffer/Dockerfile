FROM python:3.11-slim

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential \
      libpcap-dev \
      i2c-tools \
      libgpiod2 \
      python3-smbus \
      python3-rpi.gpio \
 && pip install --upgrade pip setuptools wheel \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/libs
COPY libs/pyproject.toml    /app/libs/pyproject.toml
COPY libs/src               /app/libs/src
RUN pip install --no-cache-dir -e .

WORKDIR /app/led_sniffer
COPY storage-node/led_sniffer/pyproject.toml  /app/led_sniffer/pyproject.toml
COPY storage-node/led_sniffer/src            /app/led_sniffer/src
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["led-sniffer"]
CMD []
