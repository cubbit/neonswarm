"""
LCD disk monitor with self-healing supervisor loop.

Design notes:

* Main loop runs in the foreground thread; it owns the Kubernetes client and
  all LCD writes. Button callbacks run on the gpiozero thread and only set
  ``_wake_event`` — they do no I/O and carry no state, so a button press can
  never block on a slow K8s call. The tick reconciles the Deployment against
  the physical rocker position on every iteration, making the loop idempotent
  and immune to missed-callback races.
* Every tick is wrapped in a catch-all try/except so transient failures
  (I2C glitch, K8s 503, network blip) never crash the process. After
  ``ERROR_DISPLAY_THRESHOLD`` consecutive failures the LCD shows a short
  error label so a human can see it on the panel.
* A health file at ``HEALTH_FILE`` is touched on every loop iteration (success
  **or** error). Kubelet's liveness probe checks the staleness of this file —
  so a true process hang (not a transient error) triggers a pod restart.
* SIGTERM / SIGINT set ``_stop_event`` and the loop exits cleanly at the next
  iteration boundary. The LCD is intentionally **not** cleared on shutdown so
  the panel keeps showing useful information even when the pod is gone.
* The Kubernetes monitor rediscovers its target deployment on NotFound errors,
  so a Helm upgrade that renames the agent deployment does not require a
  restart of lcd-storage.
"""

import argparse
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, TypeVar

from gpiozero import Device, Button
from gpiozero.pins.lgpio import LGPIOFactory

from utils.loggable import Loggable
from utils.conversion import convert_to_node_format

from lcd.lcd import LCDController
from storage_monitor.storage_monitor import StorageMonitor
from k8s.k8s_monitor import K8SDeploymentMonitor, DeploymentNotFoundError
from render import render_frame, render_error

# Configure gpiozero to use LGPIO (needed for Raspberry Pi GPIO)
Device.pin_factory = LGPIOFactory()

# Default CLI values
DEFAULT_I2C_ADDRESS = 0x27
DEFAULT_INTERVAL = 10.0          # seconds
DEFAULT_BUTTON_PIN = 17          # GPIO pin for on/off switch
DEFAULT_DEPLOYMENT_PREFIX = "agent"
DEFAULT_NAMESPACE = "neonswarm"
DEFAULT_PATH = "/"
DEFAULT_BUTTON_BOUNCE_TIME = 0.1  # seconds (latching rocker, generous debounce)

# Resiliency knobs
INIT_MAX_ATTEMPTS = 10           # ~3 min worst case with exponential backoff
INIT_BASE_DELAY = 1.0
INIT_MAX_DELAY = 30.0
ERROR_DISPLAY_THRESHOLD = 3      # consecutive failures before LCD shows error
LCD_REINIT_THRESHOLD = 5         # consecutive LCD write failures before reinit
HEALTH_FILE = Path("/tmp/healthy")

T = TypeVar("T")

logger = logging.getLogger(__name__)


