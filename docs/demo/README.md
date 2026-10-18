# DSC-31 demonstration preparation

**Preparation only. No retail recording, analytical run, successful restocking
demonstration or DSC-31 acceptance is claimed.** Start with the
[recording script](RECORDING_SCRIPT.md), then the [capture checklist](CHECKLIST.md).
The [evidence area](../../evidence/demo/README.md) contains an unfilled index
template, not completed run evidence.

## Source and ownership

Prepared against user-designated `origin/nightly`
`7af5a855ea98a47d332b2428bc1325f8154eb49e` on October 18, 2026.
The live [DSC-31 issue](https://linear.app/gr3enarr0w/issue/DSC-31),
[DSC-3](https://linear.app/gr3enarr0w/issue/DSC-3),
[DSC-24](https://linear.app/gr3enarr0w/issue/DSC-24),
[DSC-30](https://linear.app/gr3enarr0w/issue/DSC-30) and
[single-case contract](https://linear.app/gr3enarr0w/document/retail-mvp-single-restocking-case-shared-data-and-implementation-72e8278521db)
were read through connected Linear. Linked Drive/Miro content was not read
through those services in this assignment; local provenance manifests were read.

The architecture owner's published [allocation](../architecture/OWNERSHIP.md)
reserves application-relative `docs/demo/` and `evidence/demo/` for DSC-31;
this component acknowledges and uses exactly those paths. A fresh acknowledgment
request was sent to the actual DSC-3 session
`01a14ad0-4645-7661-b396-a295d232196e`; sending it is not a received acknowledgment.
No shared interfaces, parent controls, dependencies, DSCraft or datasets change.
The [agreed snapshot](../contracts/SNAPSHOT.json) is `0.1.0-draft.3`, schema
SHA-256 `1d4615cf03d571d3ba9cc6df34e5848b109918d3b0274b7007abc8ce1544ed46`.
DSC-24/3 own contract changes; DSC-10 owns transition/checkpoint changes.

## Recording gate at the reviewed nightly revision

Actual recording waits for working integration through verified DSC-30 delivery.
Component tests and examples permit preparation but do not open this gate.
Recheck these versioned sources on the eventual recording revision:

| Gate | Current evidence / owner action needed |
| --- | --- |
| Approved retail invocation | [Native boundary](../integration/NATIVE_BOUNDARY.md) and [adapter](../integration/ADAPTER.md) establish real isolated synthetic Codex/Data execution on the reviewed macOS host, CLI `0.163.0`, Data `1.0.11`. The approved retail chain has not executed. Engineering probe commands are not the retail launcher. |
| Safe preparation and historical availability | [Preparation interface](../preparation/INTERFACE.md) and [parent gates](../parent/COORDINATION.md) document rejection of derived development release and absent genuine information-availability evidence. DSC-24/3/10/26/27 must resolve this without releasing raw December records to development. |
| Feature-generation context | The parent gates require a valid release/availability mechanism for derived task, EDA and development-error summaries. Full-history QA must not become LLM context. |
| Scoreable target | [Modeling status](../modeling/README.md) retains unknown sparse dates and incomplete daily targets. Genuine target/completeness/availability evidence is needed; source row counts do not establish scoreable horizons. |
| Numerical approval before wording | [Replenishment integration](../replenishment/INTEGRATION.md) documents the missing same-task numerical check/parent approval/resume checkpoint before humanizing. DSC-10/24/3 own that bridge. |
| Independent delivery | [Verification coordination](../verification/COORDINATION.md) and parent gates require genuine trusted callbacks, check-only native transport, current approvals and actual output readback. |

The parent already supports the documented frozen-bundle/manifest/plan/rule release
follow-up; do not list that historical limitation as an unresolved gate.
The supported native profile uses experimental protocol fields and host pins.
Do not claim portability or verified gateway routing from the engineering probe.

## Bounded preparation deliverable

One supplied sales package plus its synthetic operational supplements, historical
decision date **November 30, 2025**, `product_unit`. No app launch, executable,
additional dataset suite, unrelated task or independent phase agents is required.
Routine analytical progress remains internal; the final customer report contains
the relevant findings and measured results. This runbook's reviewer views are
internal evidence inspection, not customer progress features.

No real invocation or recording was attempted in this preparation. Missing-data
guidance, measured validation failure, execution failure and a successful
illustrative list remain distinct. Do not close DSC-31/56/9 from this deliverable.

## Preparation verification

On October 18, 2026, Python `3.13.0`, jsonschema `4.25.1`, pytest `9.0.2`:

- `PYTHONPATH=src python3 -m pytest tests -q`: **610 passed, 632 subtests passed**.
  These existing tests establish regression compatibility, not a recorded run.
  An earlier `--import-mode=importlib` invocation failed collection because
  component fixture helpers use top-level imports; ordinary collection passed
  without shared configuration changes or excluded tests.
- All seven hashes in `docs/contracts/SNAPSHOT.json` matched; all five local
  input byte sizes/hashes matched the existing generation manifest. These were
  read-only byte checks, not data preparation or measured analytical results.
- Local Markdown links/code fences and all 15 pending CSV rows checked. Two
  read-only subagents reviewed temporal safety, gates, interfaces and capture
  sequence; their sequencing/classification/reproducibility corrections were
  incorporated. They do not supply runtime parent/verifier authority.
