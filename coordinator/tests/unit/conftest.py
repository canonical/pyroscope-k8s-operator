import json
from contextlib import contextmanager
from pathlib import Path
from shutil import rmtree
from unittest.mock import MagicMock, patch

import pytest
from ops import ActiveStatus
from ops.testing import Container, Context, Relation, PeerRelation

from charm import PyroscopeCoordinatorCharm


@contextmanager
def k8s_patch(status=ActiveStatus(), is_ready=True):
    with patch("lightkube.core.client.GenericSyncClient"):
        with patch.multiple(
            "coordinated_workers.coordinator.KubernetesComputeResourcesPatch",
            _namespace="test-namespace",
            _patch=lambda _: None,
            get_status=MagicMock(return_value=status),
            is_ready=MagicMock(return_value=is_ready),
        ) as patcher:
            yield patcher


@pytest.fixture()
def coordinator():
    return MagicMock()


@pytest.fixture(autouse=True, scope="session")
def cleanup_rendered_alert_rules():
    yield
    src_dir = Path(__file__).parent / "src"
    if src_dir.exists():
        rmtree(src_dir)


@pytest.fixture
def pyroscope_charm():
    with patch("socket.getfqdn", return_value="localhost"):
        with k8s_patch():
            yield PyroscopeCoordinatorCharm


@pytest.fixture(scope="function")
def context(pyroscope_charm):
    return Context(charm_type=pyroscope_charm)


@pytest.fixture(scope="function")
def s3_config():
    return {
        "access-key": "key",
        "bucket": "pyroscope",
        "endpoint": "http://1.2.3.4:9000",
        "secret-key": "soverysecret",
    }


@pytest.fixture(scope="function")
def s3(s3_config):
    return Relation(
        "s3",
        remote_app_data=s3_config,
        local_unit_data={"bucket": "pyroscope"},
    )


@pytest.fixture(scope="function")
def external_host():
    # traefik hostname
    return "example.com"


@pytest.fixture(scope="function")
def ingress(external_host):
    return Relation(
        "ingress",
        remote_app_data={"external_host": external_host, "scheme": "http"},
    )


@pytest.fixture(scope="function")
def catalogue():
    return Relation("catalogue")


@pytest.fixture(scope="function")
def all_worker():
    return Relation(
        "pyroscope-cluster",
        remote_app_data={"role": '"all"'},
        remote_units_data={
            0: {
                "address": json.dumps("localhost"),
                "juju_topology": json.dumps(
                    {
                        "application": "worker",
                        "unit": "worker/0",
                        "charm_name": "pyroscope",
                    }
                ),
            }
        },
    )


@pytest.fixture(scope="function")
def peers():
    return PeerRelation(
        "peers",
    )


@pytest.fixture(scope="function")
def nginx_container():
    return Container(
        "nginx",
        can_connect=True,
    )


@pytest.fixture(scope="function")
def nginx_prometheus_exporter_container():
    return Container(
        "nginx-prometheus-exporter",
        can_connect=True,
    )
