import json
from unittest.mock import patch
import pytest
from dataclasses import replace

import yaml

from charm import PyroscopeCoordinatorCharm
from pyroscope import Pyroscope
from ops.testing import State


def get_worker_unit_data(unit_no):
    return {
        "address": json.dumps(f"worker-{unit_no}.test.svc.cluster.local"),
        "juju_topology": json.dumps(
            {
                "model": "test",
                "unit": f"worker/{unit_no}",
                "model_uuid": "1",
                "application": "worker",
                "charm_name": "PyroscopeWorker",
            }
        ),
    }


@pytest.fixture
def state_with_s3_and_workers(
    all_worker, s3, nginx_container, nginx_prometheus_exporter_container
):
    state = State(
        leader=True,
        relations=[all_worker, s3],
        containers=[nginx_container, nginx_prometheus_exporter_container],
    )
    return state


@pytest.fixture
def state_with_ingress_subdomain(
    all_worker,
    s3,
    nginx_container,
    nginx_prometheus_exporter_container,
    ingress_subdomain,
):
    state = State(
        leader=True,
        relations=[all_worker, s3, ingress_subdomain],
        containers=[nginx_container, nginx_prometheus_exporter_container],
    )
    return state


@pytest.fixture
def state_with_ingress_subpath(
    all_worker,
    s3,
    nginx_container,
    nginx_prometheus_exporter_container,
    ingress_subpath,
):
    state = State(
        leader=True,
        relations=[all_worker, s3, ingress_subpath],
        containers=[nginx_container, nginx_prometheus_exporter_container],
    )
    return state

@pytest.mark.parametrize("tls", (False,True))
@pytest.mark.parametrize("workers_no", (1,3))
def test_memberlist_config(workers_no, tls, context, state_with_s3_and_workers, all_worker, s3):
    # GIVEN an s3 relation and a worker relation that has n units
    workers = replace(
        all_worker,
        remote_units_data={
            worker_idx: get_worker_unit_data(worker_idx)
            for worker_idx in range(workers_no)
        },
    )
    state = replace(state_with_s3_and_workers, relations={workers, s3})

    # WHEN an event is fired
    with patch("coordinated_workers.coordinator.Coordinator.tls_available", tls):
        with context(context.on.relation_changed(workers), state) as mgr:
            charm: PyroscopeCoordinatorCharm = mgr.charm
            actual_config = charm.pyroscope.config(charm.coordinator)
            actual_config_dict = yaml.safe_load(actual_config)
            expected_memberlist_config = {
                "bind_port": 7946,
                "join_members": [f"worker-{worker_idx}.test.svc.cluster.local:7946" for worker_idx in range(workers_no)],
                "tls_enabled": tls,
                 **(
                {
                    "tls_cert_path": Pyroscope.tls_cert_path,
                    "tls_key_path": Pyroscope.tls_key_path,
                    "tls_ca_path": Pyroscope.tls_ca_path,
                }
                if tls
                else {}
                ),
            }
            # THEN memberlist config portion is generated
            assert "memberlist" in actual_config_dict
            # AND this config contains all worker units as members + tls config if enabled
            assert actual_config_dict["memberlist"] == expected_memberlist_config

@pytest.mark.parametrize("tls", (False,True))
def test_server_config(context, state_with_s3_and_workers, tls):
    # GIVEN an s3 relation and a worker relation
    # WHEN an event is fired
    with patch("coordinated_workers.coordinator.Coordinator.tls_available", tls):
        with context(context.on.config_changed(), state_with_s3_and_workers) as mgr:
            charm: PyroscopeCoordinatorCharm = mgr.charm
            actual_config = charm.pyroscope.config(charm.coordinator)
            actual_config_dict = yaml.safe_load(actual_config)
            expected_config = {
                "http_listen_port": 4040,
            }
            if tls:
                expected_config["http_tls_config"] = {
                    "cert_file": Pyroscope.tls_cert_path,
                    "key_file": Pyroscope.tls_key_path,
                    "client_ca_file": Pyroscope.tls_ca_path,
                }
            # THEN server config portion is generated
            assert "server" in actual_config_dict
            # AND this config contains both http and grpc server ports + tls config if enabled
            assert actual_config_dict["server"] == expected_config


@pytest.mark.parametrize("workers_no", (1, 3))
def test_ingester_config(
    workers_no, context, state_with_s3_and_workers, all_worker, s3
):
    # GIVEN an s3 relation and an ingester worker relation that has n units
    ingester_workers = replace(
        all_worker,
        remote_app_data={"role": '"ingester"'},
        remote_units_data={
            worker_idx: get_worker_unit_data(worker_idx)
            for worker_idx in range(workers_no)
        },
    )
    state = replace(state_with_s3_and_workers, relations={ingester_workers, s3})
    # WHEN an event is fired
    with context(context.on.relation_changed(ingester_workers), state) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        actual_config = charm.pyroscope.config(charm.coordinator)
        actual_config_dict = yaml.safe_load(actual_config)
        expected_config = {
            "lifecycler": {
                "ring": {
                    "replication_factor": 3 if workers_no > 1 else 1,
                    "kvstore": {"store": "memberlist"},
                }
            }
        }
        # THEN ingester config portion is generated
        assert "ingester" in actual_config_dict
        # AND this config has memberlist store and a replication factor dependant on the no of ingester workers
        assert actual_config_dict["ingester"] == expected_config


