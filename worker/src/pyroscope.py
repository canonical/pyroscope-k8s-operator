#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Pyroscope workload management objects."""

import logging
import socket
import re

from typing import Optional
from ops.charm import CharmBase
from coordinated_workers.worker import Worker, CONFIG_FILE
from ops.pebble import Layer

API_PORT = 4040


logger = logging.getLogger(__name__)


class PyroscopeWorker(Worker):
     
    _name = "pyroscope"

    def __init__(self, charm: CharmBase):
        super().__init__(
            charm=charm,
            name=self._name,
            pebble_layer=self.layer,
            endpoints={"cluster": "pyroscope-cluster"},
            readiness_check_endpoint=self.readiness_check_endpoint,
            # FIXME: add resources requests and limits
        )

    # FIXME: remove `running_version()` and perhaps the `Worker` inheritance
    # once we use the pyroscope rock because the shared worker expects the workload binary at /bin/pyroscope
    def running_version(self) -> Optional[str]:
        """Return Pyroscope workload version."""
        if not self._container.can_connect():
            return None

        version_output, _ = self._container.exec(["/usr/bin/pyroscope", "-version"]).wait_output()
        # Output looks like this:
        # Pyroscope, version 1.13.4 (branch: HEAD, revision 32137ee)
        if result := re.search(r"[Vv]ersion:?\s*(\S+)", version_output):
            return result.group(1)
        return None
    
    @staticmethod
    def layer(worker: Worker) -> Layer:
        """Return the Pebble layer for the Worker.

        This method assumes that worker.roles is valid.
        """
        # Configure Pyroscope workload traces
        env = {}
        if tempo_endpoint := worker.cluster.get_workload_tracing_receivers().get(
            "jaeger_thrift_http", None
        ):
            topology = worker.cluster.juju_topology
            # TODO once https://github.com/grafana/pyroscope/issues/4127 is implemented, switch to otel envvars
            env.update(
                {
                    "JAEGER_ENDPOINT": (f"{tempo_endpoint}/api/traces?format=jaeger.thrift"),
                    "JAEGER_SAMPLER_PARAM": "1",
                    "JAEGER_SAMPLER_TYPE": "const",
                    "JAEGER_TAGS": f"juju_application={topology.application},juju_model={topology.model}"
                    + f",juju_model_uuid={topology.model_uuid},juju_unit={topology.unit},juju_charm={topology.charm_name}",
                }
            )

        roles = worker.roles
        # sort the roles to avoid unnecessary replans
        roles = sorted(roles)
        return Layer(
            {
                "summary": "pyroscope worker layer",
                "description": "pebble config layer for pyroscope worker",
                "services": {
                    "pyroscope": {
                        "override": "replace",
                        "summary": "pyroscope worker process",
                        # Allow configuring multiple roles for one worker application
                        "command": f"/usr/bin/pyroscope -config.file={CONFIG_FILE} -target={','.join(roles)}",
                        "startup": "enabled",
                        "environment": env,
                    }
                },
            }
        )

    @staticmethod
    def readiness_check_endpoint(worker: Worker) -> str:
        """Endpoint for worker readiness checks."""
        scheme = "https" if worker.cluster.get_tls_data() else "http"
        return f"{scheme}://{socket.getfqdn()}:{API_PORT}/ready"