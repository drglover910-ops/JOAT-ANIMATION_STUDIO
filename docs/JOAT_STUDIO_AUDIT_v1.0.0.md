# JOAT Animation Studio — evidence-based audit

File version: **1.0.0**. Audit date: **October 18, 2026, Eastern time**. Scope: JOAT Animation Studio and its Main Assistant interfaces. Production remains paused. This audit made no deployment, hardware, secret, database, or GPU-inference changes. Local evidence copies and reports were created only.

## Decision and interpretation of the update

The studio has real working production components. It needs completion and better reuse of verified knowledge, not a rebuild or more management bots. Keep the functioning Main → Executive/Studio Control → specialist chain. Treat the Director as the creative authority within that chain rather than introducing a second executive layer.

The entire supplied 2,857-line update was read. Its Main Assistant/Opportunity Engine/GHL examples are context; unrelated project changes are excluded. Its instruction to audit first governs this pass. Historical “execute” passages do not resume the paused render queue. The 60-second alternative script does not replace the approved 90-second script. Existing casting remains Founder/CHAR-001 as consultant, Cristu/CHAR-004 as business owner, Kiana/CHAR-002 as customer. The later approved timing adjustment remains: shots 11/12/15 six seconds, shots 10/16/18 four seconds, all others five seconds, total 90-seconds.

Several copied statements require qualification:

- A sampled reference breakdown is not a frame-accurate edit list. Suggested music/SFX are not verified reference audio.
- The copied 3/5 quality ratings are not an established measurement of this studio's current film. A proposed 90% style threshold is not an achieved score or a commercial certification.
- The current saved60-second master is 1024×576 at 24 fps, not the 910×512/30fps description in the other conversation. A different exported/screen-recorded file may explain the difference.
- Public models, a README license, or a working Space do not by themselves establish all commercial usage rights.
- Saving conversations, hashing assets, and generating valid JSON are respectively persistence, integrity checks, and contracts; none alone proves learning, visual identity fidelity, or finished animation quality.

## A. Current architecture inventory

Fresh read-only discovery found 26 JOAT-associated Spaces. Four are RUNNING: Main Assistant, Executive/Studio Control, renderer, Reference Lab.22 are PAUSED, including the original individual department Spaces and ACE music lab. Their paused status is not a lost capability:20 department roles are bundled into Studio Control and run as local CPU subprocesses.

| Component | Verified current release | Runtime | What this proves |
|---|---|---|---|
| Main Assistant | app2.1.97, commit36c8beb2a80b26534c096846d83209b0ce9c7eaf | Private,cpu-basic,RUNNING | Deployed orchestration/UI source exists and is running; no paid LLM call made in audit |
| Executive Producer / Studio Control | app1.2.20, commit2a9e8b4b8a7d3d963ada6491f9c66f4602be4897 | Private,cpu-basic,RUNNING | Bundled source and current runtime; GPU hold=true |
| LTX renderer | app1.0.14, commitbe1591ad2ad05c3af51f27fd671658d1873e15af | Private,zero-a10g,RUNNING | Existing native rendering lane, not new inference during audit |
| Reference Lab | app2.16, commit8ce0f763e9c9db18950dc35726e3ee851ebf5412 | Private,zero-a10g,RUNNING | Qwen scene-candidate integration deployed; prior actual candidate preserved |
| ACE music lab | commit74cf2714b50c1ce5b5b3c8d46c3bf9c78147f335 | Public,PAUSED | Wrapper/source exists; no live music call or90-second score verified |
| Selected GitHub project | drglover910-ops/JOAT-ANIMATION_STUDIO | Checkout has no commits/tracked files; remote query yielded no main ref | No maintained GitHub implementation baseline verified here |

The running HF repositories currently hold the production code history. `/workspace/joat-implementation` holds implementation/evidence working files; it is not a substitute for a maintained source repository.

Storage roles already match much of the proposed design:

