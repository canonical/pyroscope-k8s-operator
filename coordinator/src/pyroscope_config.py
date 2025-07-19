# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module for interacting with the Pyroscope configuration."""

from enum import StrEnum, unique
from typing import List, Optional

from coordinated_workers.coordinator import ClusterRolesConfig
from pydantic import BaseModel, Field


@unique
class PyroscopeRole(StrEnum):
    """Pyroscope component role names.

    References:
     arch:
      -> https://grafana.com/docs/pyroscope/latest/reference-pyroscope-architecture/about-grafana-pyroscope-architecture/
     config:
      -> https://grafana.com/docs/pyroscope/latest/configure-server/
    """

    # FIXME: add other optional modules
    # https://github.com/canonical/pyroscope-k8s-operator/issues/4
    all = "all"  # default, meta-role.
    querier = "querier"
    query_frontend = "query-frontend"
    query_scheduler = "query-scheduler"
    ingester = "ingester"
    distributor = "distributor"
    compactor = "compactor"
    store_gateway = "store-gateway"
    tenant_settings = "tenant-settings"
    ad_hoc_profiles = "ad-hoc-profiles"

    @staticmethod
    def all_nonmeta():
        return {
            PyroscopeRole.querier,
            PyroscopeRole.query_frontend,
            PyroscopeRole.query_scheduler,
            PyroscopeRole.ingester,
            PyroscopeRole.distributor,
            PyroscopeRole.compactor,
            PyroscopeRole.store_gateway,
            PyroscopeRole.tenant_settings,
            PyroscopeRole.ad_hoc_profiles,
        }


META_ROLES = {
    "all": set(PyroscopeRole.all_nonmeta()),
}
# Pyroscope component meta-role names.

MINIMAL_DEPLOYMENT = {
    PyroscopeRole.querier: 1,
    PyroscopeRole.query_frontend: 1,
    PyroscopeRole.query_scheduler: 1,
    PyroscopeRole.ingester: 1,
    PyroscopeRole.distributor: 1,
    PyroscopeRole.compactor: 1,
    PyroscopeRole.store_gateway: 1,
    PyroscopeRole.tenant_settings: 1,
    PyroscopeRole.ad_hoc_profiles: 1,
}
# The minimal set of roles that need to be allocated for the
# deployment to be considered consistent (otherwise we set blocked).

RECOMMENDED_DEPLOYMENT = {
    PyroscopeRole.querier.value: 3,
    PyroscopeRole.query_frontend.value: 2,
    PyroscopeRole.query_scheduler.value: 2,
    PyroscopeRole.ingester.value: 3,
    PyroscopeRole.distributor.value: 2,
    PyroscopeRole.compactor.value: 3,
    PyroscopeRole.store_gateway.value: 3,
    PyroscopeRole.tenant_settings: 1,
    PyroscopeRole.ad_hoc_profiles: 1,
}
# The set of roles that need to be allocated for the
# deployment to be considered robust according to Grafana Pyroscope's
# Helm chart configurations.
# https://github.com/grafana/pyroscope/blob/main/operations/pyroscope/helm/pyroscope/values-micro-services.yaml

PYROSCOPE_ROLES_CONFIG = ClusterRolesConfig(
    roles={role for role in PyroscopeRole},
    meta_roles=META_ROLES,
    minimal_deployment=MINIMAL_DEPLOYMENT,
    recommended_deployment=RECOMMENDED_DEPLOYMENT,
)
# Define the configuration for Pyroscope roles.


class Kvstore(BaseModel):
    """Kvstore schema."""

    store: str = "memberlist"


class Ring(BaseModel):
    """Ring schema."""

    kvstore: Kvstore
    replication_factor: Optional[int] = None


class Lifecycler(BaseModel):
    """Lifecycler schema."""

    ring: Ring


class ShardingRing(BaseModel):
    """ShardingRing schema."""

    replication_factor: int


class ShardingRingCompactor(BaseModel):
    """Compactor ShardingRing schema."""

    kvstore: Kvstore


class Api(BaseModel):
    """Api schema."""

    base_url: Optional[str] = Field(
        alias="base-url", default=None
    )  # this is the only field with dash in the entire config

    model_config = {"populate_by_name": True}


class Server(BaseModel):
    """Server schema."""

    http_listen_port: int


class Ingester(BaseModel):
    """Ingester schema."""

    lifecycler: Lifecycler


class StoreGateway(BaseModel):
    """StoreGateway schema."""

    sharding_ring: ShardingRing


class Memberlist(BaseModel):
    """Memberlist schema."""

    bind_port: int
    join_members: List[str]


class S3Storage(BaseModel):
    """S3 Storage schema"""

    bucket_name: str
    endpoint: str
    access_key_id: str
    secret_access_key: str
    region: Optional[str] = None
    insecure: bool = False


class Storage(BaseModel):
    """Storage schema"""

    backend: str
    s3: S3Storage


class Distributor(BaseModel):
    """Distributor schema."""

    ring: Ring


class Compactor(BaseModel):
    """Distributor schema."""

    sharding_ring: ShardingRingCompactor


class DB(BaseModel):
    """Pyroscope DB schema."""

    data_path: str


class PyroscopeConfig(BaseModel):
    """PyroscopeConfig config schema."""

    api: Api
    server: Server
    distributor: Distributor
    ingester: Ingester
    store_gateway: StoreGateway
    memberlist: Memberlist
    storage: Storage
    compactor: Compactor
    pyroscopedb: DB
