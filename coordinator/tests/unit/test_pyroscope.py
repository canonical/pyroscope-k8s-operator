from unittest.mock import MagicMock
import pytest

from pyroscope import Pyroscope


@pytest.mark.parametrize("url", ("/", None, "foo.com"))
def test_pyroscope(url):
    # this test was added for the one and only purpose to achieve 100% coverage.
    cfg = Pyroscope(url)
    mm = MagicMock()
    mm.cluster.gather_addresses.return_value = ("192.0.2.0", "192.0.2.1")
    mm.cluster.gather_addresses_by_role.return_value = {
        "all": {"192.0.2.0", "192.0.2.1"}
    }
    mm._s3_config = {
        "endpoint": "s3-endpoint",
        "region": "s3-region",
        "access_key_id": "s3-access_key",
        "secret_access_key": "s3-secret_key",
        "bucket_name": "s3-bucket",
        "insecure": True,
        "tls_ca_path": "s3-tls_ca_path",
    }
    assert cfg.config(mm)
