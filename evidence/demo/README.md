# DSC-31 capture evidence — not yet recorded

This directory currently contains preparation instructions and a blank
[human index template](index.template.csv). **No recording or completed retail
evidence bundle exists here.** The [script](../../docs/demo/RECORDING_SCRIPT.md)
and [checklist](../../docs/demo/CHECKLIST.md) specify future capture.

Copy the template to the approved restricted capture location for a genuine run.
It is an editorial locator, not a shared wire schema, runtime evidence record or
verifier decision. Row labels map to script/checklist requirements, not new
contract enum values. Blank fields and `not_recorded` mean no proof exists;
never populate an actual score, approval, hash or recording ref from an example.

For each real row, retain:

- The requirement and immutable shared evidence-record reference where applicable.
- Exact task/task-version, input-version/digest, proposal-version/digest,
  approval-version/digest, execution-contract ref and run/stage/attempt from the
  referenced records; preserve source and producer lineage.
- Artifact reference (`artifact_id`, integer `version`, `sha256`, `provenance`)
  plus resolvable retained location. Multiple artifacts/checks need separate rows.
- Expected versus actual check, real/mock evidence mode, named verifier,
  `accepted`/`rejected`/`needs_evidence` decision and verification timestamp from
  actual evidence; use `not_recorded` only as editorial status before review.
- Original recording reference/hash and segment timecodes; reconcile native/event
  timestamps, report readback and bytes. Missing success evidence belongs in the
  limitations column and bundle's outcome note.

Use DSC-24's existing [evidence_record](../../docs/contracts/FIELD_GUIDE.md) for
approved-run checks: `requirement_id`, `requirement_source`, `checked_artifacts`,
`check`, `evidence_mode`, `verifier_decision`, `verifier`, `verified_at` and
`mock_limitation` alongside required identity/binding fields. Do not add recording
fields to that schema. Pre-signoff request/proposal/guidance has no approved run:
link submission/proposal-bound events/checks directly without inventing approval
or an execution evidence record. A genuinely executed run can use synthetic
operational inputs: `evidence_mode=real` does not change their provenance to
supplied facts. Mock chains remain mock throughout downstream capture.

Keep producer artifacts in their original approved namespaces under
`artifacts/<task-id>/<run-id>/`; the capture index references immutable originals
or hash-identical retained copies. Preserve native invocation receipts, stage
manifests/results, actual code/config, LLM feature provenance, measured metrics,
frozen manifest/forecast, final output and parent/verifier decisions. Retain
recording bytes in the authorized restricted bundle; omit credentials and bulk
reasoning/skill contents. Do not commit customer raw inputs or recordings merely
because this directory is reserved. Publishing/sharing has its own authorization.

Bundle outcome notes must distinguish `not_recorded`, incomplete evidence,
missing-data guidance, measured validation failure, execution failure and verified
illustrative restocking success in plain language. These are editorial labels,
not new runtime outcomes. Failure-only evidence must enumerate absent success
artifacts. A successful native synthetic probe or component test remains evidence
only of its original limited claim and cannot fill retail-run rows.
