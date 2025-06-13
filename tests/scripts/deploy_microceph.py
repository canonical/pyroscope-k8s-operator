# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import logging
import os
import subprocess
import shlex
from typing import List, Optional

logger = logging.getLogger("deploy_microceph")

def run_script(command: str, exit_on_error: Optional[bool] = True):
    logger.info(f"{command=}")
    try:
        run_result = subprocess.run(shlex.split(command), text=True, capture_output=True)
    except FileNotFoundError:
        if exit_on_error:
            logger.exception(f"{command=} exited with an exception:")
            exit()
        return None
    if run_result.returncode != 0:
        logger.error(f"{run_result.stdout=}")
        logger.error(f"{run_result.stderr=}")
        if exit_on_error:
            exit(f"{command=} failed with error code {run_result.returncode}")
    logger.info(f"{run_result.stdout=}")
    logger.info(f"{run_result.stderr=}")
    return run_result


def run_scripts(commands: List[str], exit_on_error: Optional[bool] = True):
    for command in commands:
        run_script(command, exit_on_error)


def deploy_microceph(access_key: str, secret_key: str, disk_size: str, disk_no: str):
    run_result = run_script("ceph status", exit_on_error=False)

    if run_result is None or run_result.returncode != 0:
        commands = [
            "snap install microceph",
            "snap refresh --hold microceph",
            "microceph cluster bootstrap",
            f"microceph disk add loop,{disk_size},{disk_no}",
            "microceph enable rgw --port 8080 --ssl-port 8443",
            "microceph.ceph -s",
            "microceph.radosgw-admin user create --uid=user --display-name=User",
        ]
        run_scripts(commands)
    else:
        logger.info("microceph is installed and ready. skipping bootstrap")

    commands = [

        f"microceph.radosgw-admin key create --uid=user --key-type=s3 --access-key={access_key} --secret-key={secret_key}",
    ]

    run_scripts(commands)


def add_bucket(access_key: str, secret_key: str, bucket_name: str):
    commands = [
        "apt install -y s3cmd",
        f"s3cmd --host=localhost:8080 --access_key={access_key} --secret_key={secret_key} --host-bucket= --no-ssl mb s3://{bucket_name}"
    ]
    run_scripts(commands)


if __name__ == "__main__":
    user = os.getenv("MC_USER", "accesskey")
    password = os.getenv("MC_PASSWORD", "secretkey")
    deploy_microceph(
        access_key=user,
        secret_key=password,
        disk_size=os.getenv("MC_DISK_SIZE", "4G"),
        disk_no=os.getenv("MC_DISK_NO", "3"),
    )
    add_bucket(
        access_key=user,
        secret_key=password,
        bucket_name=os.getenv("MC_BUCKET", "pyroscope"),
    )
