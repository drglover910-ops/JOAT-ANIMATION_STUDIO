---
title: Joat Reference Lab
emoji: 🎭
colorFrom: red
colorTo: green
sdk: gradio
sdk_version: 6.27.0
python_version: '3.12.12'
app_file: app.py
hf_oauth: true
pinned: false
license: apache-2.0
models:
  - Qwen/Qwen-Image-Edit-2511
---

<!-- README.md — FILE VERSION: 2.9 -->
# J.O.A.T. Reference Lab

README file version: **2.9**. App **2.9-approved-job-storage**; mission helper **1.0.2**;
approved job asset helper **1.0.1**. Each file keeps its own version counter.

## Standalone studio workflow

The Mission Reference Candidates and Approved Job References tabs do not require
GoHighLevel. Existing legacy GHL tools remain available as optional integrations;
their reconciliation and canonical registration safeguards are unchanged.
Canonical originals stay in the existing Character/Environment Masters.

Import the exact original candidate PNG and candidate_review.json. Prepare the
CPU-only save preview, check job/character/style/wardrobe/source hashes, explicitly
approve the image, then save. Approval automatically retains the selected bytes
and a source/approval manifest in the existing Hugging Face bucket. Image hash and
dimensions must match the candidate report and signed plan. A screenshot is not
an acceptable substitute. Generated images are job assets, not canonical identities
or production QC passes. No new image generation is needed for an approved image.

## Dedicated studio storage

Use the private existing-or-new studio bucket **Dezz-9-10/J.O.A.T.-Studio-storage**
at **/studio**, read/write in Reference Lab. All production Spaces receive the same
/studio path with permissions appropriate to their role. Mounting provides access;
actual per-department persistence/routing still needs application integration and acceptance.

Keep Main Assistant's original bucket and /data mount unchanged. During migration,
Reference Lab retains its old Main Assistant bucket /data mount for reading the source.
The Studio Storage Migration tab copies only /data/joat-studio approved-reference
records and generation-attempt claims to /studio/joat-studio. It does not copy private
/data/joat-main-assistant data, delete sources, generate images or grant new creative approvals.

Upload the original saved approved_job_reference.json, confirm the migration, then
click Copy studio records and verify (no GPU). Original image bytes, descriptor ID,
source hashes and owner approval are preserved. Destination URI and outer manifest
fingerprint change with explicit source-fingerprint migration lineage. Repeated migration
is idempotent; conflicting destination data is preserved and rejected, not overwritten.
The helper retains data descriptor version1.0.0 for stable approved IDs while code
file version advances to1.0.1; old approved records remain load-compatible.

Approved references remain under joat-studio/approved-references/<asset_id>.
Attempt claims migrate first to block duplicate provider calls. Only Reference Lab
writes approved-reference and reference-attempt namespaces; other department writers
must use their own output directories when their routing integration is implemented.
Mount read/write permission itself is bucket-wide, not a folder-level ACL.

Missing/unverifiable mounts fail closed. No temporary fallback is called durable.
No new secret is required for platform-managed mounts; existing model access is preserved.
Do not expose /data or /studio through Gradio allowed_paths. Bucket data is mutable;
verify destination readback and restart retention before retiring temporary old mounts.
Retain the old source copies until migration acceptance passes.

## Generation and cost controls

Qwen/Qwen-Image-Edit-2511, guidance 1.0, 50 steps, seed42 and CPU offload are unchanged.
The mission path requests 1024x576 and a 600-second GPU reservation; the original
single-image path retains 180 seconds. A reservation is not an actual cost estimate
or a guarantee of provider allowance. Generation requires explicit owner approval;
there is no automatic retry. New mission attempt claims persist in the bucket before
provider invocation and block repeat exact plans across container replacement.
PNG/review outputs remain temporary until approval/save; download them promptly.

## Status and next integration

CPU tests cover owner/approval gates, tamper rejection, scope binding, restart-style
reload, idempotent save and persistent generation claims. Live mount writes,
restart readback and Director → Supervisor → Worker approved-frame routing still
require acceptance. This update does not change old production packets or render
another video. Missing references are generated only for a real job after checking
existing individual images or verified card crops. Full panel indexing is pending.

## Attribution

Qwen Image Edit 2511 is developed by Qwen Team, Alibaba Cloud, under Apache 2.0.
https://huggingface.co/Qwen/Qwen-Image-Edit-2511
