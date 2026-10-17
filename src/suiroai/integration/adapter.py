"""DSC-26 stage boundary; DSC-10 retains all checkpoint decisions.

Customer dispatch is deliberately blocked by NativeHost until native read
isolation has been demonstrated. Synthetic probes do not override that gate.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import uuid

from suiroai.contracts import VERSION, record_ref, validate_handoff, validate_record
from .artifacts import ArtifactStore, read_stage_file
from .native import NativeHost


class AdapterRejected(ValueError):
    """Untrusted or invalid handoff: no worker was dispatched."""


def _refs(value):
    if isinstance(value, dict):
        if set(value) == {"artifact_id", "version", "sha256", "provenance"}:
            yield value
        else:
            for item in value.values():
                yield from _refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _refs(item)


def _key(ref):
    return json.dumps(ref, sort_keys=True)


def _check_snapshot():
    from suiroai.contracts import validation
    root = Path(validation.__file__).parent
    expected = {
        root / "schema/retail-contract.schema.json":
            "1d4615cf03d571d3ba9cc6df34e5848b109918d3b0274b7007abc8ce1544ed46",
        root / "validation.py":
            "aecca19351e368e982ef014639c3f83120064fe1c480109fb41d3c9e9129368a",
    }
    if VERSION != "0.1.0-draft.3" or any(
            hashlib.sha256(path.read_bytes()).hexdigest() != sha
            for path, sha in expected.items()):
        raise AdapterRejected("DSC-24 snapshot differs; owner agreement required")


class StageAdapter:
    """Accept existing immutable task records; never form or amend a task.

    ``parent_permits`` is supplied by the trusted DSC-10 process. It authenticates
    the exact stage-request reference independently of worker-authored JSON.
    Handoff refs include the current approval chain and upstream stage evidence;
    external refs must already exist in this measured store, not merely a list
    of caller-provided hashes. Mock handoffs are rejected by default.
    """

    def __init__(self, store: ArtifactStore, *, work_root: Path,
                 parent_permits, host=None, ceiling_seconds=300,
                 allow_mock_handoffs=False):
        if not callable(parent_permits) or not 0 < ceiling_seconds <= 3600:
            raise ValueError("trusted parent verifier and finite ceiling required")
        self.store = store
        self.work_root = Path(work_root)
        self.parent_permits = parent_permits
        self.host = host or NativeHost()
        self.ceiling_seconds = ceiling_seconds
        self.allow_mock_handoffs = allow_mock_handoffs

    def execute(self, request_ref, *, handoff_refs, external_refs=(),
                cancellation: threading.Event | None = None):
        started = time.monotonic()
        _check_snapshot()
        handoff_refs, external_refs = list(handoff_refs), list(external_refs)
        if len(handoff_refs) > 128 or len(external_refs) > 256:
            raise AdapterRejected("handoff reference count exceeds adapter bound")
        request = self.store.read_record(request_ref)
        if request.get("kind") != "stage_request" or validate_record(request):
            raise AdapterRejected("invalid stage request")
        if self.parent_permits(deepcopy(request_ref)) is not True:
            raise AdapterRejected("DSC-10 did not authorize this exact stage request")
        records = [self.store.read_record(ref) for ref in handoff_refs]
        records = [r for r in records if record_ref(r) != request_ref] + [request]
        if not self.allow_mock_handoffs and any(r["provenance"] == "mock" for r in records):
            raise AdapterRejected("mock handoff cannot authorize real execution")
        # Measure referenced external bytes even though validate_handoff alone
        # only checks graph consistency. Reading occurs in the trusted adapter.
        total = 0
        for ref in external_refs:
            total += len(self.store.read_bytes(ref))
            if total > self.store.max_total_bytes:
                raise AdapterRejected("handoff external bytes exceed adapter bound")
        known = {_key(record_ref(r)) for r in records} | {_key(r) for r in external_refs}
        if any(_key(ref) not in known for r in records for ref in _refs(r)):
            raise AdapterRejected("handoff contains unresolved artifact references")
        executions = [r for r in records if r.get("kind") == "execution_contract"]
        if len(executions) != 1:
            raise AdapterRejected("one current execution contract required")
        execution = executions[0]
        # Exhaustion is an inspectable adapter outcome, not a dispatch. Shared
        # validator intentionally also rejects exhausted requests for dispatch.
        limit_errors = {
            "stage cannot dispatch with exhausted attempts or time",
            "model stage cannot dispatch with exhausted candidate budget",
            "feature stage cannot dispatch with exhausted feature budget",
            "stage request deadline exceeds remaining execution bound",
        }
        errors = validate_handoff(records, external_refs)
        exhausted = request["remaining_limits"]["max_execution_seconds"] == 0 or \
            request["remaining_limits"]["max_stage_attempts"] == 0
        exhausted |= request["stage"] in {"initial_baseline_evaluation", "comparison_and_freeze"} and \
            request["remaining_limits"]["max_candidates"] == 0
        exhausted |= request["stage"] == "llm_features" and \
            request["remaining_limits"]["max_llm_feature_definitions"] == 0
        remaining_errors = [e for e in errors if not (exhausted and e in limit_errors)]
        if remaining_errors:
            raise AdapterRejected("; ".join(remaining_errors))
        provenance = "mock" if any(r["provenance"] == "mock" for r in records) else "derived"
        self.work_root.mkdir(parents=True, exist_ok=True)
        attempt_root = Path(tempfile.mkdtemp(prefix="stage-", dir=self.work_root))
        audit = {"request_ref": request_ref, "customer_model_turn_requested": False,
                 "mock_handoff": provenance == "mock", "events": [], "published_refs": [],
                 "phase": "pre_dispatch"}

        def failure(code, reason):
            audit["phase"] = "execution_failed"
            audit["events"].append({"error_code": code, "reason": reason})
            audit["stage_outputs_accepted"] = False
            audit["working_directory_released"] = False
            evidence = self.store.put_bytes(
                "adapter-audit-" + uuid.uuid4().hex, 1, provenance,
                (json.dumps(audit, sort_keys=True, indent=2) + "\n").encode())
            result = self._result(request, request_ref, provenance)
            result.update(outcome="execution_failed", evidence_refs=[evidence], failure={
                "stage": "adapter_execution", "error_code": code, "reason": reason,
                "scope_limitation": "This MVP could not produce a reliable solution with the supplied data/scope in this stage.",
                "evidence_refs": [evidence]})
            if validate_record(result):
                raise AdapterRejected("adapter generated invalid failure envelope")
            self.store.put_record(result)
            return result

        if cancellation is not None and cancellation.is_set():
            return failure("cancelled", "Cancelled before native dispatch")
        if exhausted:
            return failure("budget_exhausted", "Parent supplied an exhausted stage limit; no turn started")
        deadline = datetime.fromisoformat(request["deadline"])
        seconds = min((deadline - datetime.now(timezone.utc)).total_seconds(),
                      request["remaining_limits"]["max_execution_seconds"],
                      self.ceiling_seconds - (time.monotonic() - started))
        if seconds <= 0:
            return failure("timeout", "Stage deadline expired before native dispatch")
        monotonic_deadline = time.monotonic() + seconds

        def stop_reason():
            if cancellation is not None and cancellation.is_set():
                return "cancelled", "Cancelled before output acceptance"
            if time.monotonic() >= monotonic_deadline or datetime.now(timezone.utc) >= deadline:
                return "timeout", "Stage deadline expired before output acceptance"
            return None
        try:
            manifest = self.store.stage_released(request["released_input_refs"], attempt_root / "work")
            prompt = self._prompt(request, request_ref, execution, records, manifest)
            seconds = min(monotonic_deadline - time.monotonic(),
                          (deadline - datetime.now(timezone.utc)).total_seconds())
            if seconds <= 0:
                return failure("timeout", "Stage deadline expired during input staging")
            run = self.host.execute(cwd=attempt_root / "work", prompt=prompt,
                evidence_dir=attempt_root / "native", timeout_seconds=seconds,
                cancellation=cancellation, mode="customer")
            audit["native"] = run.evidence
            audit["thread_id"], audit["turn_id"] = run.thread_id, run.turn_id
            audit["customer_model_turn_requested"] = bool(run.turn_id)
            if run.outcome != "completed":
                return failure(run.error_code, run.message)
            if run.mode != "customer":
                return failure("integrity_error", "Engineering execution cannot satisfy a customer stage")
            if stop := stop_reason():
                return failure(*stop)
            for entry in manifest["artifacts"]:
                data = read_stage_file(attempt_root / "work", entry["relative_path"])
                if hashlib.sha256(data).hexdigest() != entry["byte_sha256"]:
                    return failure("integrity_error", "Worker changed a released input")
            # Native completion alone never establishes analytical success.
            return self._retrieve(request, request_ref, provenance, attempt_root / "work",
                                  records, external_refs, audit, failure, stop_reason)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return failure("integrity_error", str(exc))

    @staticmethod
    def _result(request, request_ref, provenance):
        return {"kind": "stage_result", "schema_version": VERSION,
            "artifact_id": "adapter-result-" + uuid.uuid4().hex, "artifact_version": 1,
            "provenance": provenance, "binding": deepcopy(request["binding"]),
            "run_id": request["run_id"], "stage": request["stage"], "attempt": request["attempt"],
            "execution_contract_ref": deepcopy(request["execution_contract_ref"]),
            "stage_request_ref": deepcopy(request_ref), "parent_decision": None,
            "outcome": "execution_failed", "failure": None, "output_refs": [],
            "evidence_refs": [], "gaps": [], "final_validation_result_ref": None}

    @staticmethod
    def _prompt(request, request_ref, execution, records, manifest):
        from suiroai.contracts import schema_validator
        proposal = next(r for r in records if r["kind"] == "task_proposal")
        payload = {"goal": proposal["goal"], "output": proposal["output"],
            "binding": request["binding"], "stage_request": request,
            "stage_request_ref": request_ref,
            "result_schema": schema_validator().schema,
            "as_of_context": execution["temporal_plan"],
            "target_policy": execution["target_policy"],
            "acceptance_rule": execution["acceptance_rule"],
            "material_assumptions": execution["source_assumptions"],
            "allowed_actions": execution["allowed_actions"], "released_files": manifest}
        return ("Use OpenAI Data for this single parent-authorized stage of the existing approved task. "
            "Do not redefine its goal/output or advance another checkpoint. Read only released files. "
            "Keep routine progress internal. Return actionable gaps separately from measured validation "
            "failure and execution failure. Never claim unexecuted code succeeded. "
            "Write stage-result.json matching the shared stage_result schema, with parent_decision null; "
            "write artifact-manifest.json as a list of {ref,path,encoding} entries for each new artifact "
            "(encoding bytes or record). Paths are relative to this stage directory. "
            "Keep bindings/versions unchanged and retain actual code and execution evidence.\n" +
            json.dumps(payload, sort_keys=True))

    def _retrieve(self, request, request_ref, provenance, root, records, external_refs, audit, failure,
                  stop_reason=lambda: None):
        def read_relative(name):
            return read_stage_file(root, name, max_bytes=self.store.max_bytes)
        entries = json.loads(read_relative("artifact-manifest.json"))
        if not isinstance(entries, list) or len(entries) > 100:
            raise ValueError("invalid or exhausted artifact manifest")
        fetched, new_records, pending, identities = [], [], [], set()
        total_bytes = 0
        for entry in entries:
            data, ref = read_relative(entry["path"]), entry["ref"]
            total_bytes += len(data)
            if total_bytes > self.store.max_total_bytes:
                raise ValueError("output aggregate byte limit exhausted")
            if ref["provenance"] != provenance:
                raise ValueError("worker output provenance mismatch")
            identity = (ref["artifact_id"], ref["version"])
            if identity in identities:
                raise ValueError("duplicate worker output identity")
            identities.add(identity)
            if entry["encoding"] == "record":
                record = json.loads(data)
                if record_ref(record) != ref or validate_record(record):
                    raise ValueError("worker record hash/schema mismatch")
                if record["kind"] in {"submission", "task_proposal", "task_approval", "execution_contract", "stage_request", "stage_result"}:
                    raise ValueError("worker cannot author task or permission records")
                if record.get("binding") != request["binding"] or record.get("run_id") != request["run_id"]:
                    raise ValueError("worker changed version/run binding")
                if any(record.get(key) is not None for key in ("parent_decision", "parent_review", "parent_authorization")):
                    raise ValueError("worker cannot author a parent decision")
                actual = record_ref(record)
                new_records.append(record)
            elif entry["encoding"] == "bytes":
                actual = dict(ref, sha256=hashlib.sha256(data).hexdigest())
            else:
                raise ValueError("unknown artifact encoding")
            if actual != ref:
                raise ValueError("retrieved artifact differs from worker reference")
            fetched.append(ref)
            pending.append((entry["encoding"], ref, data))
        result = json.loads(read_relative("stage-result.json"))
        expected = self._result(request, request_ref, provenance)
        # Stage envelope identity belongs to the adapter, never a worker's
        # attempt to replace an already stored parent/result record.
        result["artifact_id"] = expected["artifact_id"]
        result["artifact_version"] = 1
        for field in ("binding", "run_id", "stage", "attempt", "execution_contract_ref",
                      "stage_request_ref", "parent_decision", "provenance"):
            if result.get(field) != expected[field]:
                raise ValueError("worker stage result changed " + field)
        errors = validate_handoff(records + new_records + [result], external_refs + fetched)
        if errors:
            raise ValueError("; ".join(errors))
        if any(ref not in fetched for ref in result["output_refs"]):
            raise ValueError("stage outputs must be retrieved from this actual attempt")
        # Nothing becomes a trusted stage output until the entire handoff passes.
        # Preflight immutable identities before publishing any of this batch.
        for encoding, ref, data in pending:
            self.store.check_identity(ref)
        self.store.check_identity(record_ref(result))
        if stop := stop_reason():
            return failure(*stop)
        for encoding, ref, data in pending:
            if encoding == "record":
                self.store.put_record(json.loads(data))
            else:
                self.store.put_bytes(ref["artifact_id"], ref["version"], ref["provenance"], data)
            audit["published_refs"].append(ref)
        # Retain native provenance as evidence without presenting routine logs.
        audit["phase"] = "retrieval_checks_passed_before_parent_decision"
        native_ref = self.store.put_bytes("native-audit-" + uuid.uuid4().hex, 1, provenance,
            (json.dumps(audit, sort_keys=True, indent=2) + "\n").encode())
        result["evidence_refs"].append(native_ref)
        if stop := stop_reason():
            return failure(*stop)
        self.store.put_record(result)
        if stop := stop_reason():
            return failure(*stop)
        return result
