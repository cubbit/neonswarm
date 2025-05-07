#!/usr/bin/env python3

"""
Continuously display disk usage on a 16×2 I2C LCD with optional logging.
"""

from gpiozero import Device  # noqa: E402
from gpiozero.pins.lgpio import LGPIOFactory

# tell gpiozero which backend to use, *before* importing Button
Device.pin_factory = LGPIOFactory()  # noqa: E402

import argparse
import logging
import shutil
import sys
import time
import os
from kubernetes import client, config

from RPLCD.i2c import CharLCD
from utils.parsing import sizeof
from gpiozero import Button

# Default configuration constants
DEFAULT_I2C_ADDRESS = 0x27
DEFAULT_INTERVAL = 10.0
LCD_COLS = 16
LCD_ROWS = 2
DEFAULT_PATH = "/"
DEFAULT_NAMESPACE = "neonswarm"
DEFAULT_BUTTON_PIN = 17  # GPIO pin for the button
GPIOCHIP = "gpiochip0"  # GPIO interface
DEFAULT_BUTTON_BOUNCE_TIME = 0.05  # Button debounce in ms


class LCDDiskMonitor:
    """Monitor disk usage and display it on an I2C LCD."""

    def __init__(
        self,
        path,
        i2c_addr=DEFAULT_I2C_ADDRESS,
        interval=DEFAULT_INTERVAL,
        namespace=DEFAULT_NAMESPACE,
        button_pin=DEFAULT_BUTTON_PIN,
    ):
        self._path = path
        self._interval = interval
        self._namespace = namespace

        logging.debug(
            "Initializing LCDDiskMonitor: path=%s, address=0x%X, " "interval=%.1fs",
            path,
            i2c_addr,
            interval,
        )

        # Kubernetes setup and pick the per-node agent Deployment
        self._setup_k8s()

        self._lcd = CharLCD(
            i2c_expander="PCF8574", address=i2c_addr, cols=LCD_COLS, rows=LCD_ROWS
        )

        self._button = self._setup_button(button_pin)

    def _setup_button(self, pin):
        button = Button(
            pin,
            pull_up=True,
            bounce_time=DEFAULT_BUTTON_BOUNCE_TIME,
        )
        button.when_pressed = self._on_button_pressed
        button.when_released = self._on_button_released

        return button

    def _on_button_pressed(self):
        logging.info(
            "Button pressed → scaling %s → 1 replica",
            self._deployment_name,
        )

        self._set_deployment_replicas(
            self._deployment_name,
            self._namespace,
            1,
        )

        # Monitor immediately to update the LCD accordingly
        self._monitor()

    def _on_button_released(self):
        logging.info(
            "Button released → scaling %s → 0 replica",
            self._deployment_name,
        )

        self._set_deployment_replicas(
            self._deployment_name,
            self._namespace,
            0,
        )

        # Monitor immediately to update the LCD accordingly
        self._monitor()

    def _set_deployment_replicas(
        self,
        deployment,
        namespace,
        replicas,
    ):
        try:
            # patch only the replicas field
            self._k8s.patch_namespaced_deployment(
                name=deployment,
                namespace=namespace,
                body={"spec": {"replicas": replicas}},
            )
        except Exception as e:
            logging.error(
                "Failed to scale replicas for %s to %d: %s",
                deployment,
                replicas,
                e,
            )

    def _setup_k8s(self):
        config.load_incluster_config()
        logging.debug("Loaded in-cluster K8S config")
        self._k8s = client.AppsV1Api()

        self._node_name = os.environ.get("NODE_NAME")
        if not self._node_name:
            logging.error(
                "NODE_NAME env variable not set; cannot pick local Deployment. Are you running inside K8S?"
            )
            sys.exit(1)

        self._deployment_name = self._pick_local_deployment()

        logging.info("Deployment name: %s", self._deployment_name)
        if not self._deployment_name:
            logging.error("No agent Deployment targets node %s", self._node_name)
            sys.exit(1)

    def _pick_local_deployment(self):
        deps = self._k8s.list_namespaced_deployment(namespace=self._namespace).items
        for d in deps:
            aff = d.spec.template.spec.affinity
            if not aff or not aff.node_affinity:
                continue

            req = aff.node_affinity.required_during_scheduling_ignored_during_execution
            if not req:
                continue

            for term in req.node_selector_terms:
                for expr in term.match_expressions or []:
                    if (
                        expr.key == "kubernetes.io/hostname"
                        and self._node_name in expr.values
                    ):
                        return d.metadata.name
        return None

    def _monitor(self):
        replicas = self._get_agent_replicas()

        logging.info("Agent replicas: %d", replicas)

        if replicas == 0:
            # Should stop waiting for an input, displaying that the Agent is OFF
            self._lcd_write_text("Agent is OFF")
        else:
            # Should write the Storage
            used, total = self._get_disk_usage()
            self._lcd_write_storage(used, total)

    def _get_agent_replicas(self):
        deployment = self._k8s.read_namespaced_deployment(
            namespace=self._namespace,
            name=self._deployment_name,
        )
        replicas = deployment.spec.replicas or 0

        return replicas

    def _get_disk_usage(self):
        """Return (used_bytes, total_bytes) for the filesystem path."""
        try:
            usage = shutil.disk_usage(self._path)
        except (FileNotFoundError, PermissionError) as ex:
            logging.error("Cannot access path %s: %s", self._path, ex)
            sys.stderr.write(f"Error: {ex}\n")
            sys.exit(1)

        logging.debug(
            "Disk usage for %s: total=%d, used=%d, free=%d",
            self._path,
            usage.total,
            usage.used,
            usage.free,
        )

        return usage.used, usage.total

    def _lcd_write_storage(self, used, total):
        """Write the formatted usage to the LCD."""
        used_str = sizeof(used)
        total_str = sizeof(total)

        logging.info("Updating LCD display to '%s/%s'", used_str, total_str)

        time.sleep(0.05)

        self._lcd.clear()
        self._lcd.write_string("Storage")
        self._lcd.crlf()
        self._lcd.write_string(f"{used_str}/{total_str}")

    def _lcd_write_text(self, text):
        logging.info("Updating LCD display to '%s'", text)

        time.sleep(0.05)

        self._lcd.clear()
        self._lcd.write_string(text)

    def start(self):
        """Begin polling and updating the LCD until interrupted."""
        logging.info(
            "Starting disk monitor on %s every %.1fs", self._path, self._interval
        )

        try:
            while True:
                self._monitor()
                time.sleep(self._interval)
        except KeyboardInterrupt:
            logging.info("Interrupted; clearing LCD and exiting")
            self._lcd.clear()
            sys.exit(0)


def main():
    """Parse arguments and run the monitor."""
    parser = argparse.ArgumentParser(
        description=("Display used/total storage on a 16×2 I2C LCD" " with logging.")
    )

    parser.add_argument(
        "-n",
        "--namespace",
        type=str,
        help="The K8S namespace to scan for agents",
        default=DEFAULT_NAMESPACE,
    )
    parser.add_argument(
        "path",
        type=str,
        default=DEFAULT_PATH,
        help=("Mount point or path to check (e.g. /, /mnt/data, C:\\)."),
    )
    parser.add_argument(
        "-a",
        "--address",
        type=lambda x: int(x, 0),
        default=DEFAULT_I2C_ADDRESS,
        help="I2C address of the LCD (default: 0x27).",
    )
    parser.add_argument(
        "-b",
        "--button_pin",
        type=int,
        default=DEFAULT_BUTTON_PIN,
        help="On/Off button gpio pin",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help="Seconds between updates (default: 10.0).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging to the console.",
    )
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    monitor = LCDDiskMonitor(
        path=args.path,
        i2c_addr=args.address,
        interval=args.interval,
        namespace=args.namespace,
    )

    monitor.start()


if __name__ == "__main__":
    main()
