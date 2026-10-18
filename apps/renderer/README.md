---
title: LTX 2.3 Studio · AI Scene Planner
emoji: 🎬
colorFrom: indigo
colorTo: pink
sdk: gradio
sdk_version: 5.44.1
python_version: '3.12'
app_file: app.py
hf_oauth: true
hf_oauth_scopes:
  - inference-api
pinned: true
short_description: 'Economy, AI planner, LoRA refresh & native audio'
tags:
  - video
  - image-to-video
  - ltx
  - ltx-video
  - lora
  - civitai
  - audio
  - controlnet
  - pose
  - depth
  - zerogpu
  - scene-planning
---

# 🎬 LTX 2.3 Studio · 10Eros

**One image. One idea. Motion and sound, planned together.**

Turn a reference image into a clip or a longer scene with native audio. Choose **Simple** for
guided creation or **Pro — all tools & settings** for the full toolset.

**🆕 Live clip progress · 🔒 Face-only Identity Lock · 🪄 AI Scene Planner · 🔄 Looping LoRA Refresh · 🔊 Native audio**

## 🆕 Economy — less work per clip

**Economy is the new starting preset:** approximately **0.65 megapixels**, snapped to the
model's supported grid, with **one sampling pass**. It reduces image detail and skips the
refinement pass to reduce GPU work. **Fast**, **Balanced** and **Quality** remain available;
select Balanced or Quality when refined detail matters more than speed. Simple and Pro both
keep the speed selector. Imported profiles retain their saved resolution and refinement settings.

Model preparation and custom LoRA downloads now finish **before** the video GPU request.
Delivery conversion happens **after** it returns, and a compatible 24 fps H.264 MP4 is reused
without a second encode. Stitching and soundtrack fitting also run on the CPU.

The GPU readout uses the actual snapped image size, clip durations and motion-control overhead.
It shows the **requested reservation**, not a billing receipt or a measured render time.
Reservations retain their existing timeout calibration. These changes have not been benchmarked
on a live ZeroGPU worker, so no fixed percentage saving is promised for your settings.

## 🆕 LoRA Refresh — relevant choices that loop

**Prepare prompt & LoRA/effects** and **Split into clips** share one selection.
Press **🔄 Refresh — next group ↻** in either panel to browse the next group of up to five
candidates ranked by the current prompt or scene. Refresh returns to the beginning after the
relevant matches are exhausted. It never fills the list with random catalogue entries.

- General NSFW **all-in-one / AIO** entries stay visible on each page unless confirmed broken
  or incompatible. Visibility does not enable them automatically.
- Your selected adapters stay visible alongside the rotating group. The list can therefore
  contain more than five entries. Select up to **two**; a third tick replaces the oldest selection.
- **Refresh makes no AI generation call.** It keeps the current selection, except confirmed bad
  entries, and leaves the scene's wording and timing intact apart from owned trigger suffixes.
- Known activation words follow LoRA changes in the **main prompt and every nonempty clip**.
  Editing the custom LoRA text also updates them. Previously inserted words are removed when
  switching adapters; words already written by you are preserved. The app does not invent
  activation words when metadata has none.
- Trigger ownership is tracked in the current UI session. Words loaded from a profile or pasted
  manually without that history are treated as user text and are not silently deleted.
- Confirmed missing files and explicitly incompatible model metadata are excluded for 24 hours,
  then rechecked. Identifiable invalid-weight failures also mark the affected adapter.
- Timeouts, rate limits and login failures do not permanently blacklist an adapter. Pinned general
  options survive transient checks. Link availability alone cannot prove that weights will load
  or that a visual effect will look good.

These are catalogue suggestions, not downloaded bundles. Refresh never deletes the shared
catalogue. The guided two-adapter limit does not remove Pro's manual LoRA controls or separate
video/audio strengths. Initial prompt preparation and scene splitting can ask the writer to
choose adapters; it may answer **NONE**.

## 🆕 AI Scene Planner — available in Simple

