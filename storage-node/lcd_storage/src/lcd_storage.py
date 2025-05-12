import argparse
import logging
import sys
import time
from os import environ

from gpiozero import Device, Button
from gpiozero.pins.lgpio import LGPIOFactory

from utils.loggable import Loggable
from utils.parsing import sizeof
from lcd.lcd import LCDController
from storage_monitor.storage_monitor import StorageMonitor
from k8s.k8s_monitor import K8SDeploymentMonitor

# Configure gpiozero to use LGPIO (needed for Raspberry Pi GPIO)
Device.pin_factory = LGPIOFactory()

# Default CLI values
DEFAULT_I2C_ADDRESS = 0x27
DEFAULT_INTERVAL = 10.0  # seconds
DEFAULT_BUTTON_PIN = 17  # GPIO pin for on/off button
DEFAULT_DEPLOYMENT_PREFIX = "agent"
DEFAULT_NAMESPACE = "neonswarm"
DEFAULT_PATH = "/"
DEFAULT_BUTTON_BOUNCE_TIME = 0.05  # seconds


class LCDDiskMonitor(Loggable):
    """
    Monitor disk usage and display on a 16×2 I2C LCD, with optional K8s scaling.

    Periodically checks the replica count of a Kubernetes Deployment on this node.
    If replicas == 0, displays "<prefix> is OFF"; otherwise, displays used/total storage.
    """

    def __init__(
        self,
        path: str,
        node_name: str,
        namespace: str,
        deployment_prefix: str,
        button_pin: int,
        i2c_addr: int,
        interval: float,
        log_level: int,
    ) -> None:
        """
        Args:
            path: Filesystem path to monitor.
            node_name: Kubernetes node name for selecting the Deployment.
            namespace: Kubernetes namespace containing the Deployment.
            deployment_prefix: Prefix filter for deployment names.
            button_pin: GPIO pin number for the on/off button.
            i2c_addr: I2C address of the LCD device.
            interval: Polling interval in seconds.
            log_level: Python logging level.
        """
        super().__init__(log_level)
        self._path = path
        self._interval = interval

        # Initialize components
        self._lcd = LCDController(i2c_addr=i2c_addr, log_level=log_level)
        self._k8s_monitor = K8SDeploymentMonitor(
            namespace=namespace,
            node_name=node_name,
            deployment_name_prefix=deployment_prefix,
            log_level=log_level,
        )
        self._storage_monitor = StorageMonitor(path=path, log_level=log_level)
        self._button = self._setup_button(button_pin)

    def _setup_button(self, pin: int) -> Button:
        """
        Configure the on/off Button to scale the Deployment up/down.

        Returns:
            Configured gpiozero Button.
        """
        btn = Button(pin, pull_up=True, bounce_time=DEFAULT_BUTTON_BOUNCE_TIME)
        btn.when_pressed = lambda: self._scale(1)
        btn.when_released = lambda: self._scale(0)
        return btn

    def _scale(self, replicas: int) -> None:
        """
        Scale the monitored Deployment to the specified replica count.

        Args:
            replicas: Desired number of replicas (0 or 1).
        """
        name = self._k8s_monitor.deployment_name
        self.logger.info("Scaling '%s' to %d replicas", name, replicas)
        self._k8s_monitor.set_replicas(replicas)

    def _monitor(self) -> None:
        """
        Poll the Deployment replica count and update the LCD accordingly.
        """
        replicas = self._k8s_monitor.replicas
        if replicas == 0:
            # Show OFF message
            msg = f"{self._k8s_monitor.deployment_name} is OFF"
            self._lcd.write(msg)
        else:
            # Display storage usage
            used, total = self._storage_monitor.get_disk_usage()
            line1 = "Storage"
            line2 = f"{sizeof(used)}/{sizeof(total)}"
            self._lcd.write([line1, line2])

    def start(self) -> None:
        """
        Start the monitoring loop until interrupted by SIGINT.
        """
        self.logger.info(
            "Starting LCDDiskMonitor: path=%s interval=%.1fs",
            self._path,
            self._interval,
        )
        try:
            while True:
                self._monitor()
                time.sleep(self._interval)
        except KeyboardInterrupt:
            self.logger.info("Interrupted; clearing LCD and exiting")
            self._lcd.clear()
            sys.exit(0)


def main() -> None:
    """
    Parse CLI arguments and launch the LCD disk monitor.
    """
    parser = argparse.ArgumentParser(
        description="Display disk usage on a 16×2 I2C LCD with optional K8s scaling."
    )
    parser.add_argument(
        "-n",
        "--namespace",
        type=str,
        default=DEFAULT_NAMESPACE,
        help="Kubernetes namespace containing the Deployment.",
    )
    parser.add_argument(
        "-p",
        "--prefix",
        type=str,
        default=DEFAULT_DEPLOYMENT_PREFIX,
        help="Prefix filter for Deployment names.",
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
        "--button-pin",
        type=int,
        default=DEFAULT_BUTTON_PIN,
        help="GPIO pin for on/off button (default: 17).",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help="Seconds between updates (default: 10.0).",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=DEFAULT_PATH,
        help="Filesystem path to monitor (default: '/').",
    )
    parser.add_argument(
        "--node-name",
        type=str,
        default=None,
        help="Kubernetes node name; defaults to $NODE_NAME env var.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")

    node_name = args.node_name or environ.get("NODE_NAME")
    if not node_name:
        parser.error("NODE_NAME not set and --node-name not provided")

    monitor = LCDDiskMonitor(
        path=args.path,
        node_name=node_name,
        namespace=args.namespace,
        deployment_prefix=args.prefix,
        button_pin=args.button_pin,
        i2c_addr=args.address,
        interval=args.interval,
        log_level=level,
    )
    monitor.start()


if __name__ == "__main__":
    main()