- Main's own state: `/data/joat-main-assistant`, including SQLite, conversations, tasks, approvals, receipts and recovery directories.
- Shared studio state/media: `/studio/joat-studio`, backed by `Dezz-9-10/J.O.A.T.-Studio-storage`.
- Canonical assets: existing pinned Character/Environment Master sources, not a new bucket migration.
- Credentials: existing platform secrets. Audit inspected expected secret presence only, never values.
- GHL: Main's exposed configuration has `JOAT_GHL_ENABLED=false`. Studio operation is already independent of GHL.

Evidence: `space_inventory_v1.0.0.json`, `live_snapshot_v1.0.0.json`, `end_snapshot_v1.0.0.json`, `main_safe_config_v1.0.0.json`, `control_safe_config_v1.0.0.json`.

## B. Verified hierarchy and responsibilities

Owner → Main Assistant → Executive/Studio Control → Director/creative packets and relevant specialist roles → Generation Supervisor → Generation Worker → private LTX renderer → QC → Post Supervisor → specialist media operations → final review → archive/delivery.

Director is a creative role; Executive/Control is the operational host and dispatch authority. The current software does not prove a separately deployed DirectorLLM that autonomously leads every production step. Keeping the existing chain avoids duplicating authority.

The20 roles are source-hash-verified departmental applications in one Control deployment. They are not20 independentLLM services. None of their app sources contains an LLM chat-completion call. Main has an InferenceClient chat/proposal path and separate deterministic dispatch code. Main's source default is `openai/gpt-oss-120b` with provider auto; a model supplied as a secret override could not be verified from public variables. No claim that this default was exercised in this audit.

Main retains its conversation records and company-level interfaces. Studio Control owns the bounded local execution pool. Project JSON/receipts/grants/frame bindings in the shared bucket hold production state. Existing signed requests, hash checks, reservations, cancellation and explicit unknown-outcome handling provide useful control boundaries.

## C. Agent-by-agent capability matrix

Status vocabulary: **V** verified operational for the stated narrow capability; **I** implemented but not verified end-to-end; **P** partially implemented; **D** documented/planned; **M** missing in inspected source; **U** unable to verify. A role can have different statuses for different functions.

| Role | Evidence-backed capability | Status and remaining limit |
|---|---|---|
| Main Assistant | Chat/proposal code,SQLite schema, signed executive dispatch, browser production UI and saved-film retrieval | V for demonstrated studio dispatch; P for broad autonomous orchestration; persistence restart/restore not re-tested |
| Executive/Control |20 allowlisted local roles, native callback routing, bounded subprocess pool and source manifest verification | V; application-level boundaries, not a full multi-tenant sandbox |
| Character Master | Canonical registry, locked character packets and pinned source hashes | V; hashing does not prove rendered face identity |
| Environment Master | Environment identities, source mapping and locked packets | V; physical geometry consistency remains a visual QC task |
| Director | Structured per-shot directions, locks, role assignment and approval metadata | V for contracts; P for autonomous creative reasoning, supplied upstream by Main/operator |
| Shot/Camera | Exact shot/camera/time contracts | V for instructions; P for reliable model execution of every camera intent |
| Performance/Action | Structured emotion, action, gaze and continuity constraints | V for contracts; P for perceptual performance enforcement |
| Generation Supervisor | Validated job packets and worker handoff | V, proven by native saved MP4 outcomes |
| Generation Worker | Prepared plan, source verification, runtime audit and LTXI2V execution | V for controlled single composed frame; P for broader multi-character reference qualification |
| QC | Source/media validation and owner creative-review gates | V for technical/gate operations; P for automated visual, voice and lip-sync evaluation |
| Post Supervisor | Existing supplied-media specialist workflow and checkpoints | V for prior small production; full new90-second completion pending |
| Editorial | Real trims/assembly through shared media code | V for existing accepted tests/earlier film; current90-second edit not built |
| Sound | Supplied/native audio mixing and loudness processing | V; reusable verifiedSFX library and complete new-film sound design incomplete |
| Music Worker | Music work-order contracts and supplied-track handling | V for supplied-media path; P for new ACE score generation/assembly |
| Compositing/VFX | Real image/graphic overlays | V for demonstrated2D overlays; moving-tablet perspective tracking and complex effects not qualified |
| Color/Finish | Existing media filtering/finishing operations | V for implemented/tested lane; no reference-level artistic grading certification |
| Titles/Graphics | Existing titles/interface graphics and compositing | V; final-audio-synchronized90-second captions and end card pending |
| Voice/Dialogue | Supplied audio registration and native actor dialogue in earlier clips | V for those paths; stable voice across every new shot and phoneme-level lip-sync not qualified |
| CPU Narration | Kokoro candidate speech, pinned model bytes and13 word-checked narrator clips | V for prepared narration; not an actor-dubbing substitute |
| Delivery/Archive | Earlier private-bucket MP4 archive and readback manifest | V for earlier small delivery; current90-second film has no final approval/archive |
| Browser Worker | Validated browser work-order contracts | P; no verified general interactive browser execution. Main's uploaded-video/URL evidence code is separate |
| Hugging Face Master | Validated platform work-order/action packets | P: source explicitly returns planned/requires_execution_layer; not a working agent-deployment factory |