**Writer access:** no extra app login is required to try the public Qwen writer. Like WAN,
LTX forwards the current browser's ZeroGPU context. It does not decide that a visitor is
anonymous merely because there is no LTX OAuth session. The default writer's GPU reservation
can still exceed the access or quota available to a particular request. A refused reservation
is shown clearly, with no automatic retry and no change to the existing scene plan.

Optional personal sign-in is under the prompt controls. It uses that visitor's account.
LTX never sends the owner's `HF_TOKEN`, `PLANNER_HF_TOKEN`, `EXPANDER_HF_TOKEN` or cached Hub
login to the AI writer. This is not a promise of unlimited or free-only GPU use: the platform's
quota and prepaid-credit rules still apply to the account making the request. Changing the
LTX video length does not change the remote writer's reservation.

That Qwen endpoint has a fixed 1024-token answer limit. LTX now plans **up to two clips per
request** for this writer so complete JSON is more likely to fit. Other writing Spaces retain
batches of up to six. Long scenes therefore require multiple writer requests; no automatic
retry is submitted after an admission error. Your existing scene stays intact on failure.

Describe all the actions once. The selected writing model suggests **the number of clips,
a separate prompt for each stage and an individual duration for each clip**.

1. Upload a starting image and describe the sequence in **The whole scene**.
2. Press **🪄 Split into clips**. Automatic clip count and automatic timing are on by default.
3. Press **🎬 Make the whole scene and join it**. LTX generates the clips in order, including
   their audio, and joins the completed scene at the end.

You do not need to split prompts or enter times by hand. The preview shows every clip's prompt,
its proposed duration and an approximate total length. Open **Review or edit the clip prompts**
only if you want to adjust the plan. You can also fix the clip count or turn off automatic timing.

For example: **“The character turns around, crouches, then claps while crouching.”**

| Stage | Main action | Example time | Continuity |
| --- | --- | --- | --- |
| Clip 1 | Turn around and settle | About 3 s | Finish facing the new direction |
| Clip 2 | Lower into a crouch | About 2.7 s | Start in the previous clip's ending pose |
| Clip 3 | Clap while remaining crouched | About 1.7 s | Preserve the crouch; include the clapping sound |

These times illustrate a possible plan. The model estimates the time required for each action,
and the app rounds times to LTX's supported frame intervals. Actual action completion and the
exact motion still depend on the video model. Short actions usually work better as short clips.

The planner is asked to keep **one main action or one natural movement phase per clip**, preserve
the action order, maintain character and scene continuity, and carry the ending pose into the
next stage. Because LTX generates sound together with the video, each prompt can include the
requested sounds or speech for that stage.

Ideas can be written in Bulgarian or English; clip prompts are written in English for LTX.
Leave the scene idea empty to use the main prompt. Longer plans are written in small batches
with the previous stages as context. If the writer returns incomplete or invalid data, your
existing plan is kept. Planning does not start video generation.

The planner uses the **Big model Space** selected beside the prompt controls, initially
`amisima/Qwen3.8-27B-Uncensored-Demo`. Your idea and reference image are sent to that Space for
planning. This submits additional GPU work, using the current visitor's authenticated or
anonymous access. It is a separate request from LTX video generation.

## 🎞️ Scene Builder — up to 64 clips with audio

Eight clips was an application limit, not an LTX model limit. This build supports **1–64 clips
per scene run**, with one generation request per clip. Available GPU allowance, memory and the
selected settings still determine what can finish.

**Live status above the video shows the current clip before generation starts:** for example,
“Generating clip 2 of 5”, its planned duration and a short prompt summary. The bar counts
completed clips, not estimated denoising progress. “Joining completed clips” is a separate CPU
stage. Stop and errors retain a visible explanation and the completed queue.

Each clip starts from the last frame of the preceding one. The reviewed prompts and durations
stay fixed during the run; edits apply when you start or resume it. Completed clips collect in
the queue and are joined at the end, with their generated audio included.

