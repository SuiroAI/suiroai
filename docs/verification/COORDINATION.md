# DSC-30 development coordination

This branch implements only independent verification and permitted delivery in the published DSC-30 ownership allocation: `src/suiroai/verification/`, `tests/verification/` and `docs/verification/`. Shared schemas remain DSC-24-owned; parent transitions/approval remain DSC-10-owned. No DSCraft interfaces or shared infrastructure are changed to support this component.

## Source of truth

The branch starts from user-designated `nightly` commit `83f134f`. It consumes the development interface pinned in `docs/contracts/SNAPSHOT.json`:

| Item | Pinned value |
| --- | --- |
| Shared contract | `0.1.0-draft.3` |
| Contract owner commit | `dd3e0dda1b759ebe5439e78e8cf10e3374eb700b` |
| Schema SHA-256 | `1d4615cf03d571d3ba9cc6df34e5848b109918d3b0274b7007abc8ce1544ed46` |
| Scope | Agreed structural interface for parallel development; no real execution acceptance |

The existing architecture [ownership map](../architecture/OWNERSHIP.md) already reserves these exact DSC-30 paths and releases consumer development against draft.3. A fresh DSC-3 re-acknowledgment was requested for this work. That owner was waiting for approval and no fresh response was received; this document does **not** claim a new acknowledgment. The published allocation is the current write boundary. New shared-contract or parent changes must still go through their respective owners.

## Actual owner-session agreements

The implementation coordinator received the following agreements from the actual role sessions, rather than treating review subagents as those owners:

| Owner session | Agreed consumer boundary |
| --- | --- |
| DSC-29 thread `01a14cdf-5ac2-7940-8f10-d64b5520e972` | Independent checking consumes daily forecast evidence and receipts retaining both Order_Date and Expected_Arrival_Date. Unknown within-day arrival order uses conservative end-of-day treatment; totals alone do not prove absence of intervening shortages. |
| DSC-10 thread `01a14cdf-02ec-78d3-a17c-28d4d391a4ad` | Verification is check-only first; the parent reviews and authorizes afterward. Workers do not manufacture parent approval or publish from a producer pass flag. |

These are development agreements, not evidence of a real completed analytical run or customer delivery. Daily forecast, scope and product-name payload parsing is supplied explicitly through reviewed source readers. The consumer has no undocumented forecast format default and does not interpolate an aggregate into daily values.

## Implemented separation

Independent candidate evidence binds the exact unapproved quantity version. The parent subsequently owns approved quantities and the immutable candidate reference. Report verification binds that approved version and the current final-validation/frozen forecast references, stores checks without permission, and waits for parent authorization of the exact checked draft. Final publication uses the existing output surface and requires actual readback equal to approved UTF-8 bytes.

Arbitrary claims and customer prose have no general truth-checking schema in draft.3. Trusted independent callbacks must inspect actual evidence and the full narrative; missing reviewers block the response. Parent identity/currentness are likewise not proven by actor strings. Trusted parent authentication is an explicit application boundary, not a new external service or autonomous agent.

The missing-input example contains only submission and proposal. It has no approved execution binding or run. Preexecution guidance checks preserve this fact and return submission/proposal-bound checks for DSC-25/DSC-10; they do not fabricate a final-report packet.

## Development evidence and acceptance waits

See [README.md](README.md) for API contracts, meaningful negative checks and reproducible component/shared-contract test commands. Fixtures and test deliveries remain explicitly mock evidence. They cannot close DSC-30, promote synthetic assumptions to supplied facts or establish actual OpenAI Data capability.

Real delivery waits for genuine DSC-29 drafts/quantity/source evidence, current DSC-10 validation and quantity approvals, applicable preparation/feature/model artifacts, independent reviewers, authenticated source adapters, DSC-26 supported execution evidence and actual approved-output readback. A parent-reviewed terminal failure uses genuine failure evidence instead of successful quantity evidence. Any unresolved key remains an explicit exception; unresolved integration or authority gaps remain blockers.
