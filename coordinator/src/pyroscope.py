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
    # this is the single source of truth for which ports are opened and configured
    # in the distributed Pyroscope deployment
    memberlist_port = 7946
    http_server_port = 4040

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
            server=self._build_server_config(),
            distributor=self._build_distributor_config(),
            ingester=self._build_ingester_config(addrs_by_role),
            store_gateway=self._build_store_gateway_config(addrs_by_role),
            memberlist=self._build_memberlist_config(addrs),
            storage=self._build_storage_config(coordinator._s3_config),
            compactor=self._build_compactor_config(),
            pyroscopedb=self._build_pyroscope_db(),
        )
        return yaml.dump(
            config.model_dump(mode="json", by_alias=True, exclude_none=True)
        )

    def _build_server_config(self):
        return pyroscope_config.Server(
            http_listen_port=self.http_server_port,
        )

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

    def _build_memberlist_config(self, worker_peers: Optional[Tuple[str, ...]]):
        return pyroscope_config.Memberlist(
            bind_port=self.memberlist_port,
            join_members=(
                [f"{peer}:{self.memberlist_port}" for peer in worker_peers]
                if worker_peers
                else []
            ),
        )

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
