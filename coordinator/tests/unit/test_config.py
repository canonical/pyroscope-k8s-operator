import json
from dataclasses import replace

import pytest
import yaml
from ops.testing import State

from charm import PyroscopeCoordinatorCharm


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
    all_worker, s3, nginx_container, nginx_prometheus_exporter_container, peers
):
    state = State(
        leader=True,
        relations=[all_worker, s3, peers],
        containers=[nginx_container, nginx_prometheus_exporter_container],
    )
    return state


@pytest.fixture
def state_with_ingress(
    all_worker, s3, nginx_container, nginx_prometheus_exporter_container, ingress, peers
):
    state = State(
        leader=True,
        relations=[all_worker, s3, ingress, peers],
        containers=[nginx_container, nginx_prometheus_exporter_container],
    )
    return state


@pytest.mark.parametrize("workers_no", (1, 3))
def test_memberlist_config(
    workers_no, context, state_with_s3_and_workers, all_worker, s3
):
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
    with context(context.on.relation_changed(workers), state) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        actual_config = charm.pyroscope.config(charm.coordinator)
        actual_config_dict = yaml.safe_load(actual_config)
        expected_memberlist_config = {
            "bind_port": 7946,
            "join_members": [
                f"worker-{worker_idx}.test.svc.cluster.local:7946"
                for worker_idx in range(workers_no)
            ],
        }
        # THEN memberlist config portion is generated
        assert "memberlist" in actual_config_dict
        # AND this config contains all worker units as members
        assert actual_config_dict["memberlist"] == expected_memberlist_config


def test_server_config(context, state_with_s3_and_workers):
    # GIVEN an s3 relation and a worker relation
    # WHEN an event is fired
    with context(context.on.config_changed(), state_with_s3_and_workers) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        actual_config = charm.pyroscope.config(charm.coordinator)
        actual_config_dict = yaml.safe_load(actual_config)
        expected_config = {
            "http_listen_port": 4040,
        }
        # THEN server config portion is generated
        assert "server" in actual_config_dict
        # AND this config contains both http and grpc server ports
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


def test_base_url_config_with_no_ingress(context, state_with_s3_and_workers):
    with context(context.on.config_changed(), state_with_s3_and_workers) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        actual_config = charm.pyroscope.config(charm.coordinator)
        actual_config_dict = yaml.safe_load(actual_config)
        expected_config = {}
        # THEN api config portion is generated
        assert "api" in actual_config_dict
        # AND this config doesn't contain the base-url
        assert actual_config_dict["api"] == expected_config


def test_base_url_config_with_ingress(context, state_with_ingress, external_host):
    with context(context.on.config_changed(), state_with_ingress) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        expected_prefix = f"/{state_with_ingress.model.name}-pyroscope-coordinator-k8s"
        assert (
            charm.ingress.is_ready()
            and charm.ingress.external_host
            and charm.ingress.scheme
        )
        assert charm._external_http_url == f"http://{external_host}{expected_prefix}"

        actual_config = charm.pyroscope.config(charm.coordinator)
        actual_config_dict = yaml.safe_load(actual_config)
        expected_config = {"base-url": expected_prefix}
        # THEN api config portion is generated
        assert "api" in actual_config_dict
        # AND this config contains the base-url used by pyroscope-UI to point at the right endpoints
        assert actual_config_dict["api"] == expected_config
