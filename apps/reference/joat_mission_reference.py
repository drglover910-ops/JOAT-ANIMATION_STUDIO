# joat_mission_reference.py — FILE VERSION: 1.0.3
"""J.O.A.T. mission reference candidates. File version 1.0.3.

Additive workflow: originals and canonical/GHL registries remain untouched.
"""
import hashlib
import io
import json
import os
import tempfile
import threading
import time
from pathlib import Path

import gradio as gr
from PIL import Image, ImageOps

FILE_VERSION = "1.0.3"
ROOT = Path(tempfile.gettempdir()) / "joat-mission-reference"
LOCK = threading.Lock()
OWNER = "Dezz-9-10"
MODEL = "Qwen/Qwen-Image-Edit-2511"
OUTPUT_WIDTH = 1024
OUTPUT_HEIGHT = 576
GPU_SECONDS = 600


def require_owner(profile):
    if profile is None or profile.username.casefold() != OWNER.casefold():
        raise ValueError("Sign in as the studio owner.")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def read_reference(path, role):
    if not path:
        raise ValueError("Missing " + role + " reference.")
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Reference must be an image under 25 MiB.")
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as opened:
        if opened.width * opened.height > 20_000_000:
            raise ValueError("Reference exceeds 20 megapixels.")
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.load()
    return image, {"role": role, "sha256": hashlib.sha256(raw).hexdigest(),
                   "width": image.width, "height": image.height}


def prepare(identity, second_identity, environment, wardrobe, mission, prompt, confirmed):
    if confirmed is not True:
        raise ValueError("Confirm the identity and individual reference roles first.")
    if not mission or not mission.strip() or len(mission) > 160:
        raise ValueError("Enter a mission identifier (maximum 160 characters).")
    if not prompt or not prompt.strip() or len(prompt) > 4000:
        raise ValueError("Enter the exact image instruction (maximum 4000 characters).")
    images, refs = [], []
    for role, path in (("identity", identity), ("second_same_character_identity", second_identity),
                       ("environment", environment), ("wardrobe_support", wardrobe)):
        if path or role == "identity":
            image, ref = read_reference(path, role)
            images.append(image)
            refs.append(ref)
    instructions = "\n".join("Image %d: %s." % (i + 1, ref["role"]) for i, ref in enumerate(refs))
    instructions += ("\nProduce ONE proposed production reference image, not a card, grid or collage. "
                     "Preserve the character identity from the identity image(s). "
                     "Environment and wardrobe references must not replace facial identity. "
                     "Do not reproduce borders, labels or sheet layouts.\nRequested image: " + prompt.strip())
    plan = {"schema": "joat.mission_reference_plan.v1", "file_version": FILE_VERSION,
            "mission": mission.strip(), "model": MODEL, "references": refs,
            "prompt": instructions, "seed": 42, "guidance_scale": 1.0, "steps": 50,
            "width": OUTPUT_WIDTH, "height": OUTPUT_HEIGHT, "gpu_reservation_seconds": GPU_SECONDS,
            "candidate_only": True, "canonical_registration": False, "qc_approved": False}
    plan["fingerprint"] = fingerprint(plan)
    return plan, images


def claim(plan):
    """Persist before invoking a provider; uncertain submissions never auto-retry."""
    unsigned = {k: v for k, v in plan.items() if k != "fingerprint"}
    if plan.get("fingerprint") != fingerprint(unsigned):
        raise ValueError("Plan fingerprint mismatch.")
    from joat_job_assets import AssetStore
    # Preserve local duplicate evidence from older releases before claiming durably.
    if (ROOT / (plan["fingerprint"] + ".attempt.json")).exists():
        raise ValueError("This exact plan was already attempted. No duplicate GPU request was sent.")
    return AssetStore().claim_attempt(plan)