All20 department app sources were matched against the current deployed Control manifest before review. Broader capabilities were not inferred from names or buttons. See `department_source_inventory_v1.0.0.json`.

## D. End-to-end production evidence

Fresh private-bucket reads verified:

1. Earlier60-second film review: SHA256`91048ab404fdc83928fdc1967f55447579dffae938e616b81226d3c7b7174532`,5,903,998bytes,H264/AAC,1024×576,24fps,1440 video frames. It is real media, not a packet simulation. Container duration is60.021333seconds;1440/24 gives60-seconds of video. AAC/container padding should be handled explicitly in delivery tolerances.
2. Corrected Style001opening: SHA256`ebffe59cf01e6bbca143a01408e23b8b314f29a811b90b6b21969cd3d9614f11`,6,112,178bytes,H264/AAC,576×1024,24fps,121 frames,5.041667seconds. Prior recordedCPUASR found no speech; per-frame scene metric max0.039747 below the0.2screening threshold. These are limited checks, not complete perceptual approval.
3. An earlier PROJECT-001delivery manifest remains readable and reports `ARCHIVED_READBACK_VERIFIED`. Its approval does not approve the60-second review or current90-second project.

Pipeline state for the current project:

| Stage | Current state | Needed next |
|---|---|---|
| Original request/timing/cast | Approved and preserved | Reuse; no new story or character redesign |
|18-shot plan | Present;90-seconds/2160 delivery frames | Preserve approved timing and words |
|16 native-video source packets | Prepared and verified | Appropriate approved scene-frame assignments |
| Narrative audio |13 CPUcandidate clips, words previously checked | Final auditory review/mix and exact timing |
| Scene images | One approved Cristu night-office frame;6 additional composition groups analyzed | Reuse valid assets/end frames; generate only genuinely missing compositions |
| LTX video | Earlier60-second film plus corrected current opening proven |15 additional planned native shots, subject to proper references and budget |
| Two-person scenes | Canonical source packets present | Complete all-visible-cast registration/binding verification before claiming two identities are controlled |
| Graphics | ExistingCPUgraphic assets/cues prepared | Qualify tablet/UI placement and motion; final captions |
| Music/SFX | Requirements and integration paths present | New evolving90-second score and sound design not completed |
| Timeline/final delivery | Earlier small workflow proven | Assemble, verify2160frames, full audiovisual QC, owner final approval, archive/readback |

The90-second film is unfinished. Finishing it does not require repeating the basic proof that MP4 generation, narration, captions, or small delivery are possible.

## E. Character and asset intelligence

Verified registry: FounderCHAR-001(11assets), KianaCHAR-002(14), DensínCHAR-003(3), CristuCHAR-004(2), Guenièvre/JenCHAR-005(1), HasleyCHAR-006(2), Ms.LaveRenCHAR-007(2). Asset counts describe registered files, not complete pose libraries or unique verified biological views.

Executive OfficeENV-001, Coffee ShopENV-002 and Luxury LoftENV-003 exist in the Environment source. The office's file label includesENV-008; the application explicitly maps it toENV-001. Do not rename assets or infer an ID mismatch from the filename alone.

