"""Compile a locked single shot for LTX without changing its source packets.

File version: 1.0.5
The caller must first validate the Supervisor/Worker packet fingerprints. This
module checks that the selected approved shot agrees with its specialist inputs;
it does not approve creative decisions or mutate assets. The complete contract
remains outside the renderer's text input and is bound by the manifest hashes.
"""

import hashlib
import json
import math

FILE_VERSION = "1.0.5"
FRAME_COMPILATION_VERSION = "1.0.3"
NATIVE_COMPILATION_VERSION = "1.0.1"
LEGACY_COMPILATION_VERSION = "1.0.0"
MAX_POSITIVE_CHARACTERS = 10000
MAX_NEGATIVE_CHARACTERS = 6000
REFERENCE_LAYOUT_GUARD = (
    "Use reference images for identity and setting, rather than reproducing their reference-sheet layout."
)
REFERENCE_LAYOUT_NEGATIVE = "contact sheet, collage, grid, reference labels"

SCHEMAS = {
    "character_packet": "joat.character_packet.v1",
    "environment_packet": "joat.environment_packet.v1",
    "director_packet": "joat.director_packet.v1",
    "shot_camera_packet": "joat.shot_camera_packet.v1",
    "performance_action_packet": "joat.performance_action_packet.v1",
}


def _stable(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_stable(value).encode("utf-8")).hexdigest()


def _text_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping(value, name):
    if not isinstance(value, dict):
        raise ValueError("Approved prompt field must be an object: " + name)
    return value


