import boto3
import pytest
from moto import mock_aws

MOCK_BUCKET = "mock-bucket"


@pytest.fixture
def aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def s3_client(aws_credentials):
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=MOCK_BUCKET)
        yield client


@pytest.fixture
def source_file(tmp_path):
    f = tmp_path / "source" / "file.txt"
    f.parent.mkdir(parents=True)
    f.write_text("hello")
    return f


@pytest.fixture
def source_dir(tmp_path):
    d = tmp_path / "source"
    d.mkdir(parents=True)
    (d / "a.txt").write_text("a")
    (d / "subdir").mkdir()
    (d / "subdir" / "b.txt").write_text("b")
    return d
