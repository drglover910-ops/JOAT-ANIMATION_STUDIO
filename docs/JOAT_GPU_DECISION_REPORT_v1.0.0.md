# JOAT GPU infrastructure and production cost decision

File version: **1.0.0**. Research date: **October 19, 2026**. Scope: read-only infrastructure, model, pricing and production evidence audit. No production code, deployment, subscription, credit balance or hardware allocation was changed. No generation was requested.

## Decision

**Keep the working four-Space architecture. Do not buy a server now. Additional ZeroGPU credits are the lowest-disruption way to remove the immediate quota bottleneck.** For the existing 90-second commercial, allow a working compute estimate of **80–130 additional normalized GPU minutes**, equivalent to **$8–$13 if entirely paid**, with a checkpoint before spending beyond $10. Included time can reduce that cash cost. These are planning estimates, not a promise that $10 guarantees a finished commercial.

A **$10 credit purchase buys 100 extra normalized GPU minutes; $15 buys 150; $30 buys 300**, at the published $1/10-minute rate. This is separate from the $9/month PRO list price. Existing usable credits would reduce the amount that needs purchasing. A fresh balance was not accessible to this audit; do not purchase based on the historical balance below.

The recommended order is: finish the current film with strict reuse and a project spending cap; measure its accepted output cost; then benchmark one time-limited rental job carrying our exact model stack. Renting has a lower published compute-hour price, but porting and startup are real costs. Buying hardware before measuring sustained production demand would be premature.

## 1. Current infrastructure

Fresh owner-authorized metadata checks found **4 running and 22 paused Spaces** among the 26 known Spaces. None of these 26 currently reports paid dedicated GPU hardware. This is not an account-wide invoice or a guarantee about other services outside the inventory.