**Start at clip** follows the next unfinished stage. While the session and its files are still
available, you can resume a stopped scene without restarting its prompt sheet. **Final Cut** also
lets you join the queued clips manually. Joining runs on the CPU and uses no extra ZeroGPU time.

The regular Scene Builder uses the per-clip sheet when present; experimental prompt relay and
internal scene chaining are disabled for that run so they cannot replace its planned actions.
Their settings remain available in Pro for separate experiments.

## ✨ Simple — guided creation

- **Prepare prompt & LoRA:** expand the idea using the photo, suggest matching adapters and set
  their strengths and trigger words. The suggestions remain editable.
- **AI Scene Planner:** automatically choose clip count, prompts and individual times.
- **Identity Lock:** optionally provide a separate portrait to help preserve likeness.
- **Native audio:** generate sound with the video.
- **Scene Builder:** generate and join a complete scene, or add just one more clip.

## 🔒 Improved Identity Lock

The standard image-to-video path now prepares the face on the CPU before requesting GPU time,
using the conservative correction from WAN. It aligns visible faces, matches lighting, protects
eye and mouth detail and changes only the face region. The current temporal frame keeps its
pose and background. The original portrait remains fixed across subsequent clips and on resume.

A gentle attention anchor uses the **corrected first frame's face region** during sampling.
The old extra full-portrait frames are no longer appended to the video latent. The full-frame
latent anchor is bypassed in this mode. The 10S anchor's frame-shape observer also handles
LTX's combined video/audio input, so this path can discover the video's actual geometry.
The unused likeness guide is disconnected from sampling, avoiding its portrait VAE encode
even though the upstream node would still perform that work with strength set to zero.

- **Face correction strength:** 0 disables the standard identity-photo path; 0.65 is the default.
  The actual blend is bounded to avoid ghosting. The result status reports a correction or skip.
- **Likeness anchor:** starts at 0.08 and is capped at 0.12 for this path, including older profiles
  that saved a stronger value. Lower it if movement becomes too restrained.
- A hidden face, unsuitable head angle or insufficient alignment skips correction and the face
  anchor. It does not paste a front-facing portrait onto a turned-away head.
- Use one clear, prominent face. Manual bbox selects a region of the uploaded identity portrait;
  the current frame is detected independently. This is not multi-person identity tracking.
- The optional CPU YuNet/SFace models download once with time limits and atomic file replacement.
  No portrait is sent to a recognition API. Unavailable models leave a conservative fallback.

Starting a fresh ordinary scene without a separate portrait uses the original scene image as its
reference. An existing identity portrait stays in place on resume. **Exact identity across every
generated frame is not guaranteed**, especially on large turns, occlusion and long sequences.

Native MSR retains its subject-reference path. Motion control and the experimental internal
scene-chain sampler remain separate from this identity path; ordinary clip continuation works.
Starting a motion-driven scene does not silently enable an incompatible identity reference.

## 🔊 Native audio & soundtrack tools

LTX generates audio together with each clip. The joined video keeps those audio tracks; a clip
without audio receives silence so it can still be joined.

In Pro, use a short **audio reference** to guide the voice, with optional normalization and voice
isolation. Custom LoRA can use different strengths for video and audio.

**🎵 Soundtrack Mixer** fits an uploaded music or audio track to the current clip or joined video.
Loop a short track, fade it and choose whether to replace generated sound or mix with it at an
adjustable volume. Soundtrack fitting runs on the CPU.

## 🎛️ Pro — all tools & settings

