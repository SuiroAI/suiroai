# DSC-24 retail MVP contracts

Snapshot `0.1.0-draft.3` is agreed by DSC-3 and DSC-26 and released as the pinned MVP development interface. Exact agreement is recorded in [COORDINATION.md](COORDINATION.md); path ownership is acknowledged.

This component supplies interface definitions, consistency checks and five small mock examples. It does not implement an analytical pipeline or demonstrate supported Codex/OpenAI Data execution.

- [Contract meanings and field explanations](CONTRACT.md)
- [JSON Schema](../../src/suiroai/contracts/schema/retail-contract.schema.json)
- [Complete field index](FIELD_GUIDE.md)
- [Five mock component examples](../../examples/contracts/v0.1.0/)
- [Actual local source reconciliation](audit/reconciliation.json)
- [Unresolved material data semantics](audit/source-semantics.md)
- [Regression tests](../../tests/contracts/test_contract.py)

From the application/worktree root, with Python 3.11+ and the DSC-3-owned jsonschema dependency installed:

```sh
PYTHONPATH=src python3 -m suiroai.contracts examples/contracts/v0.1.0/*.json
PYTHONPATH=src python3 -m unittest discover -s tests/contracts -p 'test_*.py'
PYTHONPATH=src python3 tests/contracts/build_examples.py
python3 docs/contracts/audit/reconcile_sources.py --data-root /Users/ceverson/Development/SuiroAI/data/retail_mvp/sales_2022_2025
```

Consumer imports are `suiroai.contracts.validate_record` (one message) and `validate_handoff` (a closed current task/approval/artifact graph with checked external references). `validate_bundle` additionally enforces mock-fixture packaging. No function grants consent, advances a checkpoint or authenticates a verifier. The caller independently checks external bytes, source/time correctness, actual execution and checker authority.

All example approvals, scores, checks and quantities are invented and marked mock, including external references. External mock digests identify included fixture markers; inline-message digests identify canonical JSON. The separate audit reads real local files and establishes no forecasting quality. Drive IDs/sizes come from the local manifest; remote contents were not hash-verified.

DSC-3 owns manifests/tooling. DSC-24 changes only its four allocated subtrees. Work is isolated at `/private/tmp/suiroai-dsc24` on `codex/dsc-24-contracts`, based on foundation `7e1dbb531a20f0ad4e4f82ec5764177e87550b3c`. No source datasets, DSCraft interfaces, parent code, issue statuses, merges, deployments or external publications are changed by this component.
