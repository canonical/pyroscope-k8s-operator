import dataclasses
import json

import ops
import pytest

import nginx_config
from ops.testing import State, Context
from conftest import tls_patch
from charms.pyroscope_coordinator_k8s.v0.profiling import (
    ProfilingEndpointRequirer,
    Endpoint,
)


@pytest.mark.parametrize(
    "tls",
    (
        False,
        True,
    ),
)
def test_provide_profiling(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
    profiling,
    peers,
    tls,
):
    with tls_patch(tls):
        state_out = context.run(
            context.on.update_status(),
            State(
                relations=[peers, s3, all_worker, profiling],
                containers=[nginx_container, nginx_prometheus_exporter_container],
                unit_status=ops.ActiveStatus(),
                leader=True,
            ),
        )
    profiling_out = state_out.get_relation(profiling.id)

    assert profiling_out.local_app_data == {
        "insecure": json.dumps(not tls),
        "otlp_grpc_endpoint_url": json.dumps(
            f"foo.com:{nginx_config.grpc_server_port}"
        ),
    }


@pytest.mark.parametrize(
    "internal_tls,ingress_tls,expected_insecure",
    (
        (False, False, True),
        (False, True, False),
        (True, False, True),
        (True, True, False),
    ),
)
def test_provide_profiling_ingress(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
    profiling,
    ingress,
    ingress_with_tls,
    external_host,
    peers,
    internal_tls,
    ingress_tls,
    expected_insecure,
):
    with tls_patch(internal_tls):
        state_out = context.run(
            context.on.update_status(),
            State(
                relations=[
                    peers,
                    s3,
                    ingress_with_tls if ingress_tls else ingress,
                    all_worker,
                    profiling,
                ],
                containers=[nginx_container, nginx_prometheus_exporter_container],
                unit_status=ops.ActiveStatus(),
                leader=True,
            ),
        )
    profiling_out = state_out.get_relation(profiling.id)

    assert profiling_out.local_app_data == {
        "insecure": json.dumps(expected_insecure),
        "otlp_grpc_endpoint_url": json.dumps(
            f"{external_host}:{nginx_config.grpc_server_port}"
        ),
    }


@pytest.mark.parametrize(
    "databag, expected",
    (
        ({}, []),
        (
            {"otlp_grpc_endpoint_url": '"foo.com:1234"', "insecure": '"true"'},
            [Endpoint(otlp_grpc="foo.com:1234", insecure=True)],
        ),
        (
            {"otlp_grpc_endpoint_url": '"foo.com:1234"', "insecure": '"false"'},
            [Endpoint(otlp_grpc="foo.com:1234", insecure=False)],
        ),
    ),
)
def test_require_profiling(profiling, databag, expected):
    ctx = Context(
        ops.CharmBase,
        meta={"name": "mateusz", "requires": {"profiling": {"interface": "profiling"}}},
    )
    with ctx(
        state=State(
            relations={dataclasses.replace(profiling, remote_app_data=databag)},
            leader=True,
        ),
        event=ctx.on.update_status(),
    ) as mgr:
        ep = ProfilingEndpointRequirer(mgr.charm.model.relations["profiling"])
        assert ep.get_endpoints() == expected
