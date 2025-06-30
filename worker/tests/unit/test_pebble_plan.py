# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import socket
from unittest.mock import MagicMock, patch
import pytest
from ops.model import ActiveStatus
from scenario import Relation, State
from cosl import JujuTopology

from tests.unit.helpers import set_roles
from tests.unit.conftest import config_on_disk, endpoint_ready


@config_on_disk()
@endpoint_ready()
@pytest.mark.parametrize(
    "roles",
    (
        ["all"],
        ["querier"],
        ["query-frontend"],
        ["query-scheduler"],
        ["ingester"],
        ["distributor"],
        ["compactor"],
        ["store-gateway"],
        # meta-roles
        ["query-scheduler", "query-frontend", "querier"],
        ["compactor", "store-gateway"],
    ),
)
def test_pebble_ready_plan(ctx, pyroscope_container, roles):
    roles = sorted(roles)
    host = socket.getfqdn()
    expected_plan = {
        "checks": {
            "ready": {
                "http": {"url": f"http://{host}:4040/ready"},
                "override": "replace",
                "threshold": 3
            }
        },
        "services": {
            "pyroscope": {
                "override": "replace",
                "summary": "pyroscope worker process",
                "command": f"/usr/bin/pyroscope -config.file=/etc/worker/config.yaml -target={','.join(roles)}",
                "startup": "enabled",
            }
        },
    }

    # GIVEN a pyroscope-cluster with a placeholder worker config
    state =set_roles(
            State(
                containers=[pyroscope_container],
                relations=[
                    Relation(
                        "pyroscope-cluster",
                        remote_app_data={
                            "worker_config": json.dumps("beef"),
                        },
                    )
                ],
            ),
            roles,
        )
    # WHEN a workload pebble ready event is fired
    state_out = ctx.run(
        ctx.on.pebble_ready(pyroscope_container),
        state= state
    )

    # THEN pyroscope pebble plan is generated
    pyroscope_container_out = state_out.get_container(pyroscope_container.name)
    assert pyroscope_container_out.plan.to_dict() == expected_plan
    # AND the pebble service is running
    assert pyroscope_container_out.services.get("pyroscope").is_running() is True
    
    # AND the charm status is active
    if roles == ["all"]:
        assert state_out.unit_status == ActiveStatus("(all roles) ready.")
    else:
        assert state_out.unit_status == ActiveStatus(f"{','.join(roles)} ready.")


@config_on_disk()
@endpoint_ready()
@patch.object(
    JujuTopology,
    "from_charm",
    MagicMock(
        return_value=JujuTopology(
            model="test",
            model_uuid="00000000-0000-4000-8000-000000000000",
            application="worker",
            unit="worker/0",
            charm_name="pyroscope",
        )
    ),
)
def test_tracing_config_in_pebble_plan(ctx, pyroscope_container):
    host = socket.getfqdn()
    tempo_endpoint = "http://127.0.0.1"
    expected_plan = {
        "checks": {
            "ready": {
                "http": {"url": f"http://{host}:4040/ready"},
                "override": "replace",
                "threshold": 3
            }
        },
        "services": {
            "pyroscope": {
                "override": "replace",
                "summary": "pyroscope worker process",
                "command": "/usr/bin/pyroscope -config.file=/etc/worker/config.yaml -target=all",
                "startup": "enabled",
                "environment": {
                    "JAEGER_ENDPOINT": (f"{tempo_endpoint}/api/traces?format=jaeger.thrift"),
                    "JAEGER_SAMPLER_PARAM": "1",
                    "JAEGER_SAMPLER_TYPE": "const",
                    "JAEGER_TAGS": "juju_application=worker,juju_model=test"
                    + ",juju_model_uuid=00000000-0000-4000-8000-000000000000,juju_unit=worker/0,juju_charm=pyroscope",
                }
            }
        },
    }

    # GIVEN a workload tracing endpoint in the pyroscope-cluster config
    state = State(
        containers=[pyroscope_container],
        relations=[
            Relation(
                "pyroscope-cluster",
                remote_app_data={
                    "worker_config": json.dumps("beef"),
                    "workload_tracing_receivers": json.dumps({
                        "jaeger_thrift_http": tempo_endpoint
                    })
                },
            ),
        ],
        config={
            "role-all": True,
        },
    )
    # WHEN a workload pebble ready event is fired
    state_out = ctx.run(
        ctx.on.pebble_ready(pyroscope_container),
        state= state
    )

    # THEN the pebble plan contains the workload tracing-related environment variables
    pyroscope_container_out = state_out.get_container(pyroscope_container.name)
    assert pyroscope_container_out.plan.to_dict() == expected_plan