import logging


class Loggable:
    """
    Mixin that provides a configured logger to any subclass.

    Usage:
        class MyClass(Loggable):
            def __init__(self, ..., log_level: int = logging.INFO):
                super().__init__(log_level)
                # now self.logger is ready to use
    """

    def __init__(self, log_level: int = logging.INFO) -> None:
        """
        Initialize the mixin: sets up a logger named after the subclass.
        """
        self._logger = self._setup_logging(log_level)

    def _setup_logging(self, log_level: int) -> logging.Logger:
        """
        Create or retrieve a logger for this class, attach a NullHandler,
        and set its level. Subclasses should not need to override.

        Args:
            log_level: Desired logging threshold.

        Returns:
            Configured Logger instance.
        """
        name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        logger = logging.getLogger(name)
        logger.setLevel(log_level)

        # Library best practice: attach a NullHandler so we don't
        # inadvertently double‐log if the app configures root handlers.
        if not any(isinstance(h, logging.NullHandler) for h in logger.handlers):
            logger.addHandler(logging.NullHandler())

        return logger

    @property
    def logger(self) -> logging.Logger:
        """
        Public access to the configured logger.
        """
        return self._logger
