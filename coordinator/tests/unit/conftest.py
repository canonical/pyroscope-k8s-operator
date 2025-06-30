import json
import pytest
from unittest.mock import MagicMock, patch
from charm import PyroscopeCoordinatorCharm
from ops.testing import Context, Relation, Container


@pytest.fixture()
def coordinator():
    return MagicMock()


@pytest.fixture
def pyroscope_charm():
    with patch("socket.getfqdn", return_value="localhost"):
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
def ingress_subpath():
    return Relation(
        "ingress",
        remote_app_data={
            "ingress": json.dumps({"url": "http://1.2.3.5/model-pyroscope-k8s"})
        },
        local_unit_data={
            "host": "localhost",
            "ip": "127.0.0.1",
        },
    )


@pytest.fixture(scope="function")
def ingress_subdomain():
    return Relation(
        "ingress",
        remote_app_data={
            "ingress": json.dumps({"url": "http://pyroscope-k8s.canonical.com"})
        },
        local_unit_data={
            "host": "localhost",
            "ip": "127.0.0.1",
        },
    )


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
