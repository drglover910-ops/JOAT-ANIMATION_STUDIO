# JOAT implementation instructions

File version: 1.0.0.

Preserve the approved architecture, canonical assets, immutable source packets,
creative decisions, acceptance checks and secret bindings. Main Assistant is the
company-wide coordinator. Director owns studio creative workflows and the future
studio UI; Executive/Studio Control hosts its consolidated specialist execution.
All twenty departmental roles remain distinct even though they share a host.

Use the existing checkout, not a new worktree. Each changed or uploaded file must
contain its own incremented version. Shared sources live in `shared/`; synchronize
deployment copies with `scripts/sync_shared.py` and verify them before release.
Never turn a lesson, plan, or technical result into execution or final QC approval.
No startup inference, automatic costly retries, secret resets or paid hardware.
GPU and credit limits require their own explicit authorization.

HF remains the deployment target; GitHub is source/release history. Do not commit
credentials, conversation databases, generated media or canonical reference images.
Releases must record exact HF revisions and source hashes. Original reference
resources remain in their existing HF repositories; see the baseline manifest.

Run `python -m unittest discover -s tests -v` and shared-source consistency checks.
Use the existing pinned application environments for Gradio integration checks.
Do not start inference or unpause a production hold just to test CPU changes.
