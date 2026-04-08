import logging
from typing import Callable, TypeVar

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from utils.loggable import Loggable

T = TypeVar("T")

# HTTP status codes on which we rediscover the target deployment. 404 means
# the named deployment no longer exists; 410 Gone means the apiserver's cache
# has expired the reference (can happen after etcd compaction or a
# deleted-and-recreated resource).
_REDISCOVER_STATUSES = {404, 410}

# Per-request timeout for Kubernetes API calls. Without this, the
# kubernetes-python client has no default read timeout — a hung apiserver
# would block the supervisor loop's main thread indefinitely and defeat both
# clean shutdown and the liveness probe.
_REQUEST_TIMEOUT_SECONDS = 10.0


class DeploymentNotFoundError(RuntimeError):
    """Raised when no deployment matches the prefix/node filter."""


class K8SDeploymentMonitor(Loggable):
    """
    Monitor a Kubernetes Deployment running locally on this node and manage its replicas.

    Loads in-cluster config, filters deployments by the provided prefix, selects the one
    whose node affinity targets this node, and provides methods to read and scale the
    deployment. Self-heals if the deployment is renamed or recreated by re-running the
    discovery on NotFound errors.

    Unlike the previous implementation, this class **propagates exceptions** to the
    caller instead of swallowing them and returning sentinel values — the supervisor
    loop in ``lcd_storage.py`` is responsible for handling transient failures.
    """

    def __init__(
        self,
        namespace: str,
        node_name: str,
        deployment_name_prefix: str = "",
        log_level: int = logging.INFO,
    ) -> None:
        """
        Initialize the Kubernetes deployment monitor.

        Args:
            namespace: Kubernetes namespace containing the deployments.
            node_name: Name of the Kubernetes node to filter deployments by.
            deployment_name_prefix: Prefix filter for deployment names to select.
            log_level: Logging level for monitor output.

        Raises:
            RuntimeError: If in-cluster config cannot be loaded.
            DeploymentNotFoundError: If no matching deployment exists.
        """
        super().__init__(log_level)

        self._namespace = namespace
        self._node_name = node_name
        self._deployment_name_prefix = deployment_name_prefix

        try:
            config.load_incluster_config()
            self.logger.debug("Loaded in-cluster Kubernetes configuration")
        except Exception as e:
            self.logger.error("Failed to load in-cluster config: %s", e)
            raise RuntimeError("Cannot load in-cluster Kubernetes configuration") from e

        self._k8s = client.AppsV1Api()

        self._deployment_name = self._pick_local_deployment()
        if not self._deployment_name:
            message = self._not_found_message()
            self.logger.error(message)
            raise DeploymentNotFoundError(message)

        self.logger.info("Selected deployment: %s", self._deployment_name)

    def _pick_local_deployment(self) -> str:
        """
        Find the Deployment whose node affinity targets this node.

        Returns:
            The name of the matching deployment, or an empty string if none found.

        Raises:
            ApiException: If the list call fails (caller handles).
        """
        deps = self._k8s.list_namespaced_deployment(
            self._namespace, _request_timeout=_REQUEST_TIMEOUT_SECONDS
        ).items

        for dep in deps:
            name = dep.metadata.name
            if self._deployment_name_prefix and not name.startswith(
                self._deployment_name_prefix
            ):
                continue

            spec_aff = dep.spec.template.spec.affinity
            if not spec_aff or not spec_aff.node_affinity:
                continue

            req = (
                spec_aff.node_affinity.required_during_scheduling_ignored_during_execution
            )
            if not req:
                continue

            for term in req.node_selector_terms or []:
                for expr in term.match_expressions or []:
                    if (
                        expr.key == "kubernetes.io/hostname"
                        and self._node_name in (expr.values or [])
                    ):
                        return name
        return ""

    def _not_found_message(self) -> str:
        return (
            f"No deployment with prefix '{self._deployment_name_prefix}' "
            f"found targeting node '{self._node_name}'"
        )

    def _rediscover(self) -> None:
        """
        Re-run discovery after a deployment vanishes. Updates ``_deployment_name``.

        Raises:
            DeploymentNotFoundError: If no matching deployment exists.
        """
        self.logger.warning(
            "Rediscovering deployment for prefix '%s' on node '%s'",
            self._deployment_name_prefix,
            self._node_name,
        )
        new_name = self._pick_local_deployment()
        if not new_name:
            raise DeploymentNotFoundError(self._not_found_message())
        if new_name != self._deployment_name:
            self.logger.info(
                "Deployment changed: '%s' -> '%s'", self._deployment_name, new_name
            )
        self._deployment_name = new_name

    def _call_with_rediscover(self, op: Callable[[], T]) -> T:
        """
        Run ``op`` against the current deployment; on 404/410, rediscover
        once and retry.

        Any other ApiException status (e.g. 503 Service Unavailable during an
        apiserver restart) is propagated unchanged for the supervisor loop
        to classify and display.
        """
        try:
            return op()
        except ApiException as e:
            if e.status not in _REDISCOVER_STATUSES:
                raise
            self._rediscover()
            return op()

    def set_replicas(self, replicas: int) -> None:
        """
        Scale the monitored deployment to the specified number of replicas.

        On NotFound, re-runs discovery once and retries.

        Args:
            replicas: Desired number of replicas.

        Raises:
            ApiException: For any K8s error other than handled NotFound.
            DeploymentNotFoundError: If rediscovery fails.
        """
        body = {"spec": {"replicas": replicas}}
        self._call_with_rediscover(
            lambda: self._k8s.patch_namespaced_deployment(
                name=self._deployment_name,
                namespace=self._namespace,
                body=body,
                _request_timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        )
        self.logger.info(
            "Scaled deployment '%s' to %d replicas", self._deployment_name, replicas
        )

    @property
    def replicas(self) -> int:
        """
        Get the **desired** replica count from the Deployment spec.

        Using ``spec.replicas`` (not ``status.replicas``) means the UI reflects
        intent immediately after a scale operation instead of lagging behind
        until the pods are actually running.

        Returns:
            The current desired replica count. Zero means scaled down.

        Raises:
            ApiException: For any K8s error other than handled NotFound.
            DeploymentNotFoundError: If rediscovery fails.
        """
        deployment = self._call_with_rediscover(
            lambda: self._k8s.read_namespaced_deployment(
                name=self._deployment_name,
                namespace=self._namespace,
                _request_timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        )
        return deployment.spec.replicas or 0

    @property
    def deployment_name(self) -> str:
        """Return the name of the monitored deployment."""
        return self._deployment_name