Current identity protection combines canonical hashes, approved images, locked metadata and prompt constraints. The single-frameI2V lane explicitly records biometric identity verification=false. Pixel comparison is not a reliable universal identity check when pose, lighting, wardrobe or camera change. Use source lineage plus suitable visual review; only add embedding/vision thresholds after validating them for these stylized characters.

The first job-frame binding protects one primary character. A two-person first frame needs both canonical identities and reviewed source evidence. Do not relabel a primary-only match as validation of everyone visible. Also keep image1identity, other characters, wardrobe and environment roles explicit when using reference cards. A crop cannot create an unobserved pose or reverse camera angle.

Preserve existing masters. New scene frames belong to project assets after the appropriate approval; they do not automatically become canonical identities or trusted training examples.

## F. Models, features and compute

ExistingLTXmodel is TenStrip's10ErosLTX2.3checkpoint running through pinned ComfyUI/workflows/custom nodes, not a generic unknown video endpoint. The renderer source includes a pinned workflow commit and pinned Comfy/custom-node checkout logic. Python requirements still contain broad ranges; a reproducible environment lock is not complete merely because source commits are pinned.

The feature catalogue already lists30 capabilities: image-to-video, native audio, camera prompting, writer/enhancer, scene planner/builder, continuation, keyframes, motion control, LoRAs, MSR, mixing, upscaling, profiles and export, among others. Many are correctly labeled needs_qualification or hidden/experimental. Text-only generation is not exposed in this app. Preserve that distinction rather than enabling every feature automatically.

A useful drift finding: capability JSON still names renderer commit`3d3daf99...`, while the actual renderer contract/deployment names`be1591ad...`. The latest patch is aCPUpreflight change, so this does not prove rendering is broken; it does prove knowledge and execution metadata can drift. Main/Control also contain duplicated copies of some shared modules at different versions.

| Model/resource | Verified evidence | Limitation |
|---|---|---|
| LTX2.3/10Eros | Real MP4s, source/runtime pins | No promise of every style, motion, identity or lip-sync scenario |
| Qwen-Image-Edit-2511 | Real approved scene candidate and deployed Reference Lab |6 composition requests prepared, not6 completed or necessarily6 needed calls |
| Kokoro82M | PinnedCPUnarrator path and13existing clips | Narration candidate generation is distinct from native on-screen actor speech |
| ACE-Step1.5 | Source wrapper with5–60-second output contract; Space paused | No newly verified90-second score; a README's older qualificationSHA is not current proof |
| Main LLM | InferenceClient/proposal code; defaultgpt-oss-120b | Provider health/live model selection not re-tested; no new paid LLM calls |
| Video analysis | Existing extraction/ASR/reference-analysis path | Complete visual/audio/lip-sync judgment still partial; YouTube access can be blocked |

Observed corrected opening GPU runtime124.54seconds; previous rejected candidate237.95seconds. Cache/warmup and prompt differences prevent treating the difference as a guaranteed speed improvement. These are not invoices. Fresh remaining quota/balance is unavailable to this audit. No new inference, model training, or hardware upgrade was performed.

Current public model metadata declares Apache2.0 for Qwen/Kokoro/gpt-oss and MIT for the two ACE resources. LTX2.3declares a separate community license.10Eros has no declared license in the inspected model metadata. Review the exact fine-tune, base, text encoder, LoRAs, nodes, voices, asset rights and any relevant conditions before commercial release; do not infer the entire stack is cleared from one upstream license. See `model_license_metadata_v1.0.0.json`.

## G. Memory, retrieval and intelligence gaps

