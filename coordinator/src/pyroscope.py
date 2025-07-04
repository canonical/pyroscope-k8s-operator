#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Pyroscope workload configuration and client."""

from typing import Dict, Optional, Set, Tuple
from coordinated_workers.coordinator import Coordinator
from urllib.parse import urlparse
import yaml
import pyroscope_config


class Pyroscope:
    """Class representing the Pyroscope client workload configuration."""

    _data_path = "/pyroscope-data"
    # cert paths on pyroscope container
    tls_cert_path = "/etc/worker/server.cert"
    tls_key_path = "/etc/worker/private.key"
    tls_ca_path = "/usr/local/share/ca-certificates/ca.crt"
    # this is the single source of truth for which ports are opened and configured
    # in the distributed Pyroscope deployment
    memberlist_port = 7946
    http_server_port = 4040

    def __init__(self, app_hostname: str):
        self._app_hostname = app_hostname

    def config(
        self,
        coordinator: Coordinator,
    ) -> str:
        """Generate the Pyroscope configuration."""
        addrs = coordinator.cluster.gather_addresses()
        addrs_by_role = coordinator.cluster.gather_addresses_by_role()
        external_url = coordinator._external_url
        config = pyroscope_config.PyroscopeConfig(
            api=self._build_api_config(external_url),
            server=self._build_server_config(coordinator.tls_available),
            distributor=self._build_distributor_config(),
            frontend=self._build_frontend_config(coordinator.tls_available),
            frontend_worker=self._build_frontend_worker_config(
                coordinator.tls_available
            ),
            query_scheduler=self._build_query_scheduler_config(
                coordinator.tls_available
            ),
            ingester=self._build_ingester_config(addrs_by_role),
            store_gateway=self._build_store_gateway_config(addrs_by_role),
            memberlist=self._build_memberlist_config(addrs, coordinator.tls_available),
            storage=self._build_storage_config(coordinator._s3_config),
            compactor=self._build_compactor_config(),
            pyroscopedb=self._build_pyroscope_db(),
        )
        return yaml.dump(
            config.model_dump(mode="json", by_alias=True, exclude_none=True)
        )

    def _build_server_config(self, tls=False):
        tls_config = (
            pyroscope_config.TLSConfig(
                cert_file=self.tls_cert_path,
                key_file=self.tls_key_path,
            )
            if tls
            else None
        )
        server_config = pyroscope_config.Server(
            http_listen_port=self.http_server_port,
            http_tls_config=tls_config,
        )
        return server_config

    def _build_ingester_config(self, roles_addresses: Dict[str, Set[str]]):
        ingester_addresses = roles_addresses.get(
            pyroscope_config.PyroscopeRole.ingester
        )
        return pyroscope_config.Ingester(
            lifecycler=pyroscope_config.Lifecycler(
                ring=pyroscope_config.Ring(
                    replication_factor=3
                    if ingester_addresses and len(ingester_addresses) >= 3
                    else 1,
                    kvstore=pyroscope_config.Kvstore(
                        store="memberlist",
                    ),
                )
            )
        )

    def _build_store_gateway_config(self, roles_addresses: Dict[str, Set[str]]):
        store_gw_addresses = roles_addresses.get(
            pyroscope_config.PyroscopeRole.store_gateway
        )
        return pyroscope_config.StoreGateway(
            sharding_ring=pyroscope_config.ShardingRing(
                replication_factor=3
                if store_gw_addresses and len(store_gw_addresses) >= 3
                else 1,
            )
        )

    def _build_memberlist_config(
        self, worker_peers: Optional[Tuple[str, ...]], tls=False
    ):
        tls_config = (
            {
                "tls_enabled": True,
                "tls_ca_path": self.tls_ca_path,
                "tls_cert_path": self.tls_cert_path,
                "tls_key_path": self.tls_key_path,
                "tls_server_name": self._app_hostname,
            }
            if tls
            else {}
        )
        memberlist_config = pyroscope_config.Memberlist(
            bind_port=self.memberlist_port,
            join_members=(
                [f"{peer}:{self.memberlist_port}" for peer in worker_peers]
                if worker_peers
                else []
            ),
            **tls_config,
        )
        return memberlist_config

    def _build_storage_config(self, s3_config: dict):
        return pyroscope_config.Storage(
            backend="s3", s3=pyroscope_config.S3Storage(**s3_config)
        )

    def _build_compactor_config(self):
        return pyroscope_config.Compactor(
            sharding_ring=pyroscope_config.ShardingRingCompactor(
                kvstore=pyroscope_config.Kvstore(store="memberlist")
            )
        )

    def _build_pyroscope_db(self):
        return pyroscope_config.DB(data_path=self._data_path)

    def _build_distributor_config(self):
        return pyroscope_config.Distributor(
            ring=pyroscope_config.Ring(
                kvstore=pyroscope_config.Kvstore(
                    store="memberlist",
                )
            )
        )

    def _build_api_config(self, external_url):
        if external_url:
            base_url = self._base_url(external_url)
            if base_url == "" or base_url == "/":
                # we're behind ingress, but on a root path
                return pyroscope_config.Api()
            return pyroscope_config.Api(base_url=base_url)  # pyright: ignore[reportCallIssue]
        return pyroscope_config.Api()

    def _base_url(self, external_url):
        return urlparse(external_url).path

    def _build_grpc_client_config(self, tls=False):
        return (
            pyroscope_config.GrpcClient(
                tls_enabled=True,
                tls_cert_path=self.tls_cert_path,
                tls_key_path=self.tls_key_path,
                tls_ca_path=self.tls_ca_path,
                tls_server_name=self._app_hostname,
            )
            if tls
            else None
        )

    def _build_frontend_config(self, tls=False):
        frontend_config = pyroscope_config.Frontend(
            grpc_client_config=self._build_grpc_client_config(tls),
        )
        return frontend_config

    def _build_frontend_worker_config(self, tls=False):
        frontend_worker_config = pyroscope_config.FrontendWorker(
            grpc_client_config=self._build_grpc_client_config(tls),
        )
        return frontend_worker_config

    def _build_query_scheduler_config(self, tls=False):
        query_scheduler_config = pyroscope_config.QueryScheduler(
            grpc_client_config=self._build_grpc_client_config(tls),
        )
        return query_scheduler_config
