"""Read an owner-approved per-job frame from shared studio storage.

File version: 1.0.1. No writes, generation, retries, or canonical registration.
"""
FILE_VERSION = "1.0.1"
import hashlib
import io
import json
from pathlib import Path
import re
from PIL import Image

BUCKET = "Dezz-9-10/J.O.A.T.-Studio-storage"
ROOT = Path("/studio/joat-studio")
HEX = re.compile(r"[0-9a-f]{64}")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_manifest(path):
    p = Path(path or "")
    if not p.is_file() or p.stat().st_size > 1024 * 1024:
        raise ValueError("Upload the saved approved_job_reference.json under 1 MiB.")
    value = json.loads(p.read_text())
    if not isinstance(value, dict):
        raise ValueError("Approved reference must be a JSON object.")
    if value.get("schema") == "joat.studio_storage_migration.v1":
        if (value.get("status") != "copied_and_readback_verified"
            or value.get("destination_bucket") != BUCKET
            or value.get("destination_mount") != "/studio"
            or not isinstance(value.get("selected_approved_reference"), dict)):
            raise ValueError("Use a successful studio storage migration receipt containing its approved reference.")
        value = value["selected_approved_reference"]
    return value


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema") != "joat.approved_job_reference.v1":
        raise ValueError("Use the saved approved job reference, not its preview or candidate review.")
    asset = manifest.get("asset_id", "")
    if not HEX.fullmatch(asset):
        raise ValueError("Invalid approved reference asset ID.")
    if fingerprint({k: v for k, v in manifest.items() if k != "fingerprint"}) != manifest.get("fingerprint"):
        raise ValueError("Approved reference manifest fingerprint mismatch.")
    d = manifest.get("descriptor", {})
    if (d.get("schema") != "joat.approved_job_reference_descriptor.v1"
        or d.get("asset_id") != asset
        or fingerprint({k: v for k, v in d.items() if k != "asset_id"}) != asset):
        raise ValueError("Approved descriptor fingerprint mismatch.")
    approval = manifest.get("owner_approval", {})
    if (approval.get("owner") != "Dezz-9-10" or not approval.get("approved_at")
        or approval.get("kind") != "visual_job_reference"
        or approval.get("descriptor_fingerprint") != asset):
        raise ValueError("Original owner reference approval is missing.")
    if d.get("role") != "shot_start_frame":
        raise ValueError("Only an approved shot_start_frame can condition this route.")
    expected = f"hf://buckets/{BUCKET}/joat-studio/approved-references/{asset}/image.png"
    if manifest.get("image_uri") != expected:
        raise ValueError("Approved frame must be in the dedicated studio bucket.")
    scope = d.get("scope", {})
    for key in ("project_id", "scene_id", "shot_id", "character_id", "environment_id"):
        if not isinstance(scope.get(key), str) or not scope[key].strip():
            raise ValueError("Missing approved reference scope: " + key)
    plan = d.get("plan", {})
    if fingerprint({k: v for k, v in plan.items() if k != "fingerprint"}) != plan.get("fingerprint"):
        raise ValueError("Source image plan fingerprint mismatch.")
    if plan.get("mission") != " / ".join(scope[k] for k in ("project_id", "scene_id", "shot_id")):
        raise ValueError("Source image mission differs from approved scope.")
    binding = d.get("canonical_identity_binding", {})
    if binding.get("character_id") != scope["character_id"] or binding.get("status") != "canonical_source_hash_matched":
        raise ValueError("Canonical character binding is missing.")
    identities = [r.get("sha256") for r in plan.get("references", []) if r.get("role") == "identity"]
    if identities != [binding.get("identity_source_sha256")]:
        raise ValueError("Image source identity and approved binding differ.")
    return d


def _safe_file(folder, filename):
    p = folder / filename
    if p.is_symlink() or not p.is_file():
        raise ValueError("Approved storage file is missing or is a symlink: " + filename)
    return p


def load_approved_frame(manifest, root=ROOT):
    d = validate_manifest(manifest)
    root = Path(root)
    parent = root / "approved-references"
    folder = parent / manifest["asset_id"]
    if root.is_symlink() or parent.is_symlink() or folder.is_symlink():
        raise ValueError("Approved storage path cannot be a symlink.")
    stored = read_manifest(_safe_file(folder, "manifest.json"))
    if stored != manifest:
        raise ValueError("Uploaded reference differs from the saved studio record.")
    image = _safe_file(folder, "image.png")
    if image.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Approved PNG exceeds 25 MiB.")
    raw = image.read_bytes()
    if len(raw) != d.get("size_bytes") or hashlib.sha256(raw).hexdigest() != d.get("image_sha256"):
        raise ValueError("Stored PNG differs from the approved image hash/size.")
    with Image.open(io.BytesIO(raw)) as img:
        if img.format != "PNG" or img.size != (d.get("width"), d.get("height")) or img.width * img.height > 20_000_000:
            raise ValueError("Stored PNG dimensions/format differ from approval.")
        img.load()
    review = read_manifest(_safe_file(folder, "candidate_review.json"))
    plan = review.get("plan", {})
    # Preserve the established JSON display normalization, only against signed plan.
    if fingerprint({k: v for k, v in plan.items() if k != "fingerprint"}) != plan.get("fingerprint"):
        plan = dict(plan)
        if plan.get("guidance_scale") == 1:
            plan["guidance_scale"] = 1.0
        review = dict(review, plan=plan)
    if (fingerprint(review) != d.get("candidate_review_sha256") or plan != d["plan"]
        or review.get("schema") != "joat.mission_reference_candidate.v1"
        or review.get("sha256") != d["image_sha256"]):
        raise ValueError("Stored source review differs from the approved descriptor.")
    return image


def bind_character(manifest, character):
    d = validate_manifest(manifest)
    binding = d["canonical_identity_binding"]
    if (d["scope"]["character_id"] != character.get("character_id")
        or character.get("source_asset_hashes", {}).get(binding.get("identity_asset_id"))
            != binding["identity_source_sha256"]):
        raise ValueError("Approved frame belongs to a different canonical character anchor.")
    return d


def reference_entry(manifest, character, environment, context):
    d = bind_character(manifest, character)
    scope = d["scope"]
    if any(scope[k] != context.get(k) for k in ("project_id", "scene_id", "shot_id")):
        raise ValueError("Approved frame belongs to a different job/scene/shot.")
    if scope["environment_id"] != environment.get("environment_id"):
        raise ValueError("Approved frame belongs to a different environment.")
    return {"asset_id": manifest["asset_id"], "sha256": d["image_sha256"],
        "path": "image.png", "url": manifest["image_uri"],
        "approved_job_reference": manifest}
