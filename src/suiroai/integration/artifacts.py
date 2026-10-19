"""Local immutable artifact storage; this module grants no execution permission.

Only explicitly released references are staged. Content and registry entries are
rechecked on every read. Read-only files prevent accidental overwrites, not a
malicious process running as the same OS user; host isolation is separate.

Preserve task/source versions through measured file release and result
retrieval so parent checks can inspect the exact bytes a stage consumed or wrote.

Linear: https://linear.app/gr3enarr0w/issue/DSC-26
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat

from suiroai.contracts import digest, record_ref


class ArtifactError(ValueError):
    """An artifact is missing, changed, unsafe, oversized or incorrectly bound."""


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _checked_ref(ref):
    if (not isinstance(ref, dict)
            or set(ref) != {"artifact_id", "version", "sha256", "provenance"}
            or not isinstance(ref["artifact_id"], str) or not ref["artifact_id"]
            or type(ref["version"]) is not int or ref["version"] < 1
            or not isinstance(ref["provenance"], str)
            or ref["provenance"] not in {"supplied", "synthetic", "derived", "mock"}
            or not isinstance(ref["sha256"], str) or len(ref["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in ref["sha256"])):
        raise ArtifactError("invalid contract artifact reference")
    return dict(ref)


@contextmanager
def _directory(path, *, create=False, fresh=False):
    """Walk from / with directory handles, refusing every symlink and '..'."""
    path = Path(path)
    if ".." in path.parts:
        raise ArtifactError("path traversal is forbidden")
    path = path.absolute()
    if fresh and path == Path("/"):
        raise ArtifactError("stage namespace already exists")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, part in enumerate(path.parts[1:]):
            last = index == len(path.parts) - 2
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    if fresh and last:
                        raise ArtifactError("stage namespace already exists") from None
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd
    except OSError as exc:
        raise ArtifactError(f"unsafe or inaccessible artifact directory: {exc.strerror}") from exc
    finally:
        os.close(fd)


def _read(fd, name, limit):
    try:
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise ArtifactError("artifact must be a bounded regular file")
            data = stream.read(limit + 1)
            if len(data) > limit:
                raise ArtifactError("artifact byte limit exceeded")
            return data
    except OSError as exc:
        raise ArtifactError(f"artifact unavailable: {exc.strerror}") from exc


def _write_once(fd, name, data):
    try:
        file_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=fd)
        with os.fdopen(file_fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o400)
    except FileExistsError:
        if _read(fd, name, len(data)) != data:
            raise ArtifactError("immutable artifact collision") from None
    except OSError as exc:
        raise ArtifactError(f"artifact write failed: {exc.strerror}") from exc


def read_stage_file(root, relative_path, max_bytes=16 * 1024 * 1024):
    """Read an explicitly named stage output without following any symlink."""
    path = Path(relative_path)
    if (path.is_absolute() or not path.parts or ".." in path.parts
            or type(max_bytes) is not int or max_bytes < 1):
        raise ArtifactError("stage output must be a bounded relative file path")
    with _directory(Path(root) / path.parent) as fd:
        return _read(fd, path.name, max_bytes)


class ArtifactStore:
    """Content-addressed bytes plus immutable exact-reference receipts.

    The caller supplies already approved/released refs. This store checks bytes
    and identity, and never infers approval, temporal fitness or authenticity.
    """

    def __init__(self, root, *, max_bytes=16 * 1024 * 1024,
                 max_total_bytes=64 * 1024 * 1024):
        if type(max_bytes) is not int or max_bytes < 1:
            raise ArtifactError("max_bytes must be a positive integer")
        if type(max_total_bytes) is not int or max_total_bytes < 1:
            raise ArtifactError("max_total_bytes must be a positive integer")
        self.root = Path(root).absolute()
        self.max_bytes = max_bytes
        self.max_total_bytes = max_total_bytes
        with _directory(self.root, create=True):
            pass
        for name in ("objects", "refs"):
            with _directory(self.root / name, create=True):
                pass

    @staticmethod
    def _registry_name(ref):
        return digest({"artifact_id": ref["artifact_id"], "version": ref["version"]}) + ".json"

    def get_receipt(self, ref):
        """Return a detached, measured retrieval receipt after verification."""
        _, receipt = self._retrieve(ref)
        return receipt

    def check_identity(self, ref):
        """Allow a new or measured exact identity; reject collisions/corruption.

        This is a read-only preflight, not a reservation or batch transaction.
        A later writer must still use the immutable conditional write path.
        Only a genuinely absent registry entry counts as a new identity.
        """
        ref = _checked_ref(ref)
        with _directory(self.root / "refs") as fd:
            try:
                os.stat(self._registry_name(ref), dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                return
        self._retrieve(ref)

    def _retrieve(self, ref):
        ref = _checked_ref(ref)
        with _directory(self.root / "refs") as fd:
            raw = _read(fd, self._registry_name(ref), 16384)
        try:
            receipt = json.loads(raw)
            if (set(receipt) != {"ref", "encoding", "byte_sha256", "bytes"}
                    or receipt["ref"] != ref
                    or receipt["encoding"] not in {"bytes", "canonical_json"}
                    or type(receipt["bytes"]) is not int
                    or not 0 <= receipt["bytes"] <= self.max_bytes
                    or not isinstance(receipt["byte_sha256"], str)
                    or len(receipt["byte_sha256"]) != 64
                    or any(c not in "0123456789abcdef" for c in receipt["byte_sha256"])):
                raise ArtifactError("receipt does not match exact reference")
        except (TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ArtifactError("invalid artifact receipt") from exc
        with _directory(self.root / "objects") as fd:
            data = _read(fd, receipt["byte_sha256"], self.max_bytes)
        if len(data) != receipt["bytes"] or hashlib.sha256(data).hexdigest() != receipt["byte_sha256"]:
            raise ArtifactError("measured artifact bytes do not match receipt")
        if receipt["encoding"] == "canonical_json":
            try:
                record = json.loads(data)
                if record_ref(record) != ref or _json_bytes(record) != data:
                    raise ArtifactError("canonical record does not match exact reference")
            except (ValueError, TypeError, KeyError) as exc:
                raise ArtifactError("invalid canonical record") from exc
        elif receipt["byte_sha256"] != ref["sha256"]:
            raise ArtifactError("raw byte hash does not match contract reference")
        return data, receipt

    def read_bytes(self, ref):
        """Read measured stored bytes (canonical serialization for records)."""
        return self._retrieve(ref)[0]

    def read_record(self, ref):
        data, receipt = self._retrieve(ref)
        if receipt["encoding"] != "canonical_json":
            raise ArtifactError("reference is not a registered contract record")
        return json.loads(data)

    def _put(self, ref, data, encoding):
        ref = _checked_ref(ref)
        if len(data) > self.max_bytes:
            raise ArtifactError("artifact byte limit exceeded")
        byte_sha = hashlib.sha256(data).hexdigest()
        receipt = {"ref": ref, "encoding": encoding,
                   "byte_sha256": byte_sha, "bytes": len(data)}
        receipt_bytes = _json_bytes(receipt)
        if len(receipt_bytes) > 16384:
            raise ArtifactError("artifact reference exceeds receipt limit")
        with _directory(self.root / "objects") as fd:
            _write_once(fd, byte_sha, data)
        with _directory(self.root / "refs") as fd:
            _write_once(fd, self._registry_name(ref), receipt_bytes)
        self._retrieve(ref)
        return dict(ref)

    def put_bytes(self, artifact_id, version, provenance, data):
        if not isinstance(data, bytes):
            raise ArtifactError("raw artifacts must be bytes")
        ref = {"artifact_id": artifact_id, "version": version,
               "provenance": provenance, "sha256": hashlib.sha256(data).hexdigest()}
        return self._put(ref, data, "bytes")

    def put_record(self, record):
        try:
            ref = record_ref(record)
            data = _json_bytes(record)
        except (ValueError, TypeError, KeyError) as exc:
            raise ArtifactError("invalid contract record serialization") from exc
        return self._put(ref, data, "canonical_json")

    def stage_released(self, refs, destination):
        """Copy exactly this allowlist into a fresh namespace; no dependency walk.

        The manifest contains exact refs and measured local receipts, never the
        original source/store paths. An existing namespace is never reused.
        """
        prepared = []
        seen = set()
        total = 0
        for ref in refs:
            # Bound metadata as well as content, including zero-byte artifacts.
            if len(prepared) >= 256:
                raise ArtifactError("released artifact count exceeds limit")
            ref = _checked_ref(ref)
            key = digest(ref)
            if key in seen:
                raise ArtifactError("duplicate released reference")
            seen.add(key)
            data, receipt = self._retrieve(ref)
            total += len(data)
            if total > self.max_total_bytes:
                raise ArtifactError("released artifacts exceed total byte limit")
            prepared.append((key, data, receipt))
        manifest = {"record_kind": "local_released_artifact_manifest",
                    "artifacts": [dict(receipt, relative_path="inputs/" + key)
                                  for key, _, receipt in prepared]}
        manifest_bytes = _json_bytes(manifest)
        if len(manifest_bytes) > self.max_total_bytes:
            raise ArtifactError("released manifest exceeds byte limit")
        with _directory(destination, create=True, fresh=True) as fd:
            os.mkdir("inputs", mode=0o700, dir_fd=fd)
            input_fd = os.open("inputs", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                for key, data, _ in prepared:
                    _write_once(input_fd, key, data)
            finally:
                os.close(input_fd)
            _write_once(fd, "manifest.json", manifest_bytes)
        return manifest