| Capability | Audit conclusion | Smallest appropriate action |
|---|---|---|
| Main conversation/task memory | ImplementedSQLite tables, JSON directories, configured persistence | Keep; verify actual restart/backup recovery separately without exposing conversations |
| Short-term context | Recent-message window, default 24 messages | Keep, with bounded project-aware retrieval rather than ever-longer prompts |
| Approved capability knowledge | Existing structured catalogue injected into Main context | Reuse and add freshness/consistency tests |
| General productionRAG | No verified retrieval/indexing path; KNOWLEDGE_DIRcreation alone is notRAG | Add filtered retrieval over approved project facts/lessons using existing storage first |
| Learning from corrections | Strong raw evidence exists across receipts/manifests/reports | Add a typed, reviewed lesson index; raw transcripts/results remain untrusted observations |
| Automated regression checks | Existing source/authorization/contract tests | Consolidate a repeatable versioned suite and record output-artifact evidence |
| Perceptual quality evaluator | Partial ASR/frame/technical checks and owner review | Add domain-validated benchmarks incrementally; preserve human final review |
| Model routing | Configuredprovider/model plus deterministic domain routing | No verified cost/quality-trained router or broad fallback system |
| Dataset building | No curated approved production training dataset verified | Defer until useful labeled examples accumulate |
| SFT/LoRA/DPOtraining | Not implemented as a production improvement loop | Defer; current blockers are workflow/data/quality qualification |
| Agent Factory | Manifests and action planning exist | No verified safe code-build-test-deploy-register loop; not needed to finish this film |

Twenty department source apps contain no LLM chat calls. This can be appropriate: deterministic workers should not all need separate expensive reasoning models. Improve their inputs, tools, contracts and feedback first. Main's inference and a worker's validated execution are different jobs.

A Production Intelligence Library should index existing approved character/environment references, shot specifications, qualified settings, quality outcomes and bounded lessons. Each entry needs project/style/role scope, source hashes, model/compiler versions, reviewer, approval status, evidence references and supersession. Retrieval must filter by scope and freshness. A single successful silent-office correction is evidence for that case, not a universal guarantee.

## H. Communication, orchestration and recovery

Strengths: signed Main→Executive work orders; fixed local department routing; hash-verified bundled source; unique task/job IDs; immutable source snapshots; reservations and cached artifacts; no automatic expensive retry on unknown outcomes; per-request platform delegation is forwarded in memory, not fabricated.

Limits: manual browser interventions remain necessary in someHF429/authentication situations. The currently deployed opening action is project/plan-specific, not a complete generic production scheduler. The quota panel stores owner reports/reservations, not a verified live billing balance. A receipt saying completed does not establish creative quality. New full-film approvals/cost envelopes must not be inferred from one-shot grants.

Checkpoint recovery should retrieve the same job and artifacts, not repeat theGPU call. Preserve the existing protection against restartingControl while an uncertain submitted task may still be active. Late GPU-hold-restoration failure is recorded separately; an operator restoration was verified. Historical failed receipts must remain intact.

## I. Repository and storage organization

Do not migrate functioning storage as part of this audit.

- GitHub: snapshot current audited source, tests, version manifests, schemas and deployment/rollback instructions. The selected repository currently lacks this implementation baseline.
- HF: continue hosting current applications and pinned canonical/model resources.
- Main `/data`: its separate operational database and conversation state.
- Studio `/studio`: project state, approvals, scene assets, audio/video, durable delivery and sanitized production observations.
- Shared JOATstandards: versioned policy/schema/templates owned at the ecosystem level; this thread should consume them rather than create a competing factory or standards repository.
- Secrets: retain current platform bindings; never copy values into GitHub, reports, prompts or training examples.

Do not copy generated videos, sensitive memories or liveSQLite/WAL files intoGitHub. Do not move canonical reference images merely to match a generic proposed folder layout. Generate shared files from one versioned source and add consistency checks to prevent Main/Control drift.

## J. Main Assistant integration and shared engineering standard

Main owns company-level permissions, approved delegation, broad agent registry and budget/report interfaces. The Studio Director/Control owns creative plans, shot dependencies, model qualification and department execution. Main should receive concise evidence-backed status, cost and escalation summaries; it does not need every frame inside its conversational memory.

Proposedsharedstandard: agent identity; purpose; capability/status/evidence manifest; tool and permission allowlist; model/provider policy; knowledge and memory scope; task schemas; escalation; approval scope/expiry; error/recovery/idempotency; isolation; evaluation/acceptance; observability; embedded per-file versions; pinned release/rollback; bounded cost; reviewed improvement workflow; documentation ownership.

