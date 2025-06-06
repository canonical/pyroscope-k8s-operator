# Copyright 2023 Canonical
# See LICENSE file for licensing details.
"""Nginx workload."""

import logging
from typing import Dict, List

from coordinated_workers.nginx import (
    CA_CERT_PATH,
    CERT_PATH,
    KEY_PATH,
    NginxLocationConfig,
    NginxUpstream,
)
from ops import Container

from pyroscope_config import PyroscopeRole

logger = logging.getLogger(__name__)



class NginxHelper:
    """Helper class to generate the nginx configuration."""
    _pyroscope_port = 4040
    _nginx_port = 8080
    _nginx_tls_port = 443

    _locations_write: List[NginxLocationConfig] = [
        NginxLocationConfig(path="/ingest", backend="ingester",modifier="="),
    ]

    _locations_query_frontend: List[NginxLocationConfig] = [
        NginxLocationConfig(path="/pyroscope/render", backend="query-frontend",modifier="="), # API queries
        NginxLocationConfig(path="/pyroscope/render-diff", backend="query-frontend", modifier="="),  # API queries
        NginxLocationConfig(path="/querier.v1.QuerierService", backend="query-frontend"),  # called by the frontend
    ]

    _locations_worker: List[NginxLocationConfig] = [
        NginxLocationConfig(path="/", backend="worker", modifier="="), # pyroscope UI - not bound to a specific role
        NginxLocationConfig(path="/assets", backend="worker")
    ]

    def __init__(
        self,
        container: Container,
    ):
        self._container = container

    def upstreams(self) -> List[NginxUpstream]:
        """Generate the list of Nginx upstream metadata configurations."""
        upstreams = [NginxUpstream(role, self._pyroscope_port, role) for role in PyroscopeRole]
        # add a generic `worker` upstream that routes to all workers
        upstreams.append(NginxUpstream("worker", self._pyroscope_port, "worker", ignore_worker_role=True))
        return upstreams

    def server_ports_to_locations(self) -> Dict[int, List[NginxLocationConfig]]:
        """Generate a mapping from server ports to a list of Nginx location configurations."""
        return {
            self._nginx_tls_port if self._tls_available else self._nginx_port: self._locations_write + self._locations_query_frontend + self._locations_worker
        }

    @property
    def _tls_available(self) -> bool:
        return (
                self._container.can_connect()
                and self._container.exists(CERT_PATH)
                and self._container.exists(KEY_PATH)
                and self._container.exists(CA_CERT_PATH)
            )




