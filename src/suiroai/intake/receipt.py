"""Explicit file receipt and bounded read-only inspection. No preparation.

Measure supplied file bytes, preserve source identity, and inspect tabular
structure within explicit bounds to support the task-understanding step.

Ground step2 understanding in files actually supplied and distinguish absent
or inaccessible inputs before sign-off, without performing preparation joins.

Linear: https://linear.app/gr3enarr0w/issue/DSC-25
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
import hashlib
import io
import json
import os
from pathlib import Path
import stat
from urllib.parse import urlparse

from suiroai.contracts import VERSION, input_digest, record_ref, validate_record


class IntakeError(ValueError):
    """Invalid input or unsafe conversation output; never analytical failure."""


def freeze(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def checked(record):
    errors = validate_record(record)
    if errors:
        raise IntakeError("; ".join(errors))
    return record


@dataclass(frozen=True)
class SuppliedFile:
    file_id: str
    location: str
    source_role: str
    source_namespace: str
    provenance: str = "supplied"
    version: int = 1
    original_name: str | None = None


@dataclass(frozen=True)
class MeasuredInput:
    file_id: str
    version: int
    provenance: str
    sha256: str
    data: bytes = field(repr=False)
    inspection_json: str

    @property
    def ref(self):
        return {"artifact_id": self.file_id, "version": self.version,
                "sha256": self.sha256, "provenance": self.provenance}

    @property
    def inspection(self):
        return json.loads(self.inspection_json)


@dataclass(frozen=True)
class Receipt:
    submission_json: str
    sources: tuple[MeasuredInput, ...]

    @property
    def submission(self):
        return json.loads(self.submission_json)

    @property
    def ref(self):
        return record_ref(self.submission)

    @property
    def external_refs(self):
        return [source.ref for source in self.sources]

    @property
    def inspections(self):
        return [source.inspection for source in self.sources]


def _read_local(file, limit):
    if urlparse(file.location).scheme:
        raise OSError("Remote reference needs an authorized connector/download; no bytes were inspected")
    path = Path(file.location)
    if not path.is_absolute():
        raise OSError("Supply an explicit absolute file path or connector-measured bytes")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise OSError("Supplied location is not a regular file")
        return stream.read(limit + 1)


def _inspect(file, data):
    result = {"file_id": file.file_id, "columns": [], "dictionary_preview": [],
              "inspection": "bytes measured only", "candidate_key_columns": [],
              "analytical_preparation_performed": False}
    try:
        text = data.decode("utf-8-sig")
        # csv.reader reads records, not joins, cleaning, counts or aggregation.
        reader = csv.reader(io.StringIO(text))
        header = next(reader, [])
        if not header or len(header) > 256 or any(len(c) > 256 for c in header) or sum(map(len, header)) > 4096:
            raise ValueError("header outside bounded inspection")
        result.update(columns=header, inspection="CSV header only; row meanings/fitness unverified",
                      candidate_key_columns=[c for c in header if c in {"Product_ID", "Store_ID"}])
        if file.source_role == "dictionary":
            preview = []
            for _, row in zip(range(40), reader):
                if len(row) > 256 or any(len(c) > 1024 for c in row):
                    break
                if len(freeze(preview + [row]).encode()) > 8192:
                    break
                preview.append(row)
            result["dictionary_preview"] = preview
            result["inspection"] = "CSV header and at most 40 dictionary records; preview may be partial"
    except (UnicodeError, csv.Error, ValueError):
        result["inspection"] = "Bytes measured; format requires an explicit read-only inspector"
    return result


def receive_submission(*, original_request, files, task_id, task_version,
                       input_version, received_at, read_bytes=None,
                       max_file_bytes=16 * 1024 * 1024,
                       max_total_bytes=64 * 1024 * 1024):
    """Read only the listed references; never discover or substitute fixtures.

    A trusted connector may provide read_bytes(SuppliedFile, byte_limit). It
    must bound its own network I/O. Missing/inaccessible inputs remain explicit.
    Artifact IDs/versions and task/input revisions are allocated by DSC-10.
    """
    files = tuple(files)
    if len(files) > 64 or len({f.file_id for f in files}) != len(files):
        raise IntakeError("At most 64 uniquely identified supplied files are supported")
    if any(type(f.version) is not int or f.version < 1 for f in files):
        raise IntakeError("Explicit positive file versions are required")
    if any(type(n) is not int or n < 1 for n in (max_file_bytes, max_total_bytes)):
        raise IntakeError("Positive byte limits required")
    entries, sources, total = [], [], 0
    for file in files:
        entry = {"file_id": file.file_id, "original_name": file.original_name or Path(file.location).name,
                 "supplied_location": file.location, "source_role": file.source_role,
                 "source_namespace": file.source_namespace, "provenance": file.provenance,
                 "access": "inaccessible", "sha256": None, "size_bytes": None, "access_reason": None}
        try:
            limit = min(max_file_bytes, max_total_bytes - total)
            if limit <= 0:
                raise OSError("Total receipt byte limit exhausted; supply a bounded readable extract")
            data = (read_bytes or _read_local)(file, limit)
            if not isinstance(data, bytes):
                raise IntakeError("Connector must return measured bytes")
            if len(data) > limit:
                raise OSError("File exceeds receipt byte limit; supply a bounded readable extract")
            sha = hashlib.sha256(data).hexdigest()
            sources.append(MeasuredInput(file.file_id, file.version, file.provenance, sha,
                                         data, freeze(_inspect(file, data))))
            entry.update(access="accessible", sha256=sha, size_bytes=len(data))
            total += len(data)
        except FileNotFoundError:
            entry.update(access="missing", access_reason="Supplied file does not exist; provide its accessible location")
        except (OSError, PermissionError) as exc:
            # Never copy arbitrary connector exception text (it may contain secrets).
            reason = str(exc) if read_bytes is None and not isinstance(exc, PermissionError) else "Reference could not be read; provide authorized accessible bytes"
            entry["access_reason"] = reason
        entries.append(entry)
    record = {"kind": "submission", "schema_version": VERSION,
              "artifact_id": f"{task_id}:submission", "artifact_version": input_version,
              "provenance": "mock" if any(f.provenance == "mock" for f in files) else "supplied",
              "binding": {"task_id": task_id, "task_version": task_version,
                          "input_version": input_version, "input_digest": "0" * 64},
              "original_request": original_request, "files": entries, "received_at": received_at}
    record["binding"]["input_digest"] = input_digest(record)
    return Receipt(freeze(checked(record)), tuple(sources))
