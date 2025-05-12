# LCD Storage

A Raspberry Pi–friendly utility that displays filesystem usage on a 16×2 I2C LCD and optionally scales a Kubernetes Deployment running on the same node via an on/off button.

Continuously polls:

- **Kubernetes**: checks a Deployment’s replica count on the local node and scales it to 0 or 1 via a button
- **Storage**: when the Deployment is active, shows used/total storage for a given path

## Features

- 📟 **16×2 I2C LCD Support** — Display one or two lines, with automatic trimming and clear warnings
- 🔘 **On/Off Button** — GPIO-driven scaling: press to start your agent Deployment, release to stop
- **📊 Storage Monitoring** — Shows used vs. total bytes in human-readable format
- **☸️ Kubernetes Integration** — Targets a specific Deployment (by prefix) on the local node
- **🛠 Easy CLI** — Fully configurable via command-line flags

## Requirements

- Python 3.7+
- Linux SBC with I2C support (e.g. Raspberry Pi)
- I²C LCD (16×2) wired to your board’s I²C bus
- GPIO pin for on/off button (pull-up wiring)
- (Optional) Kubernetes cluster when using the scaling feature
- Root privileges (for I²C and GPIO access)

## How to install

```bash
pip install -e .
```

## Usage

```bash
sudo lcd-storage [OPTIONS] [--path PATH]
```

| Option               | Description                                    | Default     |
| -------------------- | ---------------------------------------------- | ----------- |
| `--path`             | Filesystem path to check                       | `/`         |
| `--namespace`, `-n`  | Kubernetes namespace containing the Deployment | `neonswarm` |
| `--prefix`, `-p`     | Deployment name prefix                         | `agent`     |
| `--address`, `-a`    | I²C address of the LCD (in hex or decimal)     | `0x27`      |
| `--interval`, `-i`   | Seconds between updates                        | `10.0`      |
| `--button-pin`, `-b` | GPIO pin number for on/off button              | `17`        |
| `--verbose`, `-v`    | Enable debug-level logging                     | Off         |

## Example

Display `/mnt/data`, verbose logging, polling every 5 seconds:

```bash
sudo lcd-storage --path /mnt/data -i 5.0 -v
```

This will:

- Read deployment agent* in namespace neonswarm on this node
- On button press: scale up to 1 replica; on release: scale down to 0
- When active, show:

    ```
    Storage
    12.3G/64.0G
    ```

## Docker

You can use Docker for a clean runtime environment on your SBC.

### Build the Image

```bash
sudo docker build -t lcd-storage \
  -f storage-node/lcd_storage/Dockerfile .
```

### Run the Container

```bash
sudo docker run --rm \
  --privileged \
  --device /dev/i2c-1 \
  --device /dev/gpiochip0 \
  lcd-storage \
  --path "/" --interval 10.0 --verbose
```

### Notes

- `--privileged` grants GPIO/I²C access.
- Device flags (`--device /dev/i2c-1, /dev/gpiochip0`) let the container talk to hardware.
- Use `--namespace` and `--prefix` to enable or disable Kubernetes scaling.

## Hardware Setup

1. LCD
    - SDA → board SDA (e.g. GPIO 2)
    - SCL → board SCL (e.g. GPIO 3)
    - VCC → 5 V, GND → GND
2. Button
    - One leg → configured GPIO pin (default 17)
    - Other leg → GND (use pull-up)
3. GPIO Zero Backend
    - Uses LGPIO; ensure liblgpio and device tree overlays are enabled.
