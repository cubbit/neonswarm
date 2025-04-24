FROM python:3.11-slim

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential \
      libpcap-dev \
      i2c-tools \
      libgpiod2 \
      python3-smbus \
      python3-smbus2 \
      python3-rpi.gpio \
 && pip install --upgrade pip setuptools wheel \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/libs
COPY libs/pyproject.toml    /app/libs/pyproject.toml
COPY libs/src               /app/libs/src
RUN pip install --no-cache-dir -e .

WORKDIR /app/lcd_storage
COPY storage-node/lcd_storage/pyproject.toml  /app/lcd_storage/pyproject.toml
COPY storage-node/lcd_storage/src            /app/lcd_storage/src
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["lcd-storage"]
CMD []
