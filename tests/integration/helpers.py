# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import os
import subprocess
from pathlib import Path
from typing import Literal, Sequence, Union

import jubilant
import yaml
from jubilant import Juju
from minio import Minio
from pytest_jubilant import pack_charm

from coordinator.src.pyroscope_config import PyroscopeRole

# Application names used uniformly across the tests
ACCESS_KEY = "accesskey"
SECRET_KEY = "secretkey"
BUCKET_NAME = "pyroscope"
MINIO_APP = "minio"
S3_APP = "s3-integrator"
WORKER_APP = "pyroscope-worker"
PYROSCOPE_APP = "pyroscope"
TRAEFIK_APP = "trfk"
ALL_ROLES = [role.value for role in PyroscopeRole.all_nonmeta()]
ALL_WORKERS = [f"{WORKER_APP}-" + role for role in ALL_ROLES]
S3_CREDENTIALS = {
    "access-key": ACCESS_KEY,
    "secret-key": SECRET_KEY,
}
INTEGRATION_TESTERS_CHANNEL = "2/edge"

logger = logging.getLogger(__name__)


def get_unit_ip_address(juju: Juju, app_name: str, unit_no: int):
    """Return a juju unit's IP address."""
    return juju.status().apps[app_name].units[f"{app_name}/{unit_no}"].address


def charm_and_channel_and_resources(
    role: Literal["coordinator", "worker"], charm_path_key: str, charm_channel_key: str
):
    """Pyrosocope coordinator or worker charm used for integration testing.

    Build once per session and reuse it in all integration tests to save some minutes/hours.
    """
    # deploy charm from charmhub
    if channel_from_env := os.getenv(charm_channel_key):
        charm = f"pyroscope-{role}-k8s"
        logger.info(f"Using published {charm} charm from {channel_from_env}")
        return charm, channel_from_env, None
    # else deploy from a charm packed locally
    elif path_from_env := os.getenv(charm_path_key):
        charm_path = Path(path_from_env).absolute()
        logger.info("Using local {role} charm: %s", charm_path)
        return (
            charm_path,
            None,
            _get_resources(charm_path.parent),
        )
    # else try to pack the charm
    for _ in range(3):
        logger.info(f"packing Pyroscope {role} charm...")
        try:
            pth = pack_charm(Path() / role).charm.absolute()
        except subprocess.CalledProcessError:
            logger.warning(f"Failed to build Pyroscope {role}. Trying again!")
            continue
        os.environ[charm_path_key] = str(pth)
        return pth, None, _get_resources(pth.parent / role)
    raise subprocess.CalledProcessError


def deploy_distributed_cluster(
    juju: Juju,
    roles: Sequence[str],
    coordinator_deployed_as=None,
    wait_for_idle: bool = True,
):
    """Deploy a pyroscope distributed cluster."""
    worker_charm_url, channel, resources = charm_and_channel_and_resources(
        "worker", "WORKER_CHARM_PATH", "WORKER_CHARM_CHANNEL"
    )

    all_workers = []

    for role in roles:
        worker_name = f"{WORKER_APP}-{role}"
        all_workers.append(worker_name)

        juju.deploy(
            worker_charm_url,
            app=worker_name,
            channel=channel,
            trust=True,
            config={"role-all": False, f"role-{role}": True},
            resources=resources,
        )

    return _deploy_cluster(
        juju,
        all_workers,
        coordinator_deployed_as=coordinator_deployed_as,
        wait_for_idle=wait_for_idle,
    )


def deploy_monolithic_cluster(
    juju: Juju, coordinator_deployed_as=None, wait_for_idle: bool = True
):
    """Deploy a pyroscope-monolithic cluster."""
    worker_charm_url, channel, resources = charm_and_channel_and_resources(
        "worker", "WORKER_CHARM_PATH", "WORKER_CHARM_CHANNEL"
    )

    juju.deploy(
        worker_charm_url,
        app=WORKER_APP,
        channel=channel,
        trust=True,
        resources=resources,
    )
    return _deploy_cluster(
        juju,
        [WORKER_APP],
        coordinator_deployed_as=coordinator_deployed_as,
        wait_for_idle=wait_for_idle,
    )


