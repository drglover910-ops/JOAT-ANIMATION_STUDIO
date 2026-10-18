# J.O.A.T. Animation Studio

File version: 1.0.0.

This existing private repository is intended to become the Main Assistant
repository when the owner renames it. No rename or separate Studio repository is
part of this release. It currently captures the existing Hugging Face implementation. It does not
replace the running studio or migrate its storage. `releases/audited_baseline_v1.0.0.json`
records original repository revisions, every captured file hash and excluded
resources. Canonical images, generated media, conversations and credentials stay
in their existing private stores.

Main Assistant coordinates company-wide requests. Director owns creative studio
work and the eventual studio UI. Executive/Studio Control hosts twenty distinct
department roles; the private renderer and Reference Lab remain separate GPU
services. The ACE music lab remains paused unless explicitly needed.

Shared guidance lives in `shared/`, with byte-identical deployment copies under
`apps/main` and `apps/control`. It is reviewed, bounded evidence retrieval, not an
autonomous learning system or a grant of creative/QC/spending authority.

Run the CPU checks:

```sh
python scripts/sync_shared.py --check
python -m unittest discover -s tests -v
```

See [architecture](docs/architecture.md), [release and rollback](docs/rollback.md),
and the [audit](docs/JOAT_STUDIO_AUDIT_v1.0.0.md). Gradio integration checks use the
existing Python 3.12 development environment with pinned app dependencies. Running
an app does not authorize inference. Keep production held during source checks.