@pytest.mark.parametrize("workers_no", (1, 3))
def test_store_gateway_config(
    workers_no, context, state_with_s3_and_workers, all_worker, s3
):
    # GIVEN an s3 relation and a store-gateway worker relation that has n units
    store_gw_workers = replace(
        all_worker,
        remote_app_data={"role": '"store-gateway"'},
        remote_units_data={
            worker_idx: get_worker_unit_data(worker_idx)
            for worker_idx in range(workers_no)
        },
    )
    state = replace(state_with_s3_and_workers, relations={store_gw_workers, s3})
    # WHEN an event is fired
    with context(context.on.relation_changed(store_gw_workers), state) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        actual_config = charm.pyroscope.config(charm.coordinator)
        actual_config_dict = yaml.safe_load(actual_config)
        expected_config = {
            "sharding_ring": {
                "replication_factor": 3 if workers_no > 1 else 1,
            }
        }
        # THEN store_gateway config portion is generated
        assert "store_gateway" in actual_config_dict
        # AND this config has a replication factor dependant on the no of store-gateway workers
        assert actual_config_dict["store_gateway"] == expected_config


def test_s3_storage_config(context, state_with_s3_and_workers):
    # GIVEN an s3 relation and a worker relation
    # WHEN an event is fired
    with context(context.on.config_changed(), state_with_s3_and_workers) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        actual_config = charm.pyroscope.config(charm.coordinator)
        actual_config_dict = yaml.safe_load(actual_config)
        expected_config = {
            "backend": "s3",
            "s3": {
                "access_key_id": "key",
                "bucket_name": "pyroscope",
                "endpoint": "1.2.3.4:9000",
                "secret_access_key": "soverysecret",
                "insecure": True,
            },
        }
        # THEN storage config portion is generated
        assert "storage" in actual_config_dict
        # AND this config contains the s3 config as upstream defines it
        assert actual_config_dict["storage"] == expected_config

@pytest.mark.parametrize("tls", (False,True))
def test_grpc_client_config(context, state_with_s3_and_workers, tls):
    # GIVEN an s3 relation and a worker relation
    # WHEN an event is fired
    with patch("coordinated_workers.coordinator.Coordinator.tls_available", tls):
        with context(context.on.config_changed(), state_with_s3_and_workers) as mgr:
            charm: PyroscopeCoordinatorCharm = mgr.charm
            actual_config = charm.pyroscope.config(charm.coordinator)
            actual_config_dict = yaml.safe_load(actual_config)
            expected_config = {
                "tls_enabled": tls,
                **(
                {
                    "tls_cert_path": Pyroscope.tls_cert_path,
                    "tls_key_path": Pyroscope.tls_key_path,
                    "tls_ca_path": Pyroscope.tls_ca_path,
                }
                if tls
                else {}
                ),
            }
            # THEN grpc client config portion is generated
            assert "grpc_client" in actual_config_dict
            # AND this config contains the grpc_client config + tls config if enabled
            assert actual_config_dict["grpc_client"] == expected_config

def test_base_url_config_without_ingress(context, state_with_s3_and_workers):
    with context(context.on.config_changed(), state_with_s3_and_workers) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        actual_config = charm.pyroscope.config(charm.coordinator)
        actual_config_dict = yaml.safe_load(actual_config)
        expected_config = {}
        # THEN api config portion is generated
        assert "api" in actual_config_dict
        # AND this config doesn't contain the base-url
        assert actual_config_dict["api"] == expected_config


def test_base_url_config_with_ingress_on_subdomain(
    context, state_with_ingress_subdomain
):
    with context(context.on.config_changed(), state_with_ingress_subdomain) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        actual_config = charm.pyroscope.config(charm.coordinator)
        actual_config_dict = yaml.safe_load(actual_config)
        expected_config = {}
        # THEN api config portion is generated
        assert "api" in actual_config_dict
        # AND this config doesn't contain the base-url
        assert actual_config_dict["api"] == expected_config


def test_base_url_config_with_ingress_on_subpath(context, state_with_ingress_subpath):
    with context(context.on.config_changed(), state_with_ingress_subpath) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        actual_config = charm.pyroscope.config(charm.coordinator)
        actual_config_dict = yaml.safe_load(actual_config)
        expected_config = {"base-url": "/model-pyroscope-k8s"}
        # THEN api config portion is generated
        assert "api" in actual_config_dict
        # AND this config contains the base-url used by pyroscope-UI to point at the right endpoints
        assert actual_config_dict["api"] == expected_config
