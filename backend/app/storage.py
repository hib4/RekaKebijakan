from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Mapping


@dataclass(frozen=True)
class StorageMetadata:
    key: str
    size: int
    last_modified: datetime
    content_type: str | None = None
    etag: str | None = None
    custom: Mapping[str, str] = field(default_factory=dict)


def normalize_storage_key(key: str) -> str:
    if not isinstance(key, str) or not key or "\x00" in key or "\\" in key:
        raise ValueError("Storage key must be a non-empty POSIX-style path")
    path = PurePosixPath(key)
    if path.is_absolute() or any(part in {".", ".."} for part in key.split("/")):
        raise ValueError("Storage key must be relative and may not contain traversal segments")
    normalized = "/".join(part for part in key.split("/") if part)
    if not normalized:
        raise ValueError("Storage key must identify an object")
    return normalized


class StorageBackend(ABC):
    @abstractmethod
    def healthcheck(self) -> None: ...

    @abstractmethod
    def save(self, key: str, data: bytes | bytearray | memoryview | BinaryIO) -> StorageMetadata: ...

    @abstractmethod
    def open(self, key: str) -> BinaryIO: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def copy(self, source_key: str, destination_key: str) -> StorageMetadata: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def metadata(self, key: str) -> StorageMetadata: ...

    @abstractmethod
    def checksum(self, key: str) -> str: ...


class LocalStorageBackend(StorageBackend):
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> tuple[str, Path]:
        normalized = normalize_storage_key(key)
        target = (self.root / normalized).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as error:
            raise ValueError("Storage key resolves outside the storage root") from error
        return normalized, target

    def healthcheck(self) -> None:
        with tempfile.NamedTemporaryFile(dir=self.root, prefix=".health-", delete=True):
            pass

    def save(self, key: str, data: bytes | bytearray | memoryview | BinaryIO) -> StorageMetadata:
        normalized, target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".storage-", delete=False) as temporary:
                temporary_name = temporary.name
                if isinstance(data, (bytes, bytearray, memoryview)):
                    temporary.write(data)
                else:
                    shutil.copyfileobj(data, temporary)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, target)
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
        return self.metadata(normalized)

    def open(self, key: str) -> BinaryIO:
        return self._path(key)[1].open("rb")

    def delete(self, key: str) -> None:
        _, target = self._path(key)
        target.unlink(missing_ok=True)

    def copy(self, source_key: str, destination_key: str) -> StorageMetadata:
        _, source = self._path(source_key)
        destination_normalized, destination = self._path(destination_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as stored:
            self.save(destination_normalized, stored)
        return self.metadata(destination_normalized)

    def exists(self, key: str) -> bool:
        return self._path(key)[1].is_file()

    def metadata(self, key: str) -> StorageMetadata:
        normalized, target = self._path(key)
        stat = target.stat()
        return StorageMetadata(
            key=normalized,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
            content_type=mimetypes.guess_type(normalized)[0],
        )

    def checksum(self, key: str) -> str:
        digest = hashlib.sha256()
        with self.open(key) as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


class FirebaseStorageBackend(StorageBackend):
    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "",
        bucket_client: Any | None = None,
    ):
        if not bucket:
            raise ValueError("Firebase Storage bucket is required")
        if bucket_client is None:
            try:
                import firebase_admin
                from firebase_admin import credentials, storage
            except ImportError as error:
                raise RuntimeError("Install the 'firebase' optional dependency to use Firebase Storage") from error
            app_name = f"rekakebijakan-storage-{hashlib.sha256(bucket.encode()).hexdigest()[:16]}"
            try:
                app = firebase_admin.get_app(app_name)
            except ValueError:
                app = firebase_admin.initialize_app(
                    credentials.ApplicationDefault(),
                    {"storageBucket": bucket},
                    name=app_name,
                )
            bucket_client = storage.bucket(bucket, app=app)
        self.bucket_name = bucket
        self.prefix = prefix.strip("/")
        self.bucket = bucket_client

    def _blob_name(self, key: str) -> tuple[str, str]:
        normalized = normalize_storage_key(key)
        return normalized, f"{self.prefix}/{normalized}" if self.prefix else normalized

    def healthcheck(self) -> None:
        self.bucket.reload()

    def save(self, key: str, data: bytes | bytearray | memoryview | BinaryIO) -> StorageMetadata:
        normalized, blob_name = self._blob_name(key)
        blob = self.bucket.blob(blob_name)
        content_type = mimetypes.guess_type(normalized)[0]
        if isinstance(data, (bytes, bytearray, memoryview)):
            blob.upload_from_string(bytes(data), content_type=content_type)
        else:
            blob.upload_from_file(data, content_type=content_type)
        return self.metadata(normalized)

    def open(self, key: str) -> BinaryIO:
        _, blob_name = self._blob_name(key)
        return self.bucket.blob(blob_name).open("rb")

    def delete(self, key: str) -> None:
        _, blob_name = self._blob_name(key)
        blob = self.bucket.blob(blob_name)
        if blob.exists():
            blob.delete()

    def copy(self, source_key: str, destination_key: str) -> StorageMetadata:
        _, source = self._blob_name(source_key)
        destination_normalized, destination = self._blob_name(destination_key)
        source_blob = self.bucket.blob(source)
        self.bucket.copy_blob(source_blob, self.bucket, new_name=destination)
        return self.metadata(destination_normalized)

    def exists(self, key: str) -> bool:
        _, blob_name = self._blob_name(key)
        return bool(self.bucket.blob(blob_name).exists())

    def metadata(self, key: str) -> StorageMetadata:
        normalized, blob_name = self._blob_name(key)
        blob = self.bucket.blob(blob_name)
        blob.reload()
        modified = blob.updated or datetime.now(timezone.utc)
        if modified.tzinfo is None:
            modified = modified.replace(tzinfo=timezone.utc)
        return StorageMetadata(
            key=normalized,
            size=int(blob.size or 0),
            last_modified=modified,
            content_type=blob.content_type,
            etag=blob.etag,
            custom=blob.metadata or {},
        )

    def checksum(self, key: str) -> str:
        digest = hashlib.sha256()
        body = self.open(key)
        try:
            for chunk in iter(lambda: body.read(1024 * 1024), b""):
                digest.update(chunk)
        finally:
            body.close()
        return digest.hexdigest()


def make_storage_backend(settings: Any) -> StorageBackend:
    def setting(name: str, default: Any = None) -> Any:
        if isinstance(settings, Mapping):
            return settings.get(name, settings.get(name.upper(), default))
        return getattr(settings, name, getattr(settings, name.upper(), default))

    backend = str(setting("storage_backend", "local")).strip().lower()
    if backend == "local":
        root = setting("storage_path", setting("upload_dir"))
        if root is None:
            raise ValueError("Local storage requires storage_path or upload_dir")
        return LocalStorageBackend(root)
    if backend == "firebase":
        return FirebaseStorageBackend(
            bucket=setting("firebase_storage_bucket", ""),
            prefix=setting("firebase_storage_prefix", ""),
        )
    raise ValueError("storage_backend must be 'local' or 'firebase'")