def _deploy_cluster(
    juju: Juju,
    workers: Sequence[str],
    coordinator_deployed_as: str = None,
    wait_for_idle: bool = False,
):
    logger.info("deploying cluster")

    if coordinator_deployed_as:
        coordinator_app = coordinator_deployed_as
    else:
        coordinator_charm_url, channel, resources = charm_and_channel_and_resources(
            "coordinator", "COORDINATOR_CHARM_PATH", "COORDINATOR_CHARM_CHANNEL"
        )
        juju.deploy(
            coordinator_charm_url,
            PYROSCOPE_APP,
            channel=channel,
            resources=resources,
            trust=True,
        )
        coordinator_app = PYROSCOPE_APP

    for worker in workers:
        juju.integrate(
            coordinator_app + ":pyroscope-cluster", worker + ":pyroscope-cluster"
        )

    # we can't conditionally wait_for_idle for minio, because we need its IP soon to call deploy_s3
    _deploy_and_configure_minio(juju)

    deploy_s3(juju, bucket_name=BUCKET_NAME, s3_integrator_app=S3_APP)
    juju.integrate(coordinator_app + ":s3", S3_APP + ":s3-credentials")

    if wait_for_idle:
        logger.info("waiting for cluster to be active/idle...")
        juju.wait(
            lambda status: jubilant.all_active(
                status, coordinator_app, *workers, S3_APP
            ),
            timeout=2000,
            delay=5,
            successes=3,
        )
    return [coordinator_app, *workers, S3_APP, MINIO_APP]


def _get_resources(path: Union[str, Path]):
    meta = yaml.safe_load((Path(path) / "charmcraft.yaml").read_text())
    resources_meta = meta.get("resources", {})
    return {
        res_name: res_meta["upstream-source"]
        for res_name, res_meta in resources_meta.items()
    }


def deploy_s3(juju, bucket_name: str, s3_integrator_app: str):
    """Deploy and configure a s3 integrator.

    Assumes there's a MINIO_APP deployed and ready.
    """
    logger.info(f"deploying {s3_integrator_app=}")
    # latest revision of s3-integrator creates buckets under relation name, we pin to a working version
    juju.deploy(
        "s3-integrator",
        s3_integrator_app,
        channel="2/edge",
        revision=157,  # FIXME: regression in 2/edge breaks bucket name in databag
        base="ubuntu@24.04",
    )

    logger.info(f"provisioning {bucket_name=} on {s3_integrator_app=}")
    minio_addr = get_unit_ip_address(juju, MINIO_APP, 0)
    mc_client = Minio(
        f"{minio_addr}:9000",
        **{key.replace("-", "_"): value for key, value in S3_CREDENTIALS.items()},
        secure=False,
    )
    # create pyroscope bucket
    found = mc_client.bucket_exists(bucket_name)
    if not found:
        mc_client.make_bucket(bucket_name)

    logger.info("configuring s3 integrator...")
    secret_uri = juju.cli(
        "add-secret",
        f"{s3_integrator_app}-creds",
        *(f"{key}={val}" for key, val in S3_CREDENTIALS.items()),
    )
    juju.cli("grant-secret", f"{s3_integrator_app}-creds", s3_integrator_app)

    # configure s3-integrator
    juju.config(
        s3_integrator_app,
        {
            "endpoint": f"minio-0.minio-endpoints.{juju.model}.svc.cluster.local:9000",
            "bucket": bucket_name,
            "credentials": secret_uri.strip(),
        },
    )


def _deploy_and_configure_minio(juju: Juju):
    if MINIO_APP not in juju.status().apps:
        juju.deploy(MINIO_APP, channel="edge", trust=True, config=S3_CREDENTIALS)
    juju.wait(
        lambda status: status.apps[MINIO_APP].is_active,
        error=jubilant.any_error,
        delay=5,
        successes=3,
        timeout=2000,
    )


def get_ingress_proxied_hostname(juju: Juju):
    status = juju.status()
    status_msg = status.apps[TRAEFIK_APP].app_status.message

    # hacky way to get ingress hostname, but it's the safest one.
    if "Serving at" not in status_msg:
        raise RuntimeError(
            f"Ingressed hostname is not present in {TRAEFIK_APP} status message."
        )
    return status_msg.replace("Serving at", "").strip()