def _retry_init(
    fn: Callable[[], T],
    what: str,
    max_attempts: int = INIT_MAX_ATTEMPTS,
    base_delay: float = INIT_BASE_DELAY,
    max_delay: float = INIT_MAX_DELAY,
) -> T:
    """
    Call ``fn`` with exponential backoff until it succeeds or ``max_attempts`` runs out.

    Used to wrap hardware / cluster initializers that may fail transiently at
    pod start (I2C bus not enumerated yet, agent Deployment not yet created,
    apiserver still coming up).
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == max_attempts:
                logger.error(
                    "%s init failed after %d attempts: %s", what, attempt, e
                )
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            logger.warning(
                "%s init attempt %d/%d failed: %s (retry in %.1fs)",
                what,
                attempt,
                max_attempts,
                e,
                delay,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


class LCDDiskMonitor(Loggable):
    """
    Supervised LCD disk monitor.

    Owns the main loop, hardware handles, and the Kubernetes client. Button
    callbacks only set ``_wake_event`` to break the inter-tick sleep; the
    main loop is the sole caller of any k8s or LCD I/O, and it reconciles
    the cluster state against the physical rocker position each tick.
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
        super().__init__(log_level)

        self._path = path
        self._interval = interval
        self._node_name = node_name
        self._displayed_node_name = convert_to_node_format(node_name)
        self._log_level = log_level

        # Threading primitives. ``_wake_event`` is set by button callbacks to
        # break the inter-tick sleep early; ``_stop_event`` is set by signal
        # handlers to shut down cleanly.
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()

        # Last known desired replicas as reported by the Deployment spec.
        self._last_known_replicas: Optional[int] = None
        # Error counters
        self._consec_errors: int = 0
        self._consec_lcd_errors: int = 0

        # Initialize hardware / cluster clients with retry
        self._lcd: LCDController = _retry_init(
            lambda: LCDController(i2c_addr=i2c_addr, log_level=log_level),
            "LCD",
        )
        self._lcd.write(["booting", self._displayed_node_name])

        self._storage_monitor: StorageMonitor = _retry_init(
            lambda: StorageMonitor(path=path, log_level=log_level),
            "StorageMonitor",
        )

        self._k8s_monitor: K8SDeploymentMonitor = _retry_init(
            lambda: K8SDeploymentMonitor(
                namespace=namespace,
                node_name=self._node_name,
                deployment_name_prefix=deployment_prefix,
                log_level=log_level,
            ),
            "K8SDeploymentMonitor",
        )

        self._button = self._setup_button(button_pin)
        self._install_signal_handlers()

    # ---- setup helpers --------------------------------------------------

    def _setup_button(self, pin: int) -> Button:
        """Wire up the rocker switch. Callbacks stay non-blocking."""
        btn = Button(pin, pull_up=True, bounce_time=DEFAULT_BUTTON_BOUNCE_TIME)
        btn.when_pressed = self._on_pressed
        btn.when_released = self._on_released
        return btn

    def _install_signal_handlers(self) -> None:
        """SIGTERM / SIGINT trigger a clean shutdown on the next loop boundary."""
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, _frame) -> None:
        self.logger.info("received signal %d, shutting down", signum)
        self._stop_event.set()
        self._wake_event.set()

    # ---- button callbacks (gpiozero thread) -----------------------------
    #
    # Callbacks deliberately do **no** I/O and carry no state: they only wake
    # the supervisor loop. The tick reconciles against the physical rocker
    # position on every iteration, so no button event can ever be "lost" due
    # to a failed K8s call — the next successful tick will re-apply it.

    def _on_pressed(self) -> None:
        """Rocker switched to 'I' — wake the loop to reconcile."""
        self._wake_event.set()

    def _on_released(self) -> None:
        """Rocker switched to 'O' — wake the loop to reconcile."""
        self._wake_event.set()

    # ---- tick implementation (main thread) ------------------------------

    def _tick(self) -> None:
        """
        One full supervisor iteration.

        Reads the physical rocker position, reconciles the Deployment against
        it, reads disk usage, and updates the LCD. Fully idempotent: running
        it twice with no state change is a no-op thanks to LCD frame diffing.
        All I/O happens here so there is no sharing of the Kubernetes client
        across threads.
        """
        # 1. Determine desired state from the physical rocker position.
        #    This is the source of truth — any missed button callback will be
        #    picked up at the next tick.
        desired_replicas = 1 if self._button.is_pressed else 0

        # 2. Read authoritative state from the cluster.
        current_replicas = self._k8s_monitor.replicas

        # 3. Reconcile if they disagree. Optimistic update so the LCD reflects
        #    intent immediately instead of waiting for the next poll.
        if desired_replicas != current_replicas:
            self.logger.info(
                "reconciling: rocker=%d cluster=%d", desired_replicas, current_replicas
            )
            self._k8s_monitor.set_replicas(desired_replicas)
            current_replicas = desired_replicas

        self._last_known_replicas = current_replicas

        # 3. Read disk usage only when we intend to display it
        disk_used: Optional[int] = None
        disk_total: Optional[int] = None
        if current_replicas:
            try:
                disk_used, disk_total = self._storage_monitor.get_disk_usage()
            except (FileNotFoundError, PermissionError, OSError) as e:
                self.logger.warning("disk read failed, continuing: %s", e)

        # 4. Render and write the frame
        frame = render_frame(
            node_label=self._displayed_node_name,
            spec_replicas=current_replicas,
            disk_used=disk_used,
            disk_total=disk_total,
            deployment_name=self._k8s_monitor.deployment_name,
        )
        self._lcd_write(frame)

    def _lcd_write(self, frame: List[str]) -> None:
        """
        Write a frame to the LCD, counting failures and attempting an in-place
        reinit if too many writes in a row have failed.
        """
        try:
            self._lcd.write(frame)
            self._consec_lcd_errors = 0
        except Exception:
            self._consec_lcd_errors += 1
            self.logger.exception(
                "LCD write failed (%d consecutive)", self._consec_lcd_errors
            )
            if self._consec_lcd_errors >= LCD_REINIT_THRESHOLD:
                self._consec_lcd_errors = 0
                try:
                    self._lcd.reinit()
                except Exception:
                    self.logger.exception("LCD reinit failed")
            # Re-raise so the supervisor counts this as a tick error.
            raise

    # ---- supervisor loop ------------------------------------------------

    def start(self) -> None:
        """
        Run the supervisor loop until a shutdown signal is received.

        Never raises on transient errors — only on explicit shutdown. After
        ``ERROR_DISPLAY_THRESHOLD`` consecutive failures the LCD switches to
        an error frame so the panel shows something actionable.
        """
        self.logger.info(
            "Starting LCDDiskMonitor: path=%s interval=%.1fs", self._path, self._interval
        )

        # Clear any boot frame and let the first tick paint fresh state.
        self._touch_health()

        while not self._stop_event.is_set():
            tick_start = time.monotonic()
            tick_deadline = tick_start + self._interval

            try:
                self._tick()
                self._consec_errors = 0
            except Exception as exc:
                self._consec_errors += 1
                self.logger.exception(
                    "tick failed (%d consecutive)", self._consec_errors
                )
                if self._consec_errors >= ERROR_DISPLAY_THRESHOLD:
                    self._show_error(exc)

            # Touch the health file regardless of error — the loop itself is
            # alive and running. The liveness probe only triggers on a real hang.
            self._touch_health()

            remaining = tick_deadline - time.monotonic()
            if remaining > 0:
                # Sleep is interruptible by button press (wake_event) or shutdown.
                self._wake_event.wait(remaining)
                self._wake_event.clear()

        self.logger.info("Supervisor loop exited cleanly")

    def _show_error(self, exc: Exception) -> None:
        """
        Map an exception to a short LCD error frame and attempt to write it.

        If writing the error frame itself fails we swallow that failure —
        the supervisor loop will keep trying on subsequent ticks.
        """
        label, detail = self._classify_error(exc)
        self.logger.warning("Displaying error frame: %s / %s", label, detail)
        try:
            self._lcd.write(render_error(label, detail))
        except Exception:
            self.logger.exception("Failed to write error frame to LCD")

    @staticmethod
    def _classify_error(exc: Exception) -> tuple[str, str]:
        """Return (short_label, detail) for an error frame."""
        if isinstance(exc, DeploymentNotFoundError):
            return ("NO AGENT", "")
        name = type(exc).__name__
        if name == "ApiException":
            return ("K8S ERROR", "")
        if isinstance(exc, (FileNotFoundError, PermissionError, OSError)):
            return ("DISK ERROR", "")
        return ("ERROR", name[:16])

    def _touch_health(self) -> None:
        """Update the liveness probe marker."""
        try:
            HEALTH_FILE.touch(exist_ok=True)
        except Exception:
            self.logger.warning("failed to touch health file %s", HEALTH_FILE)


def main() -> None:
    """Parse CLI arguments and launch the LCD disk monitor."""
    parser = argparse.ArgumentParser(
        description="Display disk usage on a 16×2 I2C LCD with K8s deployment scaling."
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

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    node_name = args.node_name or os.environ.get("NODE_NAME")
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
    sys.exit(0)


if __name__ == "__main__":
    main()
