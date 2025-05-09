from pathlib import Path
import shutil
import os
import logging
from typing import Tuple, Union

from utils.loggable import Loggable


class StorageMonitor(Loggable):
    """
    Monitors disk usage for a given filesystem path.

    Methods:
        get_disk_usage() -> Tuple[int, int]:
            Returns a tuple of (used_bytes, total_bytes).
    """

    def __init__(
        self,
        path: Union[str, Path],
        log_level: int = logging.INFO,
    ) -> None:
        """
        Initialize the StorageMonitor.

        Args:
            path: Filesystem path to monitor (file or directory).
            log_level: Logging level (e.g., logging.DEBUG).
        """
        super().__init__(log_level)
        self._path = Path(path)

        if not self._path.exists():
            self.logger.error("Path does not exist: %s", self._path)
            raise FileNotFoundError(f"Path does not exist: {self._path}")
        if not os.access(self._path, os.R_OK):
            self.logger.error("No read permission for path: %s", self._path)
            raise PermissionError(f"No read permission for path: {self._path}")

    def get_disk_usage(self) -> Tuple[int, int]:
        """
        Retrieve disk usage statistics for the monitor's path.

        Returns:
            A tuple (used_bytes, total_bytes).

        Raises:
            FileNotFoundError: If the path no longer exists.
            PermissionError: If the path cannot be accessed.
        """
        try:
            usage = shutil.disk_usage(str(self._path))
        except FileNotFoundError as e:
            self.logger.error("Cannot access path %s: %s", self._path, e)
            raise
        except PermissionError as e:
            self.logger.error("Cannot access path %s: %s", self._path, e)
            raise

        self.logger.debug(
            "Disk usage for %s: total=%d bytes, used=%d bytes, free=%d bytes",
            self._path,
            usage.total,
            usage.used,
            usage.free,
        )

        return usage.used, usage.total
