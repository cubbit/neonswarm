# LED TCP Sniffer

A Python-based TCP packet sniffer that flashes a NeoPixel LED strip when a configurable amount of data is detected on a specified TCP port.
Listens for TCP packets on a given port (and optional host/interface), accumulates byte counts, and flashes a NeoPixel strip when a byte threshold is reached.
Ideal for visualizing network activity or for educational/demo purposes on devices like Raspberry Pi.

---

## Features

- 🕵️‍♂️ **TCP Sniffing** — Listens for TCP packets on a given port, with optional interface or IP filtering.
- 🔢 **Byte Threshold Trigger** — Triggers LED animation when a defined byte threshold is met.
- 🌈 **NeoPixel LED Notifications** — Visual wave animation to indicate network activity.
- ⏱ **Timeout Reset** — Resets counter after inactivity timeout.
- 🔧 **Configurable CLI** — Full customization via command-line arguments.

---

## Requirements

- Python 3.7+
- Raspberry Pi (or similar Linux board) with GPIO access
- [Adafruit NeoPixel](https://github.com/adafruit/Adafruit_CircuitPython_NeoPixel) LED strip
- Root privileges (for raw packet capture)

### Python Dependencies

Install required packages with:

```bash
pip install -e .
```

## Usage

```
sudo python3 led_sniffer.py [OPTIONS]
```

| Option                 | Description                                         | Default       |
| ---------------------- | --------------------------------------------------- | ------------- |
| `-p`, `--port`         | TCP port to monitor                                 | 4000          |
| `-s`, `--source`       | Source host IP to filter packets                    | None (any)    |
| `-i`, `--interface`    | Network interface to capture on                     | Default iface |
| `-t`, `--threshold`    | Byte threshold before LED trigger (e.g. `1K`, `2M`) | 1024 bytes    |
| `-d`, `--delay`        | Seconds of inactivity before resetting counter      | 3.0           |
| `--led-count`          | Number of LEDs in the strip                         | 30            |
| `--led-pin`            | GPIO pin name for NeoPixel data (e.g. `D18`)        | D18           |
| `--animation-color`    | Wave color as hex string (e.g. `#FF0000`, `00FF00`) | `#0065FF`     |
| `--animation-speed`    | Seconds per frame of the wave animation             | 0.09          |
| `--animation-spacing`  | Pixel spacing for the wave animation                | 3             |
| `--animation-duration` | Seconds to run the wave after threshold is hit      | 2.0           |
| `-v`, `--verbose`      | Enable debug logging                                | Off           |

## Example

```
sudo python3 led_sniffer.py -p 8080 -t 2K --animation-color "#00FF00" --led-count 20
```

This will:

- Monitor TCP port 8080
- Flash green LEDs when 2KB of data is received
- Use 20 LEDs on the strip

## Docker

You can run the LED TCP Sniffer inside a Docker container. This is especially useful for deploying on Raspberry Pi or other edge devices in a clean, isolated environment.

### Build the Image

```bash
sudo docker build -t led_sniffer -f storage-node/led_sniffer/Dockerfile .
```

### Run the Container

```bash
sudo docker run --rm \
  --privileged \
  --network host \
  --device /dev/gpiomem \
  --device /dev/i2c-1 \
  --device /dev/spidev0.0 \
  led_sniffer
```

#### Notes

- `--privileged` is required to allow low-level hardware access (GPIO, network sniffing).
- `--network host` enables the container to listen to network traffic on the host interface.
- Device flags like `--device /dev/gpiomem` and `--device /dev/spidev0.0` grant access to hardware peripherals used by the NeoPixel library.
- Make sure Docker is installed and your user has permission to run Docker with `sudo`.

## Hardware Setup

- Connect a NeoPixel-compatible LED strip to a GPIO pin (default: D18)
- Ensure your device provides enough power for the number of LEDs
- Suitable for Raspberry Pi or other Linux SBCs with GPIO + Python support

## Notes

- **Root Required**: The script uses raw sockets for packet capture and must be run with sudo.
- **Modular Design**: Relies on ThresholdSniffer for packet analysis and LEDStrip for visual output. Easily customizable.
- **Animation Logic**: The `wave()` animation is triggered whenever the byte threshold is exceeded.
