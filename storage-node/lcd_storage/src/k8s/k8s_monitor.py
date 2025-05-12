import logging
from kubernetes import client, config
from utils.loggable import Loggable


class K8SDeploymentMonitor(Loggable):
    """
    Monitor a Kubernetes Deployment running locally on this node and manage its replicas.

    This class loads the in-cluster Kubernetes configuration, filters deployments by the
    provided prefix, selects the deployment whose pods target the specified node, and
    provides methods to scale and query the deployment's replica count.
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
            RuntimeError: If no matching deployment is found or configuration fails.
        """
        super().__init__(log_level)

        self._namespace = namespace
        self._node_name = node_name
        self._deployment_name_prefix = deployment_name_prefix
        self._deployment_name = ""

        self._setup_k8s()

    def _setup_k8s(self) -> None:
        """
        Configure the Kubernetes client and select the matching deployment.

        Raises:
            RuntimeError: If configuration fails or no deployment matches.
        """
        # Load in-cluster configuration
        try:
            config.load_incluster_config()
            self.logger.debug("Loaded in-cluster Kubernetes configuration")
        except Exception as e:
            self.logger.error("Failed to load in-cluster config: %s", e)
            raise RuntimeError("Cannot load in-cluster Kubernetes configuration") from e

        # Initialize the AppsV1 API client
        self._k8s = client.AppsV1Api()

        # Select the deployment targeting this node
        self._deployment_name = self._pick_local_deployment()
        if not self._deployment_name:
            message = (
                f"No deployment with prefix '{self._deployment_name_prefix}' "
                f"found targeting node '{self._node_name}'"
            )
            self.logger.error(message)
            raise RuntimeError(message)

        self.logger.info("Selected deployment: %s", self._deployment_name)

    def _pick_local_deployment(self) -> str:
        """
        Find the Deployment whose pods are scheduled on the specified node.

        Returns:
            The name of the matching deployment, or an empty string if none found.
        """
        try:
            deps = self._k8s.list_namespaced_deployment(self._namespace).items
        except Exception as e:
            self.logger.error(
                "Failed to list deployments in namespace '%s': %s",
                self._namespace,
                e,
            )
            return ""

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
                        and self._node_name in expr.values
                    ):
                        return name
        return ""

    def set_replicas(self, replicas: int) -> None:
        """
        Scale the monitored deployment to the specified number of replicas.

        Args:
            replicas: Desired number of replicas.
        """
        try:
            self._k8s.patch_namespaced_deployment(
                name=self._deployment_name,
                namespace=self._namespace,
                body={"spec": {"replicas": replicas}},
            )
            self.logger.info(
                "Scaled deployment '%s' to %d replicas", self._deployment_name, replicas
            )
        except Exception as e:
            self.logger.error(
                "Failed to scale deployment '%s' to %d replicas: %s",
                self._deployment_name,
                replicas,
                e,
            )

    @property
    def replicas(self) -> int:
        """
        Get the current number of replicas for the monitored deployment.

        Returns:
            The current replica count.
        """
        try:
            deployment = self._k8s.read_namespaced_deployment(
                name=self._deployment_name, namespace=self._namespace
            )
            # Use status.replicas for actual current replicas
            return deployment.status.replicas or 0
        except Exception as e:
            self.logger.error(
                "Failed to get replica count for '%s': %s", self._deployment_name, e
            )
            return 0

    @property
    def deployment_name(self) -> str:
        """
        Return the name of the monitored deployment.

        Returns:
            Deployment name.
        """
        return self._deployment_name