def add_mission_ui(generate):
    from joat_saved_reference_plan import stage_proposals, read_latest, prepare_files
    stage_proposals()
    with gr.Tab("Mission Reference Candidates"):
        gr.Markdown("### Mission references v1.0.3\nPrepare one needed image from one or two identity photos, "
                    "with optional individual environment and wardrobe references. "
                    "Review outputs in Approved Job References to save them. Originals are preserved. "
                    "Candidate PNG/JSON is temporary until approved and saved. Attempt records use studio storage; a missing mount blocks generation.")
        gr.LoginButton()
        mission = gr.Textbox(label="Mission identifier", value="PROJECT-001 / SCENE-001 / SHOT-001")
        identity = gr.Image(label="Original identity portrait — one character", type="filepath")
        second = gr.Image(label="Optional second identity photo — same character", type="filepath")
        environment = gr.Image(label="Optional individual environment view", type="filepath")
        wardrobe = gr.Image(label="Optional individual wardrobe/body support", type="filepath")
        prompt = gr.Textbox(label="Exact proposed image instruction", lines=5)
        roles = gr.Checkbox(label="I reviewed these individual reference roles; identity photos show the same character")
        state = gr.State(None)
        plan_view = gr.JSON(label="CPU-only candidate plan — review before GPU approval")
        approval = gr.Checkbox(label="Approve ONE GPU candidate generation for this exact plan")
        output = gr.Image(label="Candidate only — not approved or registered", type="filepath")
        export = gr.File(label="Download candidate review or failure JSON")

        def build(a, b, c, d, m, p, confirmed, profile: gr.OAuthProfile | None):
            try:
                require_owner(profile)
                plan, _ = prepare(a, b, c, d, m, p, confirmed)
                return plan, plan, False, None, None
            except Exception as exc:
                raise gr.Error(str(exc)) from None

        def execute(plan, a, b, c, d, m, p, confirmed, approved,
                    profile: gr.OAuthProfile | None):
            try:
                require_owner(profile)
                if approved is not True or not plan:
                    raise ValueError("Prepare and review a plan, then approve one GPU generation.")
                current, images = prepare(a, b, c, d, m, p, confirmed)
                if current != plan:
                    raise ValueError("Inputs changed; prepare a new plan before generation.")
                ledger = claim(plan)
            except Exception as exc:
                raise gr.Error(str(exc)) from None
            started = time.monotonic()
            phase = "gpu_generation"
            try:
                print("JOAT_MISSION_START " + json.dumps({"fingerprint": plan["fingerprint"],
                      "width": OUTPUT_WIDTH, "height": OUTPUT_HEIGHT, "steps": 50,
                      "gpu_reservation_seconds": GPU_SECONDS}), flush=True)
                result = generate(images, plan["prompt"])
                phase = "validate_candidate"
                if result.size != (OUTPUT_WIDTH, OUTPUT_HEIGHT):
                    raise ValueError("Candidate dimensions differ from the approved plan.")
                phase = "export_candidate"
                folder = ROOT / plan["fingerprint"]
                folder.mkdir(mode=0o700, parents=True, exist_ok=True)
                image_path = folder / "candidate.png"
                result.save(image_path, format="PNG")
                evidence = {"schema": "joat.mission_reference_candidate.v1", "file_version": FILE_VERSION,
                            "plan": plan, "status": "awaiting_independent_review",
                            "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                            "width": result.width, "height": result.height,
                            "identity_verified": False, "qc_approved": False,
                            "canonical_registration": False, "automatic_retry": False}
                report = folder / "candidate_review.json"
                report.write_text(json.dumps(evidence, indent=2))
                ledger.write_text(json.dumps({"status": "candidate_received", "sha256": evidence["sha256"]}))
                return str(image_path), str(report), False
            except Exception as error:
                # Retain safe diagnostics; raw exceptions can contain credentials/URLs.
                message = str(error).casefold()
                flags = {"gpu_aborted": "gpu task aborted" in message,
                         "timeout_reported": "timeout" in message or "timed out" in message,
                         "oom_reported": "out of memory" in message,
                         "quota_reported": "quota" in message}
                failure = {"schema": "joat.mission_reference_failure.v1", "file_version": FILE_VERSION,
                           "status": "failed_or_unverified", "stage": phase,
                           "plan_fingerprint": plan["fingerprint"], "plan": plan,
                           "error_type": type(error).__name__, "diagnostic_flags": flags,
                           "elapsed_seconds": round(time.monotonic() - started, 3),
                           "automatic_retry": False, "qc_approved": False,
                           "canonical_registration": False}
                print("JOAT_MISSION_FAILURE " + json.dumps(failure), flush=True)
                folder = ROOT / plan["fingerprint"]
                folder.mkdir(mode=0o700, parents=True, exist_ok=True)
                report = folder / "candidate_failure.json"
                report.write_text(json.dumps(failure, indent=2))
                ledger.write_text(json.dumps(failure, indent=2))
                gr.Warning("Candidate failed or is unverified. Download the failure JSON; do not retry.")
                return None, str(report), False

        def load_saved(profile: gr.OAuthProfile | None):
            try:
                require_owner(profile)
                saved = read_latest()
                files = prepare_files(saved)
                return files[0], None, files[1], files[2], saved['mission'], saved['prompt'], True, None, None, False, None, None
            except Exception as exc:
                raise gr.Error(str(exc)) from None

        gr.Button("Load saved job reference proposal (no GPU)").click(
            load_saved, [], [identity, second, environment, wardrobe, mission, prompt, roles,
                             state, plan_view, approval, output, export], api_visibility="private")
        inputs = [identity, second, environment, wardrobe, mission, prompt, roles]
        gr.Button("Prepare mission reference plan (no GPU)").click(
            build, inputs, [state, plan_view, approval, output, export], api_visibility="private")
        gr.Button("Generate ONE approved candidate").click(
            execute, [state] + inputs + [approval], [output, export, approval],
            api_visibility="private", concurrency_limit=1)
        for component in inputs:
            component.change(lambda: (None, None, False, None, None),
                             outputs=[state, plan_view, approval, output, export], api_visibility="private")
