# DSC-26 ownership acknowledgment

2026-10-17 · revision 0.1.0

DSC-26 accepts DSC-3's architecture revision 0.1.0, the independent application Git root `/Users/ceverson/Development/SuiroAI/suiroai`, and these exclusive application-relative paths:

- `src/suiroai/integration/`
- `tests/integration/`
- `docs/integration/`
- `evidence/integration/`

DSC-3 confirmed these paths and supplied foundation commit `7e1dbb531a20f0ad4e4f82ec5764177e87550b3c` through the architecture session `01a14ad0-4645-7661-b396-a295d232196e`. This work uses branch `codex/dsc-26-capability` in `/private/tmp/suiroai-dsc26`. No remote is configured, and DSCraft remains outside this repository.

DSC-24 session `01a14ad0-5384-7bb3-bc03-afd35c43ea2f` acknowledged the integration coordination request. Its concrete schema was a draft pending review at the time of discovery. No local shared schema or mock adapter was created to fill that gap.

DSC-24 owns schemas; DSC-10 owns parent decisions. Shared source/manifests and other owners' checkouts remain unchanged. Discovery files do not claim interface stability or analytical acceptance. See [DISCOVERY.md](DISCOVERY.md) for actual evidence and blockers.
