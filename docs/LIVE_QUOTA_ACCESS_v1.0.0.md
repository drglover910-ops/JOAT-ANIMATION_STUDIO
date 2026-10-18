# Live quota access checkpoint

File version: 1.0.0. October 18, 2026.

Main Assistant 2.1.103 is deployed at HF revision
72328a27cfc8a64f8173111f3e3a5faf79756d83, with source readback verified.
84 CPU tests passed. No GPU generation or paid inference ran in this milestone.
The approved 90-second film remains unfinished; its story, cast, spoken words,
timing and original one-reference mission are unchanged.

Further inspection of the official Hub OpenAPI document discovered the read-only
GET /api/spaces/zero-gpu/quota endpoint. This supersedes the earlier limited
research in QUOTA_VISIBILITY_v1.0.0.md: absence from the installed SDK did not
establish absence from the API. The API defines current as remaining seconds,
base as total seconds, and resetsAt as the reset timestamp. Credits are separate.

The deployed reader verifies account identity, preserves observation timestamps,
and exposes a no-GPU live-quota button. Both existing service credentials returned
HTTP 403 and report no user.billing.read permission. Main's specialist credential
is the existing token labeled JOAT-Main-Assistant. The other credential, labeled
Workbench-Wan22-Inference, should remain untouched. Evidence is in
releases/live_quota_scope_result_v1.0.0.json; no credential values are saved.

Owner action: open https://huggingface.co/settings/tokens, find
JOAT-Main-Assistant, edit its permissions, and enable read-only billing/usage
(user.billing.read). Preserve all existing permissions. Save without rotating or
creating a token; no token copying into chat or Spaces is needed. Retest the
quota GET afterward before claiming live access works. Billing write permission
is not requested. The observed denial plus missing scope motivates this step;
success remains unverified until the retest.

Six exact supplemental scene-reference requests are pinned in
apps/main/joat_style001_reference_supplement.json. Their append-only authorization
preserves the original mission. Execution requires a fresh successful provider
quota read and headroom, one attempt per request, and zero paid-credit authority.
No supplemental request was submitted. Local reservations do not lock account
quota against use by other applications and are not a provider spending cap.
Director retains studio creative/UI ownership; Main remains the company-wide
coordinator. Control's GPU hold remains in place.
