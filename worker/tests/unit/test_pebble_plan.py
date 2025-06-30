# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import socket
import pytest
from ops.model import ActiveStatus
from scenario import Relation, State

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
                "threshold": 3,
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
    state = set_roles(
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
    state_out = ctx.run(ctx.on.pebble_ready(pyroscope_container), state=state)

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