| Core Space | Current deployed version | Hardware / state | Responsibility |
|---|---|---|---|
| [Main Assistant](https://huggingface.co/spaces/Dezz-9-10/J.O.A.T.-Main-Assistant-Bot) | 2.1.114 | CPU Basic / running, private | Company-wide assistant, project requests, evidence review, owner approvals and signed handoffs |
| [Executive Producer / Studio Control](https://huggingface.co/spaces/Dezz-9-10/J.O.A.T.-Executive-Producer-Bot) | 1.2.26 | CPU Basic / running, private | Director authority, consolidated departments, production execution and future Studio interface |
| [Animation Studio renderer](https://huggingface.co/spaces/Dezz-9-10/J.O.A.T.-Animation-Studio) | 1.0.14 | ZeroGPU / running, private | LTX/ComfyUI video generation, native speaking/audio, optional refinement and reference controls |
| [Reference Lab](https://huggingface.co/spaces/Dezz-9-10/joat-reference-lab) | 2.19 | ZeroGPU / running, private | Qwen image editing and proposed job-specific scene references |

The optional ACE music Space is paused. Consolidation retained **20 logical department roles**; these are not 20 independently running servers. Main remains the coordinator and the Director remains the studio authority. Do not merge those responsibilities to save GPU quota: CPU consolidation does not reduce the diffusion work of a generated frame.

Shared approved production assets belong in the existing Studio storage under Executive authority. Main retains its separate storage and authorized shared access. Source references, approvals, content hashes, job descriptors, work orders, candidate receipts and final QC remain distinct. **GoHighLevel is disabled and is not required to operate the Studio.**

Live source revisions recorded in the audit:

- Main: `387691cda3093310049165bd018d18df77096894`.
- Control: `1e555450e8193f53957a2f547da6ec0ac1bd7eaf`.
- Renderer: `be1591ad2ad05c3af51f27fd671658d1873e15af`.
- Reference Lab: `70b1a703ece44977e2e771977357cf1a2889faab`.

The runtime API calls the ZeroGPU tier `zero-a10g`. That label does **not** prove the backing card is an A10G. Current public documentation specifies half/full RTX Pro 6000 Blackwell allocations.

## 2. Models, execution locations and reuse

| Workload / model | Where it executes | Cost/quota implications |
|---|---|---|
| **TenStrip/LTX2.3-10Eros**, `10Eros_v1-fp8mixed_learned.safetensors` | Renderer, local ComfyUI workflow on allocated ZeroGPU | Video and native actor speech consume ZeroGPU time. This is a custom LTX fine-tune, not interchangeable with every vanilla LTX API. |
| Gemma 3 12B FP8 text encoder, from `Comfy-Org/ltx-2` | Renderer | Part of the LTX conditioning pipeline; checkpoint about 13.2 GB. |
| Distilled LoRA `ltx-2.3-22b-distilled-lora-1.1_fro90_ceil72_condsafe.safetensors` | Renderer | Required by the current qualified workflow; retain exact file and configuration. |
| LTX spatial upscaler; Licon MSR LoRA; MelBandRoformer | Renderer optional components | Used only by selected workflows. Current film profile uses single-image i2v and skips refinement; do not turn these on automatically. |
| SulphurAI/Sulphur-2-base GGUF prompt enhancer | Renderer optional local model | Additional optional inference path. Locked CPU-compiled film prompts do not need it. |
| **Qwen/Qwen-Image-Edit-2511**, BF16, CPU offload, 50 steps | Reference Lab, GPU generation | Produces candidate scene images. Approval/storage on CPU does not make the preceding generation free. |
| **hexgrad/Kokoro-82M** | Control narration department, CPU | CPU narration, cached pipeline and voices. This does not replace native speaking/lip-sync qualification. |
| **ACE-Step/Ace-Step1.5** | Optional music Space, paused | No current film music-generation execution demonstrated by this audit. |
| **openai/gpt-oss-120b** | External HF Inference Providers, Main default | Main does not host this 120B model on CPU. Calls can use inference credits or paid inference. |
| **Qwen/Qwen3-VL-30B-A3B-Instruct**, DeepInfra default | External semantic video-reference analysis | Separate provider billing, not the local CPU frame extraction step. |
| **openai/whisper-large-v3-turbo**, HF Inference default | External reference transcription | Separate inference usage; local CPU QA also uses a different Whisper model. |
| **Systran/faster-whisper-small.en**, int8 | Local CPU development/review environment | Used for word verification; not evidence that Main hosts the same service. |

An optional external Qwen writer/planner Space appears in renderer configuration. It is unnecessary for the locked current script; calling another GPU Space can consume caller quota too.

**GPU needs:** production-speed LTX video and Qwen reference generation require accelerated compute with our current implementation. Neither application requires an always-on paid dedicated GPU. GPU is allocated for inference and released afterward. CPU-only diffusion might be technically possible with extensive offload, but no practical, quality-preserving CPU render path has been qualified here.

**CPU work:** script, shot planning, packet validation, storage/hash checks, reuse selection, image cropping, FFmpeg preparation, timeline assembly, titles, audio mixing, local narration, technical media QC and delivery packaging. Semantic analysis can still call paid external models even when the host itself is CPU Basic.

**Memory:** the main video checkpoint is approximately 29.2 GB on disk plus the 13.2 GB encoder and other components. Disk size is not measured peak VRAM. The current reference pipeline uses CPU offload. There is no measured minimum-VRAM qualification in this audit. Current ZeroGPU large is documented as 48 GB, xlarge as 96 GB; for an initial rental portability test, 80–96 GB is a prudent target. A 24/32 GB consumer card is not an assured drop-in replacement. Several cards' VRAM does not automatically become one shared memory pool.

**Waste and reuse findings:**

1. Several reference calls were rejected for composition, pose or framing. They consumed time despite producing unusable candidates. The latest rejected reference used about 7.41 GPU minutes. This is a quality/prompt bottleneck as well as a hardware bottleneck.
2. Reuse approved stills and accepted footage by hash, scope, character, wardrobe, location and performance. A smiling or curious reaction cannot silently substitute for an overwhelmed performance.
3. Renderer startup downloads model assets and custom dependencies before GPU inference; download time should not be counted as actual GPU usage. It does download optional assets, including the prompt enhancer, even when this film does not need them. That adds startup/storage overhead, not demonstrated duplicate GPU inference.
4. Warm disk caches already exist. Per-allocation loading/conditioning remains; persistent rental batching could amortize it, but no speedup has been measured.
5. Separate reference and video reservation paths exist. A shared account budget ledger would improve admission control and avoid concurrent jobs consuming the same observed allowance.
6. Do not remove a model merely because it was optional for this film. Make optional startup components profile-driven only after qualification.

## 3. Verified subscription, billing and quota

| Item | Evidence and limitation |
|---|---|
| Current subscription | Owner metadata confirms **PRO active**. Public list price **$9/month**; actual invoice, taxes or annual terms not visible. |
| Included ZeroGPU | Official current limits: **PRO 40 minutes**, Team **40/member**, Enterprise **60/member**. Reset occurs 24 hours after first GPU usage, rather than guaranteed midnight. |
| Extra ZeroGPU | Prepaid credits supported: **$1 per 10 additional GPU minutes**; provider can debit automatically once included allowance is exhausted. Our application currently authorizes **$0 paid usage**, so credits alone do not override its guard. |
| Allocation size | `large`: 48 GB, quota multiplier **1×**. `xlarge`: 96 GB, **2×**. A ten-minute xlarge allocation consumes twenty normalized quota minutes; do not budget it as ten. |
| Main and Control CPU | Both currently CPU Basic, **free**. Earlier CPU Upgrade is no longer the selected hardware. |
| Fresh exact balance | **Unavailable:** injected authorized token receives 403 from quota endpoint and billing page redirects to login. No fresh credit balance or current-month invoice verified. No new secret requested. |
| Latest saved quota receipt | October 19 at **03:13:43 UTC**: **512.216199 / 2400 seconds remaining**; recorded over-quota use **0**; stated reset **October 20 00:11:13 UTC** (October 19, 8:11 PM Eastern). Historical, not a live balance. |
| Historical billing record | October 17 observation: credits **$3.68**, period usage **$3.06**, of which Main CPU Upgrade **$3.03** and inference **$0.03**. The CPU charge matches approximately 101.05 hours × $0.03. Not a present balance or new charge. |
| Existing inference services | Main is configured for HF-routed language, vision and transcription APIs. Historical inference use was visible; a current per-service invoice was not. Current docs list **$2/month PRO included compute credits**; do not assume these remain unspent or add them twice to a budget. |

**Local admission control matters:** `joat_included_film_render.py` currently requires `420 × 2 + 120 = 960` seconds of headroom for a native shot, although current documentation lists large at 1×. The reference helper requires `600 + 120 = 720`. These are conservative application checks, not evidence that each generation consumes 7 or 10 minutes. The historical 512-second balance cannot pass either guard. Any change should verify actual SDK size and account-wide outstanding reservations first, not simply delete safety checks.

## 4. Strategy comparison

| Strategy | Cost and speed | Compatibility / quality | Limits, reliability and required changes |
|---|---|---|---|
| **A. Existing ZeroGPU + credits** | $0 included; then **$0.10/normalized GPU minute**. Measured 4-second actor candidate: about **$0.28** paid equivalent. Recent Qwen reference: **$0.74**. Queue/loading affects wall time. | Preserves the working custom model, native speech and controls. Same pipeline does not guarantee every output passes QC. | Shared queue and finite allocations; extra credits extend included quota. Add explicitly approved project cap/paid policy; no model migration. Best immediate path. |
| **B. Public developers' Spaces APIs** | ZeroGPU calls still use the authenticated caller's allowance; no proven free quota escape. Speed depends on that Space's queue. | Supported public endpoints may work, but exact custom weights, 96-input contract, controls and private references are not qualified. | Upstream changes, rate limits, author availability and privacy are outside our control. API adapter and equivalence tests needed. Not an immediate savings claim. |
| **C. Inference Providers / third-party model APIs** | Provider-dependent per-output or compute billing; exact video/reference prices not verified in this environment. Independent from ZeroGPU daily allowance. | HF metadata advertises Qwen Image Edit through fal-ai and Wavespeed. **No HF provider mapping advertised for our exact 10Eros or LTX-2.3 model IDs.** This does not prove no third party offers LTX. | Hosted Qwen still needs multi-reference, order, dimensions, seed and output qualification. Vanilla LTX cannot silently replace our fine-tune. Add provider adapters, error handling, privacy approval and cost receipts. |
| **D. Rent GPU only during production** | Verified HF Jobs examples: L40S 48 GB **$1.80/h**; A100 80 GB **$2.50/h**; RTX Pro 6000 96 GB **$2.75/h**. Jobs billed per minute. No speed benchmark yet. | Can carry exact weights and workflows if container/environment passes qualification. Best path toward compute independence without buying hardware. | Provisioning, cold setup, idle time and failures bill too. Need portable pinned runner, durable artifact upload, lifecycle controls and shutdown. Availability not guaranteed by a price listing. |
| **E. Own workstation/server** | Capital plus power, storage, maintenance and operation. No current retailer quotes verified. No measured generation speed on proposed hardware. | Exact pipeline possible with sufficient compatible memory/software; smaller quantized setups require new qualification. | Removes provider daily quota, introduces hardware/uptime/maintenance constraints. A network service adapter and security controls remain necessary. Not economical at today's small spend. |

Public API feasibility is conditional: public Gradio endpoints can be called without hosting a duplicate, when the author supports that route. **Public does not mean free, private, stable or equivalent.** The Qwen author's Space is currently ZeroGPU. A public Space named `WeReCooking/ltx-2.3-cpu` reports CPU Basic, but that name/hardware does not prove diffusion runs on CPU; it may delegate. Original fork lineage and complete feature parity were not established, so it is not recommended as a replacement.

Fresh HF model metadata confirms live hosted routes for gpt-oss-120b, Qwen VL and Whisper, consistent with external calls already configured. These are useful for their own tasks and do not generate our speaking film.

### Rental calculations

At $2.75/hour, **two RTX 96 GB job-hours cost $5.50; three cost $8.25; ten cost $27.50** before any separately applicable storage/service charges. Jobs CPU Basic is **$0.01/hour**, unlike free Spaces CPU Basic. Spaces dedicated GPUs also have published hourly prices; leaving one running continuously is a different cost profile: $2.75 × 24 × 30 = **$1,980/month**.

ZeroGPU overage is $6 per normalized hour at large, or $12 per wall-clock hour at xlarge. Comparing those numbers with $2.75/hour rental suggests a benchmark is worthwhile. **It does not establish equal throughput or lower finished-film cost:** large is half a card, rental may be a full different card, and job setup/billing differ.

For illustration only, if a four-second actor shot took the same 168.23 seconds on a rental RTX, active compute would cost approximately **$0.13**, versus $0.28 ZeroGPU equivalent. If a reference took the same 444.89 seconds, approximately **$0.34**, versus $0.74. These are arithmetic scenarios, not measured rental prices per accepted generation; cold startup and retries would add cost.

Runpod, Lambda, Vast, fal, Replicate and NVIDIA retailer/product price pages were inaccessible through this environment even after authorized network retry. No current prices from those vendors are presented as verified. There is no need to pretend an unverified advertised low hourly rate is a production quote.

## 5. Current commercial: remaining work and cost

The approved project remains **PROJECT-OTU-STYLE001-90S-001**, 18 shots, exactly 90 seconds, with locked wording, roles and revised timing. Cristu is the business owner, Founder delivers the product and Kiana is the customer. **A shorter 30-second alternative was discussed but has not replaced this approved film.**

Preserved progress includes the corrected five-second opening candidate, the four-second speaking Cristu candidate with exact CPU-ASR words, a six-second CPU graphic, 13 CPU narrator WAVs and five prepared UI graphics. Candidate evidence is not final film approval. Lip sync, performance, framing, continuity, dialogue audibility and final assembly still require QC.

Approximately **14 native video slots remain** under the original allocation. Phone/calendar inserts may reduce native work if CPU or existing-footage alternatives actually satisfy their shot requirements. Several missing reference compositions still need resolving; medium customer references do not satisfy a wide shot, and the latest two-person relief composition was rejected.

| Remaining GPU work | Planning range |
|---|---:|
| Native video slots | 35.5–56.5 minutes |
| 5–7 missing/corrected reference compositions | 32.5–56 minutes |
| Correction allowance | 10–20 minutes |
| Rounded practical total | **80–130 minutes** |

Working target: **100 additional minutes**. Variation comes from per-shot complexity, reference acceptance, native audio, allocation size, failures and corrections. CPU editing, titles and delivery are outside this GPU estimate.

- Entirely paid: **$8–$13** compute equivalent.
- If a fresh full 40-minute included allowance is available for this project: approximately **$4–$9** paid remainder.
- If the historical 8.54 minutes remained unchanged: approximately **$7.15–$12.15** paid remainder.
- These scenarios exclude other account use and unmeasured external inference charges. They are not a spending authorization or guaranteed completion cap.

**Immediate practical spending policy to approve later:** use included time first; permit at most **$10 additional project GPU spend**, stop and report at that cap; consider up to **$5 more only after reviewing accepted shots and the remaining estimate**. Do not preauthorize $30 just because it is available. Reconcile any existing credits before buying more. Preserve failed outputs; never automatically resubmit an unknown or aborted job.

For the earlier shorter-film discussion: 20 paid minutes equals **$2**, 40 equals **$4**. A 25–30-second demonstration within 20 extra minutes, or 45–60 seconds within 40, is only plausible with existing suitable references, limited native shots and few corrections. It is not a guarantee of the full speaking, multi-scene story at that price.

## 6. Monthly budget and ownership decision

A reasonable **initial operating envelope** is PRO's $9 list subscription plus **$10/month extra GPU**: approximately **$19/month**, excluding tax, excess storage and external inference beyond included credits. During an active delivery month, permit **$20–$30 extra GPU** only against approved work: **$29–$39 plus extras**. This is an initial budget recommendation, not a measured per-film capacity or a promise of daily full films.

Included allowance resets rather than accumulating into a purchasable monthly pool. On-demand batching around resets can reduce cash spend when deadlines allow. Keep compute budget separate from language/vision/transcription usage and storage. Do not upgrade Team solely for more quota: its published per-member allowance remains 40 minutes. Enterprise's 60 minutes is not a cost-efficient single-user solution by itself.

**Ownership scenarios, not hardware quotations:**

- A hypothetical **$3,000** consumer workstation is not proven capable of our unchanged pipeline; consumer VRAM/offload limitations may require a different qualified configuration.
- A hypothetical **$10,000–$15,000** complete high-memory system would need exact vendor quotes, power/thermal planning and model benchmarks. This range is used only to examine economics, not assert a market price.
- At $10,000 depreciated over 36 months, capital alone is **$277.78/month**, before electricity, repairs, disks and administration.
- Example ownership break-even: $10,000/36 + $20 fixed monthly costs, divided by ($2.75 rental/hour − $0.105/hour electricity), is about **113 active hours/month**. Electricity assumes 0.7 kW × $0.15/kWh. This excludes idle power, taxes, financing, downtime and labor, and assumes equal throughput—which must be benchmarked.

At an extra-GPU budget of $10–$30/month, buying hardware is economically difficult to justify. Reconsider ownership when there is sustained utilization, privacy/latency demand or rental bills large enough to support a measured total-cost comparison. Private hardware does not remove model licensing obligations.

## 7. Proposed architecture: additive, not a rebuild

Keep Main, Control, Renderer and Reference Lab. Add the **compute router inside Control**, not another always-on Space. Main sends the same signed mission and owner authority; Director retains creative decisions and approved asset assignment.

Proposed flow:

1. Validate mission, immutable words, character/wardrobe/reference hashes, capability requirements and owner limits.
2. Reuse a valid approved asset only if its scope and performance satisfy the shot. Otherwise prepare a new inference request.
3. Read fresh quota and project budget; reserve against one account-wide ledger shared by references and videos.
4. Choose a **qualified exact-model backend**. Prefer included ZeroGPU when economical and sufficient; use a preapproved paid route only within its explicit cap. No silent model substitution.
5. Record provider task ID and submission state before waiting. Poll the same job after disconnect; do not create a second render to recover a browser session.
6. Verify output hashes, complete decode, duration, audio, frame count and identity/reference provenance. Keep independent creative/lip-sync/final QC.
7. Reconcile measured usage and billed evidence separately, release reservations and store artifacts in existing shared storage.

The router can eventually automate included-first selection, hardware compatibility and budget stopping. **It cannot currently promise authoritative live billing:** use authenticated quota responses where available, label stale observations, and stop conservatively when they cannot be read. Browser billing scraping is a fragile secondary option, not a prerequisite for generation. Do not claim that a local runtime timer is a provider invoice.

Long-lived rented sessions may reuse model weights across jobs. Use per-job clean creative state, exact pinned models, a finite session timeout, sequential memory management and explicit shutdown. Do not keep both heavyweight pipelines resident without measuring memory. Content reuse requires full cache keys: model/runtime hashes, prompt, references/order, geometry, seed, voice/audio, control settings and relevant approvals.

## 8. Exact proposed repository changes — NOT applied

Repository: private `drglover910-ops/JOAT-ANIMATION_STUDIO`. The current name is known to be provisional; no rename or new repository is necessary for this task. Every future changed file must carry its own embedded incremented version, not only a version in its download name.

| Proposed file / area | Purpose |
|---|---|
| New shared `joat_gpu_job_router.py` | Route one signed GPU task among qualified backends; retain existing department authority and caller identity. |
| New shared `joat_compute_backends.json` | Versioned capabilities: exact checkpoint/runtime pins, GPU size, controls, privacy limits, price source/date and qualification evidence. |
| New shared `joat_project_gpu_budget.py` | Atomic account/project reservations and reconciliation, included versus paid policy, approval cap and idempotency. Store no secret values in receipts. |
| `apps/main/joat_included_film_render.py` | Replace duplicated admission logic with the shared policy; reconcile documented GPU-size multipliers only after SDK verification. Preserve shot ceilings and locked-plan checks. |
| `apps/main/joat_reference_supplement.py` | Use the same ledger for references and expose accepted/rejected candidate cost; prevent accidental repeat requests. |
| `apps/main/joat_remote_generation.py` | Reconnect by execution/provider ID, preserve uncertain-submission state, support status and cancel without resubmission. |
| `apps/control/departments/generation_worker/joat_render_bridge.py` | Add backend adapter boundary while keeping current runtime audits, 96-parameter compatibility validation, hashes and full media evidence. |
| New optional `apps/gpu_runner/` | Portable pinned container/runner for a bounded rental experiment; exact ComfyUI nodes, weights and artifact uploader. This is not a fifth production Space. |
| Renderer startup/configuration | Later introduce qualified profile-based optional loading and batch cache policy; retain existing model checksums and offline/pre-GPU preparation. |
| Main and Director UI/status | Show source/time of quota observation, active reservation, project spend estimate, measured consumption, paid authority and candidate availability in both relevant workflows. Director owns full Studio controls. |
| Tests and deployment manifests | Verify budget rejection, concurrent reservations, 1×/2× sizing, reconnect idempotency, unknown submission, mismatched backend/model, failed artifact handling and unchanged approvals; reseal changed source manifests and contracts. |

These are proposed integration points, not a claim that a completed router exists. Packaging shared code between current deployment folders needs to follow the repository's existing release process. No production files were edited for this report.

## 9. Prioritized implementation after approval

1. **Finish the current commercial:** preserve checkpoints, reuse suitable approved assets, fix remaining shot specifications on CPU, obtain fresh quota, and run sequentially within an explicitly approved project budget. Do not add an infrastructure migration first.
2. **Add minimal shared accounting:** unified reservations, fresh/stale quota labels, measured usage receipts, exact paid cap and stable job recovery. Keep paid fallback disabled until granted.
3. **Qualify one rental run:** same approved references, same custom model/profile, one speaking shot and one necessary reference only if budgeted. Record cold and warm wall time, VRAM, accepted quality, native speech/lip sync, full cost and shutdown. Use an explicit timeout and spending ceiling.
4. **Enable a second backend only if it wins on accepted-output cost and quality.** Maintain ZeroGPU as an included-first option; do not lock the studio to a new provider.
5. **Revisit hardware after several real deliveries.** Compare 30-day billable hours, rejected-output cost, deadlines, concurrency and commercial revenue, rather than buying based on quota frustration.

## 10. Evidence, uncertainties and sources

Authoritative sources retrieved October 19, 2026:

- [HF ZeroGPU hardware, quota and overage](https://huggingface.co/docs/hub/spaces-zerogpu).
- [HF subscription and hardware pricing](https://huggingface.co/pricing).
- [HF Jobs pricing and billing](https://huggingface.co/docs/hub/jobs-pricing).
- [HF Inference Providers pricing](https://huggingface.co/docs/inference-providers/pricing).
- Public model metadata: [10Eros](https://huggingface.co/TenStrip/LTX2.3-10Eros), [LTX-2.3](https://huggingface.co/Lightricks/LTX-2.3), [Qwen Edit](https://huggingface.co/Qwen/Qwen-Image-Edit-2511), plus the model IDs listed above.

Local evidence in this report's folder: `live_inventory_v1.0.0.json`, `all_spaces_v1.0.0.json`, `identity_safe_v1.0.0.json`, `quota_access_v1.0.0.json`, `billing_page_access_v1.0.0.json`, `model_providers_v1.0.1.json`, and `research_fetches_v1.0.0.json`. Raw official pricing extracts are retained alongside them. Earlier `model_providers_v1.0.0.json` had an SDK parsing error for list-shaped provider metadata; **use corrected v1.0.1**, not that partial result.

Measured-use evidence comes from saved project quota receipts: speaking shot delta **168.230791 seconds**, latest reference delta **444.889001 seconds**. These reflect account-balance changes around those operations; they are stronger than allocation ceilings but are not itemized invoices or proof of all future shot costs.

Unresolved: fresh credits/current billing totals, other account workloads, external vendor prices, exact rental throughput, minimum VRAM, final creative qualification and commercial licensing of the complete custom stack. Base LTX declares a community license; 10Eros metadata has no license declaration. Confirm the applicable fine-tune/base terms before commercial distribution; lack of metadata is not itself a legal determination.

**The financial decision supported by this audit is a small capped credit allocation before a server purchase. It removes the quota bottleneck; it does not replace the remaining creative and final-delivery work.**