| Tool | What you can do |
| --- | --- |
| **LoRA Studio** | Paste custom LoRA links, upload files and adjust video/audio strengths |
| **CivitAI search & shared library** | Discover adapters, read names and trigger words, and reuse saved entries |
| **Keyframes & Size** | Set an end frame and up to 5 intermediate frames, plus timing, strength and resolution |
| **Motion Control** | Guide movement with pose, depth or canny from a driving video |
| **Identity Lock** | Adjust reference strength, face targeting and advanced identity settings |
| **Audio Studio** | Supply an audio reference and tune how adapters affect sound |
| **Soundtrack Mixer** | Fit, loop or mix a track over the generated result |
| **JSON Profiles** | Save named setups or import and export the full scene plan |
| **GPU Budget & Speed** | Start with Economy or choose Fast, Balanced or Quality; inspect the requested allowance |
| **Runtime diagnostics** | Download recent process, memory and GPU-request events when investigating a restart |
| **Experiments** | Explore prompt relay, K/V conditioning and internal scene chaining |

The GPU estimate accounts for the scene's individual clip durations. It estimates the requested
allowance, not a guaranteed completion time.

## 💾 Save your scene plan

Profile schema v4 stores the scene idea, clip count, prompt sheet, per-clip times and automatic
planning preferences alongside the existing generation, audio, LoRA, identity and stitching
settings. Named profiles and downloaded JSON files use the same import/export path.

Older profiles still load. Existing v3 clip sheets are retained, while missing timing and planning
fields reset to their defaults. Profiles without a scene sheet start with an empty one. Loading a
profile resets **Start at clip** to 1; uploaded images, audio and generated clips are not included
in settings JSON. Named profiles inside the Space are shared with its visitors.

## Custom LoRA

Use one adapter per line: a Hugging Face repo (`owner/repo`), a repo with a filename
(`owner/repo:file.safetensors`), a CivitAI download link or another `.safetensors` link. Uploaded
LoRA files are also supported. The first thirteen lines have strength sliders; additional lines
can specify strengths directly, such as `owner/repo | 0.8 | 0` for video without audio influence.
Numbers on the line take priority over sliders.

Press **download / check lora** to fetch files in advance. Generation also prefetches selected
adapters before requesting the video GPU. The shared
library stores names, trigger words and strengths for reuse by the Space's visitors.

## Please read before uploading a photograph

