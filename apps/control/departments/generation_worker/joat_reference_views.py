"""joat_reference_views.py file version 1.0.0: CPU candidate views, never render approvals."""
FILE_VERSION = "1.0.0"

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image


REVIEW_JOB = "0742f79a5e1a9bc19a02b1d46db981b3d90343ae71f777f0476fd6eed501e02a"
# Bounds are proposals based on the owner-supplied sheets, not automatic
# segmentation or approved replacements for their original locked assets.
VIEW_RULES = {
    "image_path": {"name": "Founder_identity_original.jpeg", "size": (1122, 1402),
                   "bounds": None, "role": "identity_evidence"},
    "msr_background": {"name": "Office_frontal_CANDIDATE.png", "size": (1536, 1024),
                       "bounds": (2, 2, 905, 416), "role": "environment_view_candidate"},
    "msr_ref2": {"name": "Founder_office_support_CANDIDATE.png", "size": (1312, 1199),
                 "bounds": (5, 124, 321, 403), "role": "wardrobe_body_support_candidate"},
}


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def create_candidates(sources, expected_hashes, destination, source_job_fingerprint):
    """Pure local image preparation; network/GPU/registry writes are absent."""
    if set(sources) != set(VIEW_RULES) or set(expected_hashes) != set(VIEW_RULES):
        raise ValueError("Exactly the three reviewed reference roles are required")
    destination = Path(destination)
    if not destination.is_dir():
        raise ValueError("Candidate output directory is unavailable")
    # Validate ALL inputs before creating any candidates. A hash mismatch,
    # different source layout or oversized/invalid file cannot create a
    # misleading partial review bundle.
    for key, rule in VIEW_RULES.items():
        path = Path(sources[key])
        if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Invalid reference size: " + key)
        if file_hash(path) != expected_hashes[key]:
            raise ValueError("Locked reference hash mismatch: " + key)
        with Image.open(path) as image:
            if image.size != rule["size"] or getattr(image, "n_frames", 1) != 1:
                raise ValueError("Source layout differs from the reviewed reference: " + key)
            # Coordinates refer to the displayed source orientation. Reject
            # rotated original sources instead of guessing alternate bounds.
            if image.getexif().get(274, 1) != 1:
                raise ValueError("Source orientation requires a fresh view review: " + key)
            image.load()

    entries = []
    outputs = {}
    for key, rule in VIEW_RULES.items():
        source = Path(sources[key])
        target = destination / rule["name"]
        if rule["bounds"] is None:
            shutil.copyfile(source, target)  # Preserve exact identity bytes.
        else:
            with Image.open(source) as image:
                # PNG stores the selected original pixels losslessly. No
                # resize, stretch, enhancement or generative edit occurs.
                image.crop(rule["bounds"]).save(target, format="PNG")
        with Image.open(target) as image:
            size = image.size
        outputs[key] = str(target)
        entries.append({"role": rule["role"], "source_parameter": key,
                        "source_sha256": expected_hashes[key],
                        "candidate_filename": target.name,
                        "candidate_sha256": file_hash(target),
                        "width": size[0], "height": size[1],
                        "source_size": list(rule["size"]),
                        "crop_bounds_pixels": list(rule["bounds"]) if rule["bounds"] else None,
                        "operation": "exact_original_copy" if rule["bounds"] is None else "pixel_crop_to_lossless_png",
                        "status": "identity_evidence" if rule["bounds"] is None else "pending_view_review"})
    manifest = {"schema": "joat.reference_view_review.v1", "file_version": FILE_VERSION,
                "source_job_fingerprint": source_job_fingerprint,
                "status": "candidate_views_prepared", "gpu_called": False,
                "model_called": False, "original_assets_changed": False,
                "source_job_changed": False, "ready_for_render": False,
                "qc_approved": False, "registered_with_masters": False,
                "entries": entries,
                "warnings": [
                    "Candidate crops require visual review; they are not approved render references.",
                    "The office-support character panel includes a hand-at-chin pose, not the approved neutral performance.",
                    "The identity portrait contains sunglasses, so it does not provide visible eye evidence for blink review.",
                    "Do not substitute these files into the old locked job. Responsible Masters must register approved task-specific assets and produce a new approved packet chain.",
                    "The Worker temporary files are downloads, not a durable asset archive."],
                "next_action": "Review views, then register accepted task-specific references through the existing Character/Environment Masters."}
    core = json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    manifest["review_fingerprint"] = hashlib.sha256(core.encode()).hexdigest()
    manifest_path = destination / "reference_view_review_v1.0.0.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest, outputs, str(manifest_path)


def prepare_reference_review(worker, packet, plan):
    # Import only inside this owner-gated operation; no model/provider import.
    from joat_render_bridge import prepare_plan, download_reference
    if plan != prepare_plan(worker, packet):
        raise ValueError("Prepared plan changed")
    if plan["source_job_fingerprint"] != REVIEW_JOB:
        raise ValueError("These reviewed sheet bounds apply only to the current Founder/Office diagnostic job")
    references = {key: plan["references"][key] for key in VIEW_RULES}
    if any(Path(ref["path"]).name != expected for ref, expected in [
        (references["image_path"], "1AFA568E-6872-4453-A76C-633D6B4E577F.jpeg"),
        (references["msr_ref2"], "4F168803-BC4E-4B8E-B5BE-5CA9547A042B.jpeg"),
        (references["msr_background"], "ENV-008_office_identity_anchor.jpeg"),
    ]):
        raise ValueError("Reviewed asset bindings changed")
    directory = Path(tempfile.mkdtemp(prefix="joat-reference-review-"))
    try:
        sources = {key: download_reference(ref, directory) for key, ref in references.items()}
        return create_candidates(sources, {key: ref["sha256"] for key, ref in references.items()},
                                 directory, plan["source_job_fingerprint"])
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
