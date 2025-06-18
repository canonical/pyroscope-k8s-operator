
#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import jubilant
import pytest
from jubilant import Juju, all_blocked

from helpers import deploy_monolithic_cluster, PYROSCOPE_APP, S3_APP, get_unit_ip_address, emit_profile, get_profiles_patiently


@pytest.mark.setup
def test_deploy_pyroscope(juju: Juju, coordinator_charm):
    url, channel, resources = coordinator_charm
    juju.deploy(
        url, PYROSCOPE_APP, channel=channel, resources=resources, trust=True
    )

    # coordinator will be blocked because of missing s3 and workers integration
    juju.wait(
        lambda status: all_blocked(status, PYROSCOPE_APP),
        timeout=1000
    )

def test_scale_pyroscope_up_stays_blocked(juju: Juju):
    juju.cli("add-unit", PYROSCOPE_APP, "-n", "1")
    juju.wait(
        lambda status: all_blocked(status, PYROSCOPE_APP),
        timeout=1000
    )


@pytest.mark.setup
def test_pyroscope_active_when_deploy_s3_and_workers(juju: Juju):
    deploy_monolithic_cluster(juju, coordinator_deployed_as=PYROSCOPE_APP)


def test_ingest_profiles(juju: Juju):
    # GIVEN a pyroscope cluster
    # WHEN we emit a profile through Pyroscope's HTTP API server
    address = get_unit_ip_address(juju, PYROSCOPE_APP, 0)
    # THEN we get a successful 2xx response
    assert emit_profile(address)

def test_query_profiles(juju: Juju):
    # GIVEN a pyroscope cluster
    # WHEN we query profiles through Pyroscope's HTTP API server
    address = get_unit_ip_address(juju, PYROSCOPE_APP, 0)
    # THEN we get a successful 2xx response
    # AND we a non-empty list of samples
    assert get_profiles_patiently(address)

@pytest.mark.teardown
def test_pyroscope_blocks_if_s3_goes_away(juju: Juju):
    juju.remove_relation(S3_APP, PYROSCOPE_APP)
    # FIXME: s3 stubbornly refuses to die
    # juju.remove_application(S3_APP, force=True)
    juju.wait(lambda status: jubilant.all_blocked(status, PYROSCOPE_APP),
              timeout=1000)