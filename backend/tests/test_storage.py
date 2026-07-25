from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.storage import FirebaseStorageBackend, LocalStorageBackend, make_storage_backend


class FakeFirebaseBlob:
    def __init__(self, bucket: "FakeFirebaseBucket", name: str):
        self.bucket = bucket
        self.name = name
        self.size = None
        self.updated = None
        self.content_type = None
        self.etag = None
        self.metadata = None

    def _load(self):
        content, content_type, updated, etag, metadata = self.bucket.objects[self.name]
        self.size = len(content)
        self.updated = updated
        self.content_type = content_type
        self.etag = etag
        self.metadata = metadata
        return content

    def upload_from_string(self, data, content_type=None):
        self.bucket.objects[self.name] = (
            bytes(data), content_type, datetime.now(timezone.utc), "etag", {},
        )

    def upload_from_file(self, data, content_type=None):
        self.upload_from_string(data.read(), content_type=content_type)

    def open(self, mode):
        assert mode == "rb"
        return io.BytesIO(self._load())

    def delete(self):
        self.bucket.objects.pop(self.name, None)

    def exists(self):
        return self.name in self.bucket.objects

    def reload(self):
        self._load()


class FakeFirebaseBucket:
    def __init__(self):
        self.objects = {}
        self.reload_calls = 0

    def blob(self, name):
        return FakeFirebaseBlob(self, name)

    def copy_blob(self, source_blob, destination_bucket, new_name):
        content, content_type, _updated, etag, metadata = self.objects[source_blob.name]
        destination_bucket.objects[new_name] = (
            content, content_type, datetime.now(timezone.utc), etag, metadata,
        )

    def reload(self):
        self.reload_calls += 1


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


def test_firebase_storage_prefix_lifecycle_checksum_and_healthcheck():
    bucket = FakeFirebaseBucket()
    storage = FirebaseStorageBackend("policy-bucket", prefix="tenant/data", bucket_client=bucket)

    stored = storage.save("documents/policy.txt", b"evidence")
    assert stored.key == "documents/policy.txt"
    assert stored.content_type == "text/plain"
    assert "tenant/data/documents/policy.txt" in bucket.objects
    assert storage.open("documents/policy.txt").read() == b"evidence"
    assert storage.checksum("documents/policy.txt") == hashlib.sha256(b"evidence").hexdigest()
    copied = storage.copy("documents/policy.txt", "archive/policy.txt")
    assert copied.size == len(b"evidence")
    storage.delete("documents/policy.txt")
    storage.delete("documents/policy.txt")
    assert "tenant/data/documents/policy.txt" not in bucket.objects

    storage.healthcheck()
    assert bucket.reload_calls == 1


def test_factory_uses_firebase_settings_mapping(monkeypatch):
    fake_bucket = FakeFirebaseBucket()

    def fake_init(self, bucket, *, prefix="", bucket_client=None):
        self.bucket_name = bucket
        self.prefix = prefix.strip("/")
        self.bucket = bucket_client or fake_bucket

    monkeypatch.setattr(FirebaseStorageBackend, "__init__", fake_init)

    backend = make_storage_backend({
        "STORAGE_BACKEND": "firebase",
        "FIREBASE_STORAGE_BUCKET": "policy-bucket",
        "FIREBASE_STORAGE_PREFIX": "tenant/data",
    })

    assert isinstance(backend, FirebaseStorageBackend)
    assert backend.bucket_name == "policy-bucket"
    assert backend.prefix == "tenant/data"
