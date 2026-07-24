from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.storage import LocalStorageBackend, S3StorageBackend, make_storage_backend


class FakeS3Client:
    def __init__(self):
        self.objects = {}
        self.head_bucket_calls = []

    def head_bucket(self, **values):
        self.head_bucket_calls.append(values)

    def put_object(self, Bucket, Key, Body):
        self.objects[(Bucket, Key)] = Body.read() if hasattr(Body, "read") else bytes(Body)

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)

    def copy_object(self, Bucket, Key, CopySource):
        self.objects[(Bucket, Key)] = self.objects[(CopySource["Bucket"], CopySource["Key"])]

    def head_object(self, Bucket, Key):
        content = self.objects[(Bucket, Key)]
        return {
            "ContentLength": len(content), "LastModified": datetime.now(timezone.utc),
            "ContentType": "application/octet-stream", "ETag": '"etag"', "Metadata": {},
        }


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorageBackend:
    return LocalStorageBackend(tmp_path / "objects")


@pytest.mark.parametrize(
    "key",
    ["../secret", "folder/../../secret", "/absolute", "folder/./file", "folder\\file", ""],
)
def test_local_storage_rejects_unsafe_keys(storage: LocalStorageBackend, key: str):
    with pytest.raises(ValueError):
        storage.save(key, b"unsafe")


def test_local_storage_rejects_symlink_escape(storage: LocalStorageBackend, tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (storage.root / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError):
        storage.save("escape/file.txt", b"unsafe")


def test_local_storage_save_open_metadata_and_checksum(storage: LocalStorageBackend):
    content = b"policy evidence\n"

    metadata = storage.save("documents//policy.txt", io.BytesIO(content))

    assert metadata.key == "documents/policy.txt"
    assert metadata.size == len(content)
    assert metadata.content_type == "text/plain"
    assert storage.exists("documents/policy.txt")
    with storage.open("documents/policy.txt") as stored:
        assert stored.read() == content
    assert storage.checksum("documents/policy.txt") == hashlib.sha256(content).hexdigest()


def test_local_storage_copy_and_delete(storage: LocalStorageBackend):
    storage.save("source.bin", b"payload")

    copied = storage.copy("source.bin", "archive/copy.bin")

    assert copied.key == "archive/copy.bin"
    assert copied.size == 7
    with storage.open("archive/copy.bin") as stored:
        assert stored.read() == b"payload"
    storage.delete("source.bin")
    storage.delete("source.bin")
    assert not storage.exists("source.bin")
    assert storage.exists("archive/copy.bin")


def test_factory_uses_settings_mapping(tmp_path: Path):
    backend = make_storage_backend({"STORAGE_BACKEND": "local", "STORAGE_PATH": tmp_path})

    assert isinstance(backend, LocalStorageBackend)
    assert backend.root == tmp_path.resolve()


def test_s3_storage_prefix_lifecycle_checksum_and_healthcheck():
    client = FakeS3Client()
    storage = S3StorageBackend("policy-bucket", prefix="tenant/data", client=client)

    stored = storage.save("documents/policy.txt", b"evidence")
    assert stored.key == "documents/policy.txt"
    assert ("policy-bucket", "tenant/data/documents/policy.txt") in client.objects
    assert storage.open("documents/policy.txt").read() == b"evidence"
    assert storage.checksum("documents/policy.txt") == hashlib.sha256(b"evidence").hexdigest()
    copied = storage.copy("documents/policy.txt", "archive/policy.txt")
    assert copied.size == len(b"evidence")
    storage.delete("documents/policy.txt")
    assert ("policy-bucket", "tenant/data/documents/policy.txt") not in client.objects

    storage.healthcheck()
    assert client.head_bucket_calls == [{"Bucket": "policy-bucket"}]
