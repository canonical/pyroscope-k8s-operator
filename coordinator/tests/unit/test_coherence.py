from unittest.mock import MagicMock, patch

import pytest as pytest
from coordinated_workers.coordinator import Coordinator

from pyroscope_config import (
    MINIMAL_DEPLOYMENT,
    RECOMMENDED_DEPLOYMENT,
    PYROSCOPE_ROLES_CONFIG,
    PyroscopeRole,
)


@patch("coordinated_workers.coordinator.Coordinator.__init__", return_value=None)
@pytest.mark.parametrize(
    "roles, expected",
    (
        ({PyroscopeRole.querier: 1}, False),
        ({PyroscopeRole.distributor: 1}, False),
        ({PyroscopeRole.distributor: 1, PyroscopeRole.ingester: 1}, False),
        (MINIMAL_DEPLOYMENT, True),
        (RECOMMENDED_DEPLOYMENT, True),
    ),
)
def test_coherent(mock_coordinator, roles, expected):
    mc = Coordinator(None, None, "", "", 0, None, None, None)
    cluster_mock = MagicMock()
    cluster_mock.gather_roles = MagicMock(return_value=roles)
    mc.cluster = cluster_mock
    mc._is_coherent = None
    mc.roles_config = PYROSCOPE_ROLES_CONFIG

    assert mc.is_coherent is expected


@patch("coordinated_workers.coordinator.Coordinator.__init__", return_value=None)
@pytest.mark.parametrize(
    "roles, expected",
    (
        ({PyroscopeRole.query_frontend: 1}, False),
        ({PyroscopeRole.distributor: 1}, False),
        ({PyroscopeRole.distributor: 1, PyroscopeRole.ingester: 1}, False),
        (MINIMAL_DEPLOYMENT, False),
        (RECOMMENDED_DEPLOYMENT, True),
    ),
)
def test_recommended(mock_coordinator, roles, expected):
    mc = Coordinator(None, None, "", "", 0, None, None, None)
    cluster_mock = MagicMock()
    cluster_mock.gather_roles = MagicMock(return_value=roles)
    mc.cluster = cluster_mock
    mc._is_recommended = None
    mc.roles_config = PYROSCOPE_ROLES_CONFIG

    assert mc.is_recommended is expected
