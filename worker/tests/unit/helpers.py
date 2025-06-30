from ops.testing import State
from dataclasses import replace
from typing import List

_valid_roles = [
    "all",
    "querier",
    "query-frontend",
    "query-scheduler",
    "ingester",
    "distributor",
    "compactor",
    "store-gateway",
]


def set_roles(state: State, roles: List[str]):
    """Modify a state to activate one or more pyroscope roles."""
    cfg = {}
    for role_ in _valid_roles:
        cfg[f"role-{role_}"] = False
    for role in roles:
        cfg[f"role-{role}"] = True
    return replace(state, config=cfg)
