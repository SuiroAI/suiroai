# SuiroAI retail MVP

This independent Python application supports implementation of one historical retail restocking case. The current foundation contains package configuration and reviewed architecture; it does not execute the customer workflow.

Use Python 3.11 or later. From this directory, `uv sync --locked` installs the foundation from the committed lockfile. `uv run --no-sync python -c "import suiroai"` checks package import. There is no customer executable, server or demo runner in this assignment.

- [Architecture and integration blockers](docs/architecture/ARCHITECTURE.md)
- [Exclusive component ownership](docs/architecture/OWNERSHIP.md)
- [Actual owner acknowledgments and interface status](docs/architecture/COORDINATION.md)

DSC-3 alone owns package manifests, lockfiles and shared infrastructure. The `jsonschema` dependency was requested by DSC-24 for its JSON Schema Draft 2020-12 validation; concrete schemas/examples belong to DSC-24. No analytical execution, LangChain/LangGraph or DSCraft dependencies are assumed by this foundation. Owners request additional dependencies through DSC-3 after identifying their implementation needs.

The sibling `../dscraft/` repository is a separate library and is unchanged. Source data remains at `../data/retail_mvp/sales_2022_2025/`; it is neither packaged nor silently loaded as customer input. Isolated worktrees must reference the actual approved input artifacts explicitly, since sibling paths are not a transport contract. Keep generated runs in ignored `artifacts/<task-id>/<run-id>/`, and commit only synthetic/example evidence safe for the confirmed private repository. Never commit raw customer data, credentials or generated artifacts by default.

This repository contains only the application and its own documentation. Workspace-level `docs/mvp/` files point to the canonical architecture here. Contract-only tests or mocks do not establish supported Codex/Data execution, a verified restocking report, MVP acceptance or broader V1 completion.
