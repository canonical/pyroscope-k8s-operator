#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Pyroscope; a lightweight object storage based profiling backend."""

import logging
import socket
from typing import Optional, Set, Tuple
from urllib.parse import urlparse

from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from coordinated_workers.coordinator import Coordinator
from coordinated_workers.nginx import NginxConfig, CA_CERT_PATH, CERT_PATH, KEY_PATH
from ops.charm import CharmBase
from ops.model import ModelError

import nginx_config
from pyroscope import Pyroscope
from pyroscope_config import PYROSCOPE_ROLES_CONFIG

logger = logging.getLogger(__name__)

class PyroscopeCoordinatorCharm(CharmBase):
    """Charmed Operator for Pyroscope; a distributed profiling backend."""

    def __init__(self, *args):
        super().__init__(*args)

        self._nginx_container = self.unit.get_container("nginx")
        self._nginx_prometheus_exporter_container = self.unit.get_container(
            "nginx-prometheus-exporter"
        )
        self.ingress = IngressPerAppRequirer(
            charm=self,
            port=urlparse(self._internal_url).port,
            strip_prefix=True,
            scheme=lambda: urlparse(self._internal_url).scheme,
        )
        self.pyroscope = Pyroscope()
        self.coordinator = Coordinator(
            charm=self,
            roles_config=PYROSCOPE_ROLES_CONFIG,
            external_url=self._most_external_url,
            worker_metrics_port=Pyroscope.http_server_port,
            endpoints={
                "certificates": "certificates",
                "cluster": "pyroscope-cluster",
                "grafana-dashboards": "grafana-dashboard",
                "logging": "logging",
                "metrics": "metrics-endpoint",
                "s3": "s3",
                "charm-tracing": "charm-tracing",
                "workload-tracing": "workload-tracing",
                "send-datasource": "send-datasource",
                "receive-datasource": None,
                "catalogue": "catalogue",
            },
            nginx_config=NginxConfig(
                server_name=self.hostname,
                upstream_configs=nginx_config.upstreams(Pyroscope.http_server_port),
                server_ports_to_locations=nginx_config.server_ports_to_locations(tls_available=self._are_certificates_on_disk),
                enable_status_page=True,
            ),
            workers_config=self.pyroscope.config,
            worker_ports=self._get_worker_ports,
            # FIXME: add the rest of the optional config
            # resources_requests, resources_limit_options, container_name
            # catalogue_item, workload_tracing_protocols
        )

        # do this regardless of what event we are processing
        self._reconcile()

        ######################################
        # === EVENT HANDLER REGISTRATION === #
        ######################################


    ######################
    # UTILITY PROPERTIES #
    ######################
    @property
    def hostname(self) -> str:
        """Unit's hostname."""
        return socket.getfqdn()

    @property
    def service_hostname(self) -> str:
        """The FQDN of the k8s service associated with this application.
        
        This service load balances traffic across all application units.
        Falls back to this unit's DNS name if the hostname does not resolve to a Kubernetes-style fqdn. 
        """
        # example: 'pyroscope-0.pyroscope-headless.default.svc.cluster.local'
        hostname = self.hostname
        hostname_parts = hostname.split(".") 
        # 'svc' is always there in a K8s service fqdn 
        # ref: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#services
        if "svc" not in hostname_parts:
            logger.debug(f"expected K8s-style fqdn, but got {hostname} instead")
            return hostname
        
        dns_name_parts = hostname_parts[hostname_parts.index("svc"):]
        dns_name = '.'.join(dns_name_parts) # 'svc.cluster.local'
        return f"{self.app.name}.{self.model.name}.{dns_name}" # 'pyroscope.model.svc.cluster.local'
    
    @property
    def _scheme(self) -> str:
        """Return the URI scheme that should be used when communicating with this unit."""
        scheme = "http"
        # FIXME: add a check for are_certificates_on_disk
        return scheme
    
    @property
    def _internal_url(self) -> str:
        """Return the locally addressable, FQDN based service address."""
        return f"{self._scheme}://{self.service_hostname}:8080"

    @property
    def _external_url(self) -> Optional[str]:
        """Return the external URL if the ingress is configured and ready, otherwise None."""
        try:
            if ingress_url := self.ingress.url:
                return ingress_url
        except ModelError as e:
            logger.error("Failed obtaining external url: %s.", e)
        return None
    
    @property
    def _most_external_url(self) -> str:
        """Return the most external url known about by this charm.

        This will return the first of:
        - the external URL, if the ingress is configured and ready
        - the internal URL
        """
        external_url = self._external_url
        if external_url:
            return external_url
        # If we do not have an ingress, then use the K8s service.
        return self._internal_url

    @property
    def _are_certificates_on_disk(self) -> bool:
        return (
            self._nginx_container.can_connect()
            and self._nginx_container.exists(CERT_PATH)
            and self._nginx_container.exists(KEY_PATH)
            and self._nginx_container.exists(CA_CERT_PATH)
        )
    
    ##################
    # EVENT HANDLERS #
    ##################

    ###################
    # UTILITY METHODS #
    ###################

    def _reconcile(self):
        # This method contains unconditional update logic, i.e. logic that should be executed
        # regardless of the event we are processing.
        # reason is, if we miss these events because our coordinator cannot process events (inconsistent status),
        # we need to 'remember' to run this logic as soon as we become ready, which is hard and error-prone
        pass

    def _get_worker_ports(self,  role: str) -> Tuple[int, ...]:
        """Determine, from the role of a worker, which ports it should open."""
        ports:Set[int]= {
            Pyroscope.memberlist_port,
            # we need http_server_port because the metrics server runs on it.
            Pyroscope.http_server_port,
        }
        return tuple(ports)


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(PyroscopeCoordinatorCharm)  # noqa