Reuse current schemas and explicit source fingerprints. Shared standards should not erase animation-specific cast, continuity, audio, camera or frame-level delivery rules. Coordinate anycentralstandards repository with the Main Assistant thread. No unrelatedOTUOpportunityEngine orGHLchanges are authorized by this report.

## K. Agent Factory readiness

Requirements/specifications, deterministic manifests, role dispatch, source versions and some acceptance tests already exist. An isolated code-generation environment, reviewed build/dependency process, safe deployment adapter, scoped agent registration and rollback qualification were not verified as one working factory.

The bundledHFMaster explicitly reports that authenticated external platform execution is not connected for its proposed operations. Codex's separate authenticatedHFwrite access does not give that capability to the Main Assistant agent. Do not label the factory complete or create another autonomous worker-builder here.

Defer factory expansion until the current studio's repeatable production and knowledge/evaluation path are sound. No unrestricted code execution, secret access or self-modifying production loop is proposed.

## L. Security and commercial readiness

Verified foundations: privateMain/Control/renderer/referenceSpaces; fixedowner verification; HMAC dispatch; immutable/hash-checked sources; canonical locks; path validation; durable artifact checks; no-retry safeguards; explicit final QC gates; existingfreeCPUhosting. MainGHLintegration is disabled.

Material limitations:

1. Single-owner design is not a proven client/tenant isolation system.
2. Local worker subprocesses share a host, writable storage and inherited service credentials. The pool removes the dispatch signing key, but it is not anOSsandbox with separate per-role identities. Apply a deliberate environment/credential allowlist when qualifying broader autonomy.
3. SQLite code/schema and persistence configuration are not a demonstrated consistent backup/restore drill. Document single-writer assumptions and test backup recovery before scaling instances.
4. Capability/source/dependency drift needs automated detection. SomePythondependencies are ranges.
5. Actual costs, cancellations during provider execution, performanceSLOs and broad perceptual metrics are not comprehensively monitored as one operating system.
6. Fine-tune/base/text-encoder/asset/voice commercial rights are not fully cleared by this audit.
7. Prompt-injection defenses and external-tool controls require adversarial testing before expanding browsing/deployment authority.
8. Raw captures, imported transcripts and generated failures must not become approved knowledge or training material automatically.

These findings do not revoke existing internal testing or demand new paid services. They prevent an unsupported claim of commercial, autonomous, multi-tenant readiness.

## M. Prioritized roadmap

| Priority | Action | Approximate effort / cost | Acceptance evidence |
|---|---|---|---|
|0 | Preserve current film, original script, sources, approvals and paused production state | Documentation only; no GPU | Current hashes/releases/hold recorded |
|1 | Snapshot auditedHFsource and existing regressions into selectedGitHubrepo, with rollback/release manifest | Small: roughly0.5–1day,CPU only; after authorization | Source-byte comparisons, version pins and reproducible tests; no runtime-assets/secrets committed |
|2 | Add a minimal reviewed Production Intelligence Library adapter over current bucket/SQLite; fix metadata consistency | Small/medium:1–2days,CPU first | Retrieves only approved scoped evidence, rejects stale/unreviewed records and preserves project isolation |
|3 | Complete exact supplemental reference authority and all-visible-cast frame binding | Medium:1–2days software work; required new scene inference separately budgeted | Both people's pinned identities checked, no primary-only false claims, original mission unchanged |
|4 | Use existingDirector/Controlqueue to finish only missing scenes and native actor clips | Quality-dependent; new GPU work requires chosen cost scope | No duplicates, stable cast/voices, actual playable artifacts and per-shot QC |
|5 | Finish score/SFX, preciseUI/captions, editorial/color,90-second timeline | ExistingCPU tools plus qualified music calls if used |2160 video frames/24fps, approved exact words, safe captions, intelligible mix, verified playback |
|6 | Final ownerAVreview and durable archive/readback | Existingworkflow | Final approval binds exact master SHA; MP4, manifest, captions, reports and assets consistent |
|Later | Additional styles, complex motion/VFX, agentfactory, training | Separate qualified proposals | Demonstrated need and measurable improvement over baseline |

