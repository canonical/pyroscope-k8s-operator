import logging
import os
import subprocess
from pathlib import Path

import yaml
from pytest_jubilant import pack_charm

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
PYROSCOPE_WORKER_APP = "pyroscope-worker"
PYROSCOPE_RESOURCES = {
    image_name: image_meta["upstream-source"]
    for image_name, image_meta in METADATA["resources"].items()
}


logger = logging.getLogger(__name__)


def get_worker_charm():
    if worker_charm := os.getenv("CHARM_PATH"):
        return worker_charm

    # Intermittent issue where charmcraft fails to build the charm for an unknown reason.
    # Retry building the charm
    for _ in range(3):
        logger.info("packing...")
        try:
            pth = pack_charm().charm.absolute()
        except subprocess.CalledProcessError:
            logger.warning("Failed to build Pyroscope worker. Trying again!")
            continue
        os.environ["CHARM_PATH"] = str(pth)
        return pth
    raise subprocess.CalledProcessError
