# Copyright 2023 Canonical
# See LICENSE file for licensing details.
"""Coordinator Nginx workload configuration utils."""

import logging
from typing import Dict, List

from coordinated_workers.nginx import (
    NginxLocationConfig,
    NginxUpstream,
)

from pyroscope_config import PyroscopeRole

logger = logging.getLogger(__name__)


grpc_server_port = 42424
http_server_port = 8080
https_server_port = 443
# e2e TLS in upstream is not supported yet, so we can only support TLS termination at nginx
upstream_tls = False

http_locations: List[NginxLocationConfig] = [
    NginxLocationConfig(
        path="/",
        backend="worker",
        modifier="=",
        upstream_tls=upstream_tls,
    ),  # pyroscope UI - not bound to a specific role
    NginxLocationConfig(path="/assets", backend="worker", upstream_tls=upstream_tls),
    NginxLocationConfig(
        path="/ingest", backend="distributor", modifier="=", upstream_tls=upstream_tls
    ),
    NginxLocationConfig(
        path="/pyroscope",
        backend="query-frontend",
        modifier="",
        upstream_tls=upstream_tls,
    ),  # API queries
    NginxLocationConfig(
        path="/querier",
        backend="query-frontend",
        upstream_tls=upstream_tls,
    ),  # called by the frontend
    NginxLocationConfig(
        path="/settings", backend="tenant-settings", upstream_tls=upstream_tls
    ),
    NginxLocationConfig(
        path="/adhocprofiles", backend="ad-hoc-profiles", upstream_tls=upstream_tls
    ),
]

grpc_locations: List[NginxLocationConfig] = [
    NginxLocationConfig(
        path="/opentelemetry.proto.collector",
        backend="distributor",
        is_grpc=True,
        upstream_tls=upstream_tls,
    )
]


def upstreams(pyroscope_port: int) -> List[NginxUpstream]:
    """Generate the list of Nginx upstream metadata configurations."""
    upstreams = [NginxUpstream(role, pyroscope_port, role) for role in PyroscopeRole]
    # add a generic `worker` upstream that routes to all workers
    upstreams.append(
        NginxUpstream("worker", pyroscope_port, "worker", ignore_worker_role=True)
    )
    return upstreams


def server_ports_to_locations(
    tls_available: bool,
) -> Dict[int, List[NginxLocationConfig]]:
    """Generate a mapping from server ports to a list of Nginx location configurations."""

    # send http(s) traffic to the http locations; grpc to grpc
    return {
        https_server_port if tls_available else http_server_port: http_locations,
        grpc_server_port: grpc_locations,
    }