Effort ranges are engineering estimates, not a promise of elapsed completion time or a new spending authorization. Do not authorize a fixedprice for the full film from the cost of one opening. The copied90%style target may be proposed as a future rubric, with no critical failures, but cannot replace actual identity/audio/continuity checks or be claimed achieved now.

## N. Exact proposed files and changes — not implemented

All newly introduced/uploaded code files must contain their own FILE_VERSION; increment each changed file's version, and continue the current app.py version sequence.

| Proposed path/change | Why/reuse | Acceptance / rollback |
|---|---|---|
| GitHub`AGENTS.md`, `docs/architecture.md`, `release_manifest.json`, `tests/` | Capture currentoperating standards and actual source baseline; reference sharedstandards version | Exact deployedhashes, no credentials/media; revert sourcecommit without movingbucketdata |
| `schemas/production_lesson.v1.json` | Distinguish observations, approved lessons and superseded rules | Requiresproject/style/role/model/evidence/reviewer/status; no raw output auto-promotion |
| `joat_production_knowledge.py` (new 1.0.0) | ThinCPUretrieval over existing approved records, not a new Space/vectorplatform | Scope/freshness tests; feature can be disabled without altering existingassets |
| Shared`joat_studio_capabilities.json` source plus consistency test | Current30 features are useful; rendererrevision and copied modules can drift | Correct declaration vs executioncontract and deploySHA; no newfeatures auto-enabled |
| `joat_canonical_project_references.py` (next independent version) | Extend one-request origin through exact append-only supplemental authority | Existingone-request negative tests stay valid; no new GPU on mere registry update |
| `joat_job_frame_binding.py`, `joat_approved_reference.py` (next versions) | Verify both canonical subjects when a selected shot contains two people | Reject omitted/substituted actors; preserve old single-character bindings; no biometric claims |
| Existingmedia/qualification modules (only where tests prove need) | Add stable voice, screen replacement and caption timing checks | Keep known working render path and native actor speech; no new render model by default |
| `evals/style001/` and versionedbenchmarkmanifest | Reuse60-second master, rejected opening and corrected opening as distinct evidence | Report unit vs artifact vs humanQC separately; no unnecessary inference |
| `docs/rollback.md`, backup/restoreprocedure and model/assetlicensemanifest | Make release recovery and commercial rights explicit | Non-destructive restore drill separately authorized; no source asset overwrite |

No architecture migration, new supervisor Space, memory service, model swap, factory deployment, training run, hardware upgrade or live code change was performed.

## O. Verification and audit limitations

Executed during this audit:

- 26Space runtime/source metadata checks;20 department app source hashes verified.
- Private download/readback of existing60-secondmaster, correctedopening and earlierdeliverymanifest; expected media hashes matched.
- ffprobe counted1440frames/24fps for the60-secondfilm and121 frames/24fps for theopening. FullFFmpegdecode of the60-secondfile completed without reported errors.
- 28 existingCPUunit tests passed:10 corrected-opening orchestration tests,4 allocation/Worker-entry tests,14 browser/recovery tests. These tests usemocks/stubs for transport; they are not28 new live render or visual-quality tests.
- No paid LLM call, GPU inference, deployment, secret rotation, database mutation, unpause or hardware change.
- Ending releases match starting releases; DirectorGPU hold remains true.

Limitations: no livequota/billingbalance verified; no new providerhealth/inference request; no human auditory/lip-sync rating of all reference videos; no verifiedframe-accurate referenceEDL; no new database restart/restore test; no fullpenetration or everydependencylicense review. Cross-thread valuation claims and otherprojects' implementation state were not adopted as evidence.

Evidence files in this folder: `space_inventory_v1.0.0.json`, `department_source_inventory_v1.0.0.json`, `live_artifact_readback_v1.0.0.json`, `model_license_metadata_v1.0.0.json`, `test_verification_v1.0.0.json`, source snapshots, and end-state snapshot.

**Smallest safe next step:** after this read-only review is accepted, capture the existing audited source/evaluation baseline inGitHub and introduce one scoped, CPU-only approved-knowledge retrieval/consistency improvement. Reuse the current working studio. Then resume the existing90-second project under its separately resolvedGPU budget. No newstory, duplicate60-secondtest or model-training project is required.