def _string(value, name, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError("Approved prompt text is missing: " + name)
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Approved prompt number is invalid: " + name)
    return float(value)


def _seconds(value):
    text = _string(value, "director duration")
    parts = text.split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Unsupported approved Director duration")
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        raise ValueError("Unsupported approved Director duration") from None
    if any(not math.isfinite(part) or part < 0 for part in numbers):
        raise ValueError("Invalid approved Director duration")
    if any(part >= 60 for part in numbers[1:]):
        raise ValueError("Invalid approved Director duration")
    total = 0.0
    for part in numbers:
        total = total * 60 + part
    return total


def _normal(value):
    return _string(value, "camera decision").strip().lower().replace("_", "-")


def _strings(value, name):
    if not isinstance(value, list):
        raise ValueError("Approved constraints must be a list: " + name)
    return [_string(item, name) for item in value]


def _plain(value, name, depth=0):
    """Human text from approved leaf values; no JSON or metadata serialization."""
    if depth > 5:
        raise ValueError("Approved prompt field is too deeply nested: " + name)
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or value is None:
        raise ValueError("Unsupported approved descriptive value: " + name)
    if isinstance(value, (int, float)):
        _number(value, name)
        return format(value, "g")
    if isinstance(value, list):
        return "; ".join(_plain(item, name, depth + 1) for item in value)
    if isinstance(value, dict):
        return "; ".join(
            str(key).replace("_", " ") + ": " + _plain(value[key], name + "/" + str(key), depth + 1)
            for key in sorted(value)
        )
    raise ValueError("Unsupported approved descriptive value: " + name)


def compile_approved_scene(prompt_contract, project_context, generation_specification, approved_composed_frame=False):
    """Return positive_prompt, negative_prompt, and a deterministic source manifest.

    Only the existing approved single-character/single-environment Director
    schema is supported. Missing, ambiguous, conflicting, or oversized inputs
    fail before any GPU call. Constraints not repeated in prose are retained
    verbatim in the manifest and bound to the full immutable source contract.
    """
    contract = _mapping(prompt_contract, "prompt_contract")
    context = _mapping(project_context, "project_context")
    specification = _mapping(generation_specification, "generation_specification")
    packets = {}
    for key, schema in SCHEMAS.items():
        packets[key] = _mapping(contract.get(key), key)
        if packets[key].get("schema") != schema:
            raise ValueError("Unsupported approved packet schema: " + key)
    character = packets["character_packet"]
    environment = packets["environment_packet"]
    director = packets["director_packet"]
    camera = packets["shot_camera_packet"]
    performance = packets["performance_action_packet"]

    for packet, field in ((character, "identity_locked"), (environment, "environment_locked"),
                          (camera, "camera_locked"), (performance, "performance_locked")):
        if packet.get(field) is not True:
            raise ValueError("Approved scene requires its existing lock: " + field)
    approval = _mapping(director.get("approval"), "director approval")
    if approval.get("creative_intent_locked") is not True:
        raise ValueError("Director creative intent is not approved and locked")
    _string(approval.get("approved_by"), "director approved_by")

    for key in ("project_id", "scene_id", "shot_id"):
        _string(context.get(key), "project_context/" + key)
    if director.get("project_id") != context["project_id"]:
        raise ValueError("Director and generation project differ")
    for packet in (camera, performance):
        for key in ("project_id", "scene_id", "shot_id"):
            if packet.get(key) != context[key]:
                raise ValueError("Specialist and generation context differ: " + key)
    environment_scene = _mapping(environment.get("scene_context"), "environment scene_context")
    for key in ("scene_id", "shot_id"):
        _string(environment_scene.get(key), "environment source context/" + key)
    environment_origin_reused = any(environment_scene.get(key) != context[key] for key in ("scene_id", "shot_id"))

    shots = director.get("per_shot")
    if not isinstance(shots, list) or not all(isinstance(shot, dict) for shot in shots):
        raise ValueError("Director per_shot decisions are missing")
    matches = [(index, shot) for index, shot in enumerate(shots) if shot.get("shot_id") == context["shot_id"]]
    if len(matches) != 1:
        raise ValueError("Director shot selection is missing or ambiguous")
    shot_index, shot = matches[0]
    if shot.get("scene_id") != context["scene_id"]:
        raise ValueError("Director and generation scene differ")
    if environment_origin_reused:
        # A reviewed project may explicitly reuse one locked environment Master
        # across shots. Its original scene_context remains immutable provenance.
        assignment = director.get("project_assignment", {})
        original_hash = assignment.get("original_director_sha256", "")
        if (assignment.get("owner_review_required") is not True
            or assignment.get("assigned_project_id") != context["project_id"]
            or not isinstance(original_hash, str) or len(original_hash) != 64
            or any(char not in "0123456789abcdef" for char in original_hash)
            or not isinstance(assignment.get("original_project_id"), str)
            or not assignment["original_project_id"]
            or approval.get("approved_by") != "Dezz-9-10"
            or shot.get("environment_requirements") != environment.get("environment_id")
            or not environment.get("source_asset_hashes")):
            raise ValueError("Environment origin differs without an exact owner-reviewed environment reuse")
    for group in ("camera_framing", "performance_action", "dialogue_narration", "audio_music_sfx", "caption_on_screen_text"):
        selected_values = _mapping(shot.get(group), "shot " + group)
        if selected_values.get("shot_id") != context["shot_id"]:
            raise ValueError("Director decisions belong to a different shot: " + group)
        if group in director:
            global_values = director[group]
            if not isinstance(global_values, list) or not all(isinstance(item, dict) for item in global_values):
                raise ValueError("Unsupported Director decision list: " + group)
            matching_values = [item for item in global_values if item.get("shot_id") == context["shot_id"]]
            if matching_values != [selected_values]:
                raise ValueError("Director summary and selected shot decisions differ: " + group)
    character_id = _string(character.get("character_id"), "character_id")
    environment_id = _string(environment.get("environment_id"), "environment_id")
    native_requested = "visible_cast_supplement" in director
    native_prompt = None
    if native_requested:
        supplement = _mapping(director["visible_cast_supplement"], "visible cast supplement")
        provenance = _mapping(approval.get("source_script_review"), "original script review")
        ids = shot.get("character_ids")
        if (approved_composed_frame is not True or specification.get("aspect_ratio") != "9:16"
            or provenance.get("owner") != "Dezz-9-10" or provenance.get("reviewer") != "Codex"
            or provenance.get("scope") != "original_owner_script_machine_verified_packet_mapping"
            or provenance.get("project_id") != context["project_id"]
            or supplement.get("source_shot_id") != context["shot_id"]
            or not isinstance(ids, list) or not 1 <= len(ids) <= 3 or ids[0] != character_id
            or len(set(ids)) != len(ids)):
            raise ValueError("Exact original-script composed-frame context required")
        visible = _mapping(supplement.get("character_packets"), "visible character packets")
        hashes = _mapping(supplement.get("source_asset_hashes"), "visible source hashes")
        refs = {r.get("character_id"): r for r in director.get("character_refs", [])}
        if set(visible) != set(ids) or set(hashes) != set(ids):
            raise ValueError("Visible character identities differ from the shot")
        for cid in ids:
            value = _mapping(visible[cid], "visible character")
            if (value.get("schema") != SCHEMAS["character_packet"] or value.get("character_id") != cid
                or value.get("identity_locked") is not True or not value.get("source_asset_hashes")
                or hashes[cid] != value["source_asset_hashes"]
                or shot.get("all_visible_character_source_hashes", {}).get(cid) != hashes[cid]
                or refs.get(cid, {}).get("source_asset_hashes") != hashes[cid]
                or refs.get(cid, {}).get("identity_lock_asset") != value.get("identity_lock_asset")):
                raise ValueError("Visible character canonical lock/hash differs")
        if visible[character_id] != character:
            raise ValueError("Primary visible character differs from immutable Character Master")
        native_prompt = _string(supplement.get("native_render_prompt"), "locked native render prompt")
        expected_header = "Style001 " + context["project_id"] + " / " + context["scene_id"] + " / " + context["shot_id"]
        if not native_prompt.startswith(expected_header + "\n"):
            raise ValueError("Native prompt belongs to a different shot")
        dialogue = shot["dialogue_narration"].get("dialogue", "")
        if dialogue and (dialogue not in native_prompt or "Speak ONLY this exact line" not in native_prompt):
            raise ValueError("Native prompt lost the exact spoken line")
        if not dialogue and "no narration, dialogue, music or vocals" not in native_prompt:
            raise ValueError("Narrated scenes must keep spoken audio outside native generation")
    elif shot.get("character_ids") != [character_id]:
        raise ValueError("Only the approved single-character shot is supported")
    if performance.get("character_id") != character_id or performance.get("environment_id") != environment_id:
        raise ValueError("Performance character or environment differs from its locked sources")
    shot_character = _mapping(shot.get("character_constraints"), "shot character_constraints")
    for field in ("identity_locked", "identity_lock_asset", "appearance_rules", "continuity_rules", "negative_rules", "source_asset_hashes"):
        if shot_character.get(field) != character.get(field):
            raise ValueError("Director shot character constraints differ: " + field)
    _string(character.get("identity_lock_asset"), "character identity_lock_asset")
    _string(environment.get("identity_lock_asset"), "environment identity_lock_asset")

    seconds = _number(specification.get("duration_seconds"), "duration_seconds")
    if seconds <= 0 or abs(_seconds(shot.get("duration")) - seconds) > 1e-9:
        raise ValueError("Director and generation durations differ")
    aspect = _string(specification.get("aspect_ratio"), "aspect_ratio")
    camera_timing = _mapping(camera.get("timing"), "camera timing")
    if abs(_number(camera_timing.get("duration_seconds"), "camera duration_seconds") - seconds) > 1e-9:
        raise ValueError("Camera and generation durations differ")
    shot_camera = _mapping(shot.get("camera_framing"), "shot camera_framing")
    camera_values = _mapping(camera.get("camera"), "camera")
    for director_key, camera_key in (("framing", "shot_size"), ("angle", "angle"), ("movement", "movement")):
        if _normal(shot_camera.get(director_key)) != _normal(camera_values.get(camera_key)):
            raise ValueError("Director and Camera decisions differ: " + director_key)
    shot_action = _mapping(shot.get("performance_action"), "shot performance_action")
    performance_values = _mapping(performance.get("performance"), "performance")
    action = _string(shot_action.get("action"), "Director action")
    if performance_values.get("action") != action:
        raise ValueError("Director and Performance actions differ")

    frame_scoped = approved_composed_frame is True and director.get("project_assignment", {}).get("owner_review_required") is True and len(shots) == 1
    bindings = []
    retained_director = {}
    lines = []
    prefix = "/director_packet/per_shot/" + str(shot_index)

    def add(label, value, path, destination=lines):
        rendered = _plain(value, path)
        if rendered.strip():
            destination.append(label + ": " + rendered)
        bindings.append({"source_path": path, "source_value_sha256": _hash(value),
                         "destination": "positive_prompt" if destination is lines else "negative_prompt"})

    brief = _string(director.get("creative_brief"), "creative_brief")
    if frame_scoped:
        retained_director["creative_brief"] = brief
        bindings.append({"source_path": "/director_packet/creative_brief", "source_value_sha256": _hash(brief), "destination": "retained_constraints"})
        lines.append("Scene: Animate only the selected character performance in the approved composed starting frame. One continuous shot of the approved setting; preserve the frame's identity, wardrobe and environment.")
    else:
        add("Scene", brief, "/director_packet/creative_brief")
    add("Shot duration in seconds", seconds, "/generation_specification/duration_seconds")
    add("Aspect ratio", aspect, "/generation_specification/aspect_ratio")
    add("Character", _string(character.get("character_name"), "character_name"), "/character_packet/character_name")
    appearance = _mapping(character.get("appearance_rules"), "appearance_rules")
    if not appearance:
        raise ValueError("Approved character appearance rules are missing")
    for key in sorted(appearance):
        add("Appearance " + key.replace("_", " "), appearance[key], "/character_packet/appearance_rules/" + key)
    add("Environment", _string(environment.get("environment_name"), "environment_name"), "/environment_packet/environment_name")
    add("Environment requirements", _string(shot.get("environment_requirements"), "environment_requirements"), prefix + "/environment_requirements")
    environment_rules = _mapping(environment.get("environment_rules"), "environment_rules")
    add("Environment identity", _string(environment_rules.get("identity"), "environment identity"), "/environment_packet/environment_rules/identity")
    for key in sorted(environment_scene):
        if key not in ("scene_id", "shot_id"):
            add("Environment " + key.replace("_", " "), environment_scene[key], "/environment_packet/scene_context/" + key)
    for key in ("framing", "angle", "movement"):
        add("Camera " + key, shot_camera[key], prefix + "/camera_framing/" + key)
    for key in sorted(camera_values):
        if key not in ("shot_size", "angle", "movement"):
            add("Camera " + key.replace("_", " "), camera_values[key], "/shot_camera_packet/camera/" + key)
    add("Action", action, prefix + "/performance_action/action")
    for key in sorted(performance_values):
        if key != "action":
            add("Performance " + key.replace("_", " "), performance_values[key], "/performance_action_packet/performance/" + key)
    native_media_fields = False
    for group, fields in (("dialogue_narration", ("dialogue", "narration")),
                          ("audio_music_sfx", ("audio", "music", "sfx")),
                          ("caption_on_screen_text", ("caption", "on_screen_text"))):
        values = _mapping(shot.get(group), "shot " + group)
        if values.get("shot_id") != context["shot_id"]:
            raise ValueError("Director media decisions belong to a different shot: " + group)
        # Main's established Director input uses descriptive instructions/text.
        # Compile those exact approved leaves; never fill missing legacy fields.
        alternate = "instructions" if group == "audio_music_sfx" else "text" if group == "caption_on_screen_text" else None
        if alternate is not None and alternate in values:
            if set(values) != {"shot_id", alternate}:
                raise ValueError("Ambiguous approved media decisions: " + group)
            fields = (alternate,)
            native_media_fields = True
        for field in fields:
            value = _string(values.get(field), group + "/" + field, allow_empty=True)
            post_narration = frame_scoped and group == "dialogue_narration" and field == "narration" and "Voice-over added in post" in shot.get("audio_music_sfx", {}).get("instructions", "")
            if post_narration:
                retained_director["post_narration"] = value
                bindings.append({"source_path": prefix + "/" + group + "/" + field, "source_value_sha256": _hash(value), "destination": "retained_constraints"})
            else:
                add(field.replace("_", " ").capitalize(), value, prefix + "/" + group + "/" + field)
    for field in ("continuity_constraints", "generation_instructions"):
        add(field.replace("_", " ").capitalize(), _string(director.get(field), field), "/director_packet/" + field)

    # Descriptive continuity and identity constraints must reach the model,
    # as well as the provenance manifest. Do not leave them in metadata only.
    for key in ("character_packet", "environment_packet", "shot_camera_packet", "performance_action_packet"):
        packet = packets[key]
        role = key.removesuffix("_packet").replace("_", " ")
        if "continuity_rules" in packet:
            if frame_scoped and key in ("character_packet", "environment_packet"):
                # Identity/reference administration is preserved as provenance;
                # the composed frame and explicit visual rules guide synthesis.
                bindings.append({"source_path": "/" + key + "/continuity_rules", "source_value_sha256": _hash(packet["continuity_rules"]), "destination": "retained_constraints"})
            else:
                add(role + " continuity", packet["continuity_rules"], "/" + key + "/continuity_rules")
        if key == "environment_packet":
            for name in sorted(environment_rules):
                if name != "identity":
                    add("Environment " + name.replace("_", " "), environment_rules[name], "/environment_packet/environment_rules/" + name)
        continuity = packet.get("continuity", {})
        if isinstance(continuity, dict) and "continuity_rules" in continuity:
            add(role + " continuity", continuity["continuity_rules"], "/" + key + "/continuity/continuity_rules")
        for field in ("generation_constraints", "constraints"):
            constraints = packet.get(field, {})
            if not isinstance(constraints, dict):
                raise ValueError("Unsupported approved constraints: " + key + "/" + field)
            for name in sorted(constraints):
                value = constraints[name]
                path = "/" + key + "/" + field + "/" + name
                if isinstance(value, bool):
                    lines.append(role + " constraint " + name.replace("_", " ") + ": " + str(value).lower())
                    bindings.append({"source_path": path, "source_value_sha256": _hash(value), "destination": "positive_prompt"})
                else:
                    add(role + " constraint " + name.replace("_", " "), value, path)

    negative_lines = []
    retained_constraints = {}
    for key in ("character_packet", "environment_packet", "shot_camera_packet", "performance_action_packet"):
        packet = packets[key]
        retained_constraints[key] = {}
        for field in ("appearance_rules", "environment_rules", "continuity_rules", "continuity", "negative_rules", "generation_constraints", "constraints"):
            if field in packet:
                retained_constraints[key][field] = packet[field]
        if "negative_rules" in packet:
            for index, rule in enumerate(_strings(packet["negative_rules"], key + "/negative_rules")):
                add("Constraint", rule, "/" + key + "/negative_rules/" + str(index), negative_lines)

    # Apply the technical guard only to an explicit single-scene video intent.
    # Any mention of a deliberate layout leaves that creative decision alone.
    approved_scene_text = " ".join((director["creative_brief"], shot["environment_requirements"], action)).lower()
    layout_terms = ("contact sheet", "collage", "split-screen", "split screen", "grid", "reference sheet", "reference-sheet")
    single_scene_guard = (
        len(shots) == 1
        and director.get("production_intent") in ("animation", "video")
        and not any(term in approved_scene_text for term in layout_terms)
    )
    if single_scene_guard:
        lines.append(REFERENCE_LAYOUT_GUARD)
        negative_lines.append(REFERENCE_LAYOUT_NEGATIVE)

    artifact_guard = frame_scoped and all(shot.get("caption_on_screen_text", {}).get(key, "") == "" for key in ("text", "caption", "on_screen_text")) and "No extra people, captions or effects" in director.get("generation_instructions", "")
    if artifact_guard:
        lines.append("Keep a single full-frame cinematic scene for the entire clip. Show only the approved character, setting and scene props. Do not add portrait cards, inset faces, picture-in-picture windows, floating panels, interfaces, captions, logos or other overlays. Preserve the selected Director gaze and performance; add no unrequested actions.")
        negative_lines.append("picture-in-picture, portrait cards, duplicate faces, floating portraits, inset faces, inset panels, pop-up windows, UI overlays, text overlays, reference cards, split-screen")
    compact_frame_prompt = bool(artifact_guard and single_scene_guard)
    if compact_frame_prompt:
        # Administrative asset policies and lists of forbidden visual objects
        # are not descriptions of this scene. Retain them in full provenance,
        # rather than asking the image model to illustrate them.
        retained_constraints["render_administration"] = {
            "original_positive_text": "\n".join(lines),
            "original_negative_text": "\n".join(negative_lines),
            "original_source_bindings": json.loads(_stable(bindings)),
        }
        for binding in bindings:
            if binding.get("destination") in ("positive_prompt", "negative_prompt"):
                binding["destination"] = "retained_render_administration"
        lines[:] = [
            "One uninterrupted cinematic shot. Animate the single composed starting image as one continuous scene.",
            "Keep the same character's face, hair, skin tone, body, clothing and accessories, and the same physical room and lighting throughout.",
            "Keep the camera view filled by the same continuous room and its original scene objects throughout the entire shot.",
        ]
        for key in ("framing", "angle", "movement"):
            add("Camera " + key, shot_camera[key], prefix + "/camera_framing/" + key)
        add("Action", action, prefix + "/performance_action/action")
        for key in sorted(performance_values):
            if key != "action":
                add("Performance " + key.replace("_", " "), performance_values[key], "/performance_action_packet/performance/" + key)
        # Audio instructions stay exact; post narration remains separately bound.
        for field in ("instructions", "audio", "music", "sfx"):
            value = shot.get("audio_music_sfx", {}).get(field)
            if isinstance(value, str) and value:
                add("Audio", value, prefix + "/audio_music_sfx/" + field)
        dialogue = shot.get("dialogue_narration", {}).get("dialogue", "")
        if dialogue:
            add("Spoken dialogue", dialogue, prefix + "/dialogue_narration/dialogue")
        negative_lines = [REFERENCE_LAYOUT_NEGATIVE,
            "picture-in-picture, portrait cards, duplicate faces, floating portraits, inset faces, inset panels, pop-up windows, UI overlays, text overlays, reference cards, split-screen"]
    if native_requested:
        # Original administrative text stays available for audit, never as a
        # competing request for generated narration or caption lettering.
        retained_constraints["original_script_routing"] = {
            "original_positive_text": "\n".join(lines),
            "original_source_bindings": json.loads(_stable(bindings)),
            "post_narration": shot["dialogue_narration"].get("narration", ""),
            "post_caption": shot["caption_on_screen_text"],
            "visible_character_source_hashes": hashes,
            "approval_basis": provenance,
        }
        for binding in bindings:
            if binding.get("destination") == "positive_prompt":
                binding["destination"] = "retained_original_script_administration"
        # Native LTX audio can speak administrative text. Keep the complete
        # reviewed prompt in provenance; project IDs, asset policy and internal
        # instructions must never be candidate dialogue in the model text.
        retained_constraints["original_script_routing"]["original_native_render_prompt"] = native_prompt
        retained_constraints["original_script_routing"]["original_negative_text"] = "\n".join(negative_lines)
        lines[:] = ["One continuous cinematic shot in premium stylized 3D realism, matching the supplied starting frame."]
        for key in ("original_visual", "original_camera", "lighting"):
            value = _string(supplement.get(key), "original scene " + key)
            if value not in native_prompt:
                raise ValueError("Original scene direction differs from its locked native prompt")
            lines.append(value)
            bindings.append({"source_path": "/director_packet/visible_cast_supplement/" + key,
                             "source_value_sha256": _hash(value), "destination": "positive_prompt"})
        lines.append("The camera movement is gradual and continuous throughout this same shot.")
        if dialogue:
            lines.append("Natural face-to-face character speech, with synchronized mouth movement: " + json.dumps(dialogue, ensure_ascii=False))
        else:
            lines.append("The character's lips remain at rest. Quiet location ambience only.")
        for binding in bindings:
            if binding.get("destination") == "negative_prompt":
                binding["destination"] = "retained_original_script_administration"
        negative_lines[:] = ["hard cut, jump cut, montage, scene transition, abrupt camera change, contact sheet, collage, text overlays, captions, duplicate characters, malformed hands"]
        if not dialogue:
            negative_lines.append("speech, narration, dialogue, singing, vocals, music, talking mouth")
        for cid in ids:
            if cid != character_id:
                retained_constraints["original_script_routing"].setdefault("secondary_negative_rules", {})[cid] = _strings(visible[cid].get("negative_rules", []), "secondary negative rules")
    if retained_director:
        retained_constraints["director_packet"] = retained_director
    positive_prompt = "\n".join(lines)
    negative_prompt = "\n".join(negative_lines)
    if len(positive_prompt) > MAX_POSITIVE_CHARACTERS or len(negative_prompt) > MAX_NEGATIVE_CHARACTERS:
        raise ValueError("Approved scene exceeds the bounded prompt compiler; no instructions were truncated")
    manifest = {
        "schema": "joat.prompt_compilation.v1",
        "compiler_file_version": FILE_VERSION if native_requested else FRAME_COMPILATION_VERSION if frame_scoped else NATIVE_COMPILATION_VERSION if native_media_fields or environment_origin_reused else LEGACY_COMPILATION_VERSION,
        "full_prompt_contract_sha256": _hash(contract),
        "source_packet_sha256": {key: _hash(packet) for key, packet in packets.items()},
        "project_context": dict(context),
        "project_context_sha256": _hash(context),
        "generation_specification_sha256": _hash(specification),
        "selected_director_shot_index": shot_index,
        "selected_director_shot_sha256": _hash(shot),
        "source_bindings": bindings,
        "retained_constraints": retained_constraints,
        "technical_artifact_guards": {
            "basis": "selected_owner_approved_single_shot" if single_scene_guard else "no_automatic_layout_guard",
            "positive": [lines[2]] if compact_frame_prompt else [REFERENCE_LAYOUT_GUARD] if single_scene_guard else [],
            "negative": [REFERENCE_LAYOUT_NEGATIVE] if single_scene_guard else [],
            "asset_selection_changed": False,
        },
        "positive_prompt_sha256": _text_hash(positive_prompt),
        "negative_prompt_sha256": _text_hash(negative_prompt),
        "positive_characters": len(positive_prompt),
        "negative_characters": len(negative_prompt),
        "instructions_truncated": False,
        "assets_changed": False,
        "creative_approval_granted": False,
    }
    if native_requested:
        manifest["original_script_native_routing"] = {"source_packets_changed": False, "native_prompt_sha256": _text_hash(native_prompt), "render_projection_version": "1.0.0", "administrative_text_retained_outside_generation": True, "visible_character_ids": ids, "post_narration_kept_outside_generation": True, "caption_text_kept_outside_generation": True, "still_or_video_qc_approval_granted": False}
    if frame_scoped:
        manifest["shot_prompt_routing"] = {"approved_composed_frame": True, "global_brief_retained_outside_render_text": True, "post_narration_retained_outside_render_text": "post_narration" in retained_director, "unrequested_overlay_guard": artifact_guard, "source_packets_changed": False, "compact_composed_frame_prompt": compact_frame_prompt, "administrative_policies_retained_outside_render_text": compact_frame_prompt}
    if environment_origin_reused:
        manifest["reused_environment_origin"] = {"source_scene_context": environment_scene,
            "target_context": dict(context), "environment_id": environment_id,
            "basis": "exact_owner_reviewed_environment_requirement", "source_changed": False}
    # Detach the manifest from the original packet objects to avoid aliases.
    return {"positive_prompt": positive_prompt, "negative_prompt": negative_prompt,
            "manifest": json.loads(_stable(manifest))}


def verify_compilation(compilation, prompt_contract, project_context, generation_specification, approved_composed_frame=False):
    """Verify all output text and retained constraints against the current sources."""
    expected = compile_approved_scene(prompt_contract, project_context, generation_specification, approved_composed_frame=approved_composed_frame)
    if _stable(compilation) != _stable(expected):
        raise ValueError("Compiled prompt or manifest does not match its immutable sources")
    return True