Upload only photographs of yourself, or of people who have agreed to this. Sexual imagery of a real
person made without their consent breaks Hugging Face's
[content policy](https://huggingface.co/content-policy) and is not welcome here. The same applies to
anything involving a minor, in any form, without exception.

## Notes for the Space owner

- `EXPANDER_SPACE` sets the initial writing Space used by prompt assistance and scene planning.
- **Public AI writing follows the current visitor's browser access**, with no mandatory app
  login. Missing OAuth is not treated as proof of anonymous platform access. Gradio's trusted
  ZeroGPU forwarding header is captured inside the callback before client worker threads run.
- An optional personal login appears in a collapsed accordion beside prompt assistance.
  Complete it in the app's own tab when needed. It requests `inference-api`, with no repository
  write or billing-management permission. An expired personal login must be refreshed.
- `HF_TOKEN`, cached Hub credentials, `PLANNER_HF_TOKEN` and `EXPANDER_HF_TOKEN` are never used
  for LTX AI writing. The existing download/catalogue paths can still use `HF_TOKEN`.
- Upload **both app.py and README.md**. `hf_oauth: true` enables optional personal sign-in.
  Gradio's small `authlib` / `itsdangerous` extras install during CPU startup if needed; they
  may also be added to the existing requirements.txt. Public writing and video tools remain
  available if optional login setup is unavailable.
- Each request creates and closes its own client. Visitor tokens, forwarded quota headers and
  remote chat sessions are not kept in a shared client cache or exported in profiles.
- **Personal sign-in is not a free-only mode.** The visitor's included quota and prepaid-credit
  rules apply to their own requests. Hugging Face may automatically use that visitor's prepaid
  credits after their daily quota is exhausted. Another visitor's app sign-in never selects
  the owner's token as a fallback. The app does not change account billing settings.
- Each writer request submits one job. Failure or a five-minute timeout does not replay it through
  alternate endpoints. Cancellation is best effort: a job that has already started may still run.
  Prompt preparation can make one writing call plus one adapter-selection call; longer scene
  plans can use several batches. Refresh itself never submits an AI job.
- This code cannot identify past account charges or disable billing in other Spaces. Check the
  detailed usage records to distinguish video GPU work from remote writing/encoding services.
- The README keeps `sdk_version: 5.44.1`, `python_version: '3.12'`, `app_file: app.py` and the
  existing pinned setting.

* The distilled *fast lora* the workflow needs is always loaded automatically.
* CivitAI downloads run on the Space's machine, not in your browser, so being signed in there does
  not help a gated model: set `CIVITAI_TOKEN` under *Settings → Variables and secrets*.
* The lora library writes to a dataset bucket, so it needs an `HF_TOKEN` with write access under the
  same settings page. Without one the list is still readable, only nothing new can be saved. Point it
  somewhere else with `LORA_LIBRARY_REPO` if you duplicate the Space.
* Longer durations and motion control need more GPU work; the readout estimates the requested
  reservation. It does not report the actual charge.
* Motion control: **canny** and **depth** work out of the box. **Pose** pulls `controlnet_aux` and
  `onnxruntime` down the first time it is used, so the first pose track takes a few minutes longer
  than the ones after it.
* A prepared control track is rebuilt if the render size or the clip length changed after you made
  it, so the preview and the run never disagree.
* Profiles live inside the Space. With persistent storage attached they survive a restart, and they
  are visible to everyone who opens the Space.

ALL GENERATED CONTENT MUST FOLLOW HUGGINGFACE POLICY.

## Execution and recovery

The scene runner requests one clip at a time and schedules the next only while work remains.
There is no fixed chain of 64 empty callbacks after a short scene. The scene button becomes
available again on completion, Stop or a handled error. Finished clips remain in the queue.
Use **🔗 Join queued clips / retry** to retry stitching without generating or adding a clip again.
Stitching subprocesses have time limits; an incomplete merge is not presented as success.
Failed generation does not automatically join an old video. Heavy generation, local enhancement,
control-track preparation and stitching handlers share a concurrency limit of one.

Each joined clip is normalized once to a common 24 fps size, with audio preserved or silence
inserted when needed. Explicit video durations bound audio padding, including subsecond clips.
Normalized clip caches are bounded, and completed clips remain available after a join error.
The local prompt-enhancer process is stopped after use; Comfy execution closes its event loop
and refuses to substitute an unrelated old video when a run returns no output.

Open **🩺 Runtime diagnostics** and download a report after a suspected restart. It records boot
identifiers, process memory and available container OOM counters in a bounded log, without prompts
or token values. Persistence across a container replacement depends on attached storage. These
records help diagnose a crash; they do not guarantee that every crash cause is eliminated.

The app still relies on the Space's existing model files, helper modules and dependencies.
Replace `app.py` and this `README.md` in the corresponding Space; this update is not a complete
standalone repository. Local checks cover planner/profile compatibility, looping LoRA selection and trigger replacement,
explicit authentication, per-visitor session/header isolation without AI calls,
real Gradio callback/session propagation, streaming clip/join/cancel stages, face geometry and workflow routing,
one-job failure handling, CPU/GPU call ordering, cleanup, Gradio event
bindings and real ffmpeg joins with mixed audio/video and subsecond clips. All 60 local checks passed without any AI/GPU request. GPU model inference and the live browser
workflow must be verified in the Space; these checks do not measure visual identity fidelity.

LoRA download caches distinguish the complete source URL or repository/file pair, so two
adapters named `model.safetensors` cannot silently reuse each other’s weights.

Writer access references: [Qwen Space source](https://huggingface.co/spaces/amisima/Qwen3.8-27B-Uncensored-Demo/blob/main/app.py),
[ZeroGPU quotas and credit use](https://huggingface.co/docs/hub/en/spaces-zerogpu#usage-tiers),
[Hugging Face app sign-in](https://huggingface.co/docs/hub/en/spaces-oauth).
