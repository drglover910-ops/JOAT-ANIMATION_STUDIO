"""J.O.A.T. Director Creative Intelligence - Director Worker v1.0.5

Consumes locked character packets (joat.character_packet.v1) and produces
deterministic director packets (joat.director_packet.v1).

This worker:
- Loads the approved CHAR-001 through CHAR-007 registry
- Builds locked character packets
- Validates identity and approval controls
- Produces deterministic director packets
- Preserves character identity constraints
- Never mutates characters.json
- Includes acceptance tests
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import gradio as gr
from joat_approved_reference import read_manifest, load_approved_frame, bind_character


# ============================================================================
# CONFIGURATION
# ============================================================================

ROOT = Path(__file__).resolve().parent
CHARACTERS_JSON_PATH = ROOT / "characters.json"

CHARACTER_PACKET_SCHEMA = "joat.character_packet.v1"
DIRECTOR_SCHEMA_VERSION = "joat.director_packet.v1"
DIRECTOR_VERSION = "1.0.5"

REQUIRED_CHARACTER_PACKET_FIELDS = [
    "schema",
    "character_id",
    "character_name",
    "character_version",
    "identity_locked",
    "identity_lock_asset",
    "appearance_rules",
    "continuity_rules",
    "negative_rules",
    "source_asset_hashes",
    "approval",
]

REQUIRED_APPROVAL_FIELDS = [
    "live_change_allowed",
    "requires_human_approval_for_registry_mutation",
]


# ============================================================================
# GENERAL HELPERS
# ============================================================================

def load_registry() -> dict[str, Any]:
    """Load the Character Asset Master registry."""

    if not CHARACTERS_JSON_PATH.exists():
        raise FileNotFoundError(
            f"characters.json was not found at: {CHARACTERS_JSON_PATH}"
        )

    with CHARACTERS_JSON_PATH.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)

    if not isinstance(registry, dict):
        raise ValueError("characters.json root must be a JSON object.")

    characters = registry.get("characters")

    if not isinstance(characters, list):
        raise ValueError(
            "characters.json must contain a top-level 'characters' list."
        )

    return registry


def get_character(
    character_id: str,
    registry: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return a character registry entry by ID."""

    if registry is None:
        registry = load_registry()

    for character in registry.get("characters", []):
        if character.get("id") == character_id:
            return character

    raise KeyError(f"Unknown character: {character_id}")


def get_test_character_id() -> str:
    """Use CHAR-001 when available, otherwise the first registry character."""

    registry = load_registry()

    for character in registry.get("characters", []):
        if character.get("id") == "CHAR-001":
            return "CHAR-001"

    characters = registry.get("characters", [])

    if not characters:
        raise ValueError("No characters are registered.")

    character_id = characters[0].get("id")

    if not character_id:
        raise ValueError("First registered character has no ID.")

    return character_id


def parse_json_value(
    value: str,
    default: Any,
    expected_type: type,
    field_name: str,
) -> Any:
    """Parse a JSON UI field safely."""

    if value is None or not str(value).strip():
        return default

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{field_name} contains invalid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, expected_type):
        raise ValueError(
            f"{field_name} must decode to "
            f"{expected_type.__name__}, not {type(parsed).__name__}."
        )

    return parsed


def value_for_shot(values: list[Any], index: int, default: Any) -> Any:
    """Safely select a shot-level value."""

    if not values:
        return default

    if index < len(values):
        return values[index]

    return values[-1]


# ============================================================================
# CHARACTER PACKET GENERATION
# ============================================================================

def build_character_packet(
    character_id: str,
    registry: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a locked joat.character_packet.v1 packet."""

    if registry is None:
        registry = load_registry()

    character = get_character(character_id, registry)

    assets = character.get("assets", [])

    if not isinstance(assets, list):
        raise ValueError(
            f"{character_id}: assets must be a list."
        )

    approved_assets = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and asset.get("status", "approved") == "approved"
    ]

    identity_candidates = [
        asset
        for asset in approved_assets
        if "identity_anchor" in asset.get("roles", [])
    ]

    if not identity_candidates:
        raise ValueError(
            f"{character_id}: no approved identity_anchor asset exists."
        )

    identity_anchor = identity_candidates[0]

    supporting_assets = [
        asset
        for asset in approved_assets
        if asset is not identity_anchor
    ]

    source_asset_hashes = {}

    for asset in approved_assets:
        asset_id = asset.get("asset_id")
        sha256 = asset.get("sha256")

        if asset_id and sha256:
            source_asset_hashes[asset_id] = sha256

    packet = {
        "schema": CHARACTER_PACKET_SCHEMA,
        "character_id": character["id"],
        "character_name": character["name"],
        "character_version": character.get("version", "1.0.0"),

        "identity_locked": True,
        "identity_lock_asset": identity_anchor.get("path"),

        "supporting_reference_assets": [
            asset.get("path")
            for asset in supporting_assets
            if asset.get("path")
        ],

        "appearance_rules": character.get(
            "appearance_rules",
            {},
        ),

        "continuity_rules": character.get(
            "continuity_rules",
            [],
        ),

        "negative_rules": character.get(
            "negative_rules",
            [],
        ),

        "source_asset_hashes": source_asset_hashes,

        "approval": {
            "live_change_allowed": False,
            "requires_human_approval_for_registry_mutation": True,
        },
    }

    return packet


# ============================================================================
# CHARACTER PACKET VALIDATION
# ============================================================================

def validate_character_packet(
    packet: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate joat.character_packet.v1."""

    errors: list[str] = []

    if not isinstance(packet, dict):
        return False, ["Character packet must be a JSON object."]

    for field in REQUIRED_CHARACTER_PACKET_FIELDS:
        if field not in packet:
            errors.append(
                f"Missing required character packet field: {field}"
            )

    if errors:
        return False, errors

    if packet.get("schema") != CHARACTER_PACKET_SCHEMA:
        errors.append(
            f"Invalid character packet schema: "
            f"{packet.get('schema')}"
        )

    if packet.get("identity_locked") is not True:
        errors.append(
            "Character packet identity_locked must be True."
        )

    if not packet.get("identity_lock_asset"):
        errors.append(
            "Character packet has no identity_lock_asset."
        )

    hashes = packet.get("source_asset_hashes")

    if not isinstance(hashes, dict) or not hashes:
        errors.append(
            "Character packet must contain source_asset_hashes."
        )

    approval = packet.get("approval")

    if not isinstance(approval, dict):
        errors.append(
            "Character packet approval must be an object."
        )
        approval = {}

    for field in REQUIRED_APPROVAL_FIELDS:
        if field not in approval:
            errors.append(
                f"Missing approval field: {field}"
            )

    if approval.get("live_change_allowed") is not False:
        errors.append(
            "live_change_allowed must be False."
        )

    if (
        approval.get(
            "requires_human_approval_for_registry_mutation"
        )
        is not True
    ):
        errors.append(
            "Registry mutation must require human approval."
        )

    return len(errors) == 0, errors


# ============================================================================
# DIRECTOR PACKET GENERATION
# ============================================================================

def generate_director_packet(
    creative_brief: str,
    character_packet_json: str,
    production_intent: str = "animation",
    scene_plan_str: str = "",
    environment_requirements: str = "none",
    camera_framing_str: str = "",
    performance_action_str: str = "",
    dialogue_narration_str: str = "",
    audio_music_sfx_str: str = "",
    caption_on_screen_text_str: str = "",
    duration: str = "00:00",
    continuity_constraints: str = "none",
    generation_instructions: str = "standard",
    qc_gates_str: str = "",
    downstream_handoff_str: str = "",
) -> dict[str, Any]:
    """Generate joat.director_packet.v1."""

    if not creative_brief or not creative_brief.strip():
        raise ValueError("Creative brief is required.")

    try:
        character_packet = json.loads(
            character_packet_json
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid character packet JSON: {exc}"
        ) from exc

    valid, validation_errors = validate_character_packet(
        character_packet
    )

    if not valid:
        formatted = "\n".join(
            f"- {error}"
            for error in validation_errors
        )

        raise ValueError(
            "Character packet validation failed:\n"
            f"{formatted}"
        )

    default_scene_plan = [
        {
            "shot_id": "SHOT-001",
            "scene_id": "SCENE-001",
        }
    ]

    default_camera = [
        {
            "shot_id": "SHOT-001",
            "framing": "medium",
            "angle": "eye-level",
            "movement": "static",
        }
    ]

    default_performance = [
        {
            "shot_id": "SHOT-001",
            "action": "standard",
        }
    ]

    default_dialogue = [
        {
            "shot_id": "SHOT-001",
            "dialogue": "",
            "narration": "",
        }
    ]

    default_audio = [
        {
            "shot_id": "SHOT-001",
            "audio": "",
            "music": "",
            "sfx": "",
        }
    ]

    default_caption = [
        {
            "shot_id": "SHOT-001",
            "caption": "",
            "on_screen_text": "",
        }
    ]

    default_qc = [
        "identity_anchor_match",
        "source_hash_integrity",
        "continuity_check",
        "negative_rule_check",
    ]

    default_handoff = {
        "target": "joat-animation-studio",
        "format": DIRECTOR_SCHEMA_VERSION,
    }

    scene_plan = parse_json_value(
        scene_plan_str,
        default_scene_plan,
        list,
        "Scene Plan",
    )

    if not scene_plan:
        scene_plan = default_scene_plan

    camera_framing = parse_json_value(
        camera_framing_str,
        default_camera,
        list,
        "Camera Framing",
    )

    performance_action = parse_json_value(
        performance_action_str,
        default_performance,
        list,
        "Performance/Action",
    )

    dialogue_narration = parse_json_value(
        dialogue_narration_str,
        default_dialogue,
        list,
        "Dialogue/Narration",
    )

    audio_music_sfx = parse_json_value(
        audio_music_sfx_str,
        default_audio,
        list,
        "Audio/Music/SFX",
    )

    caption_on_screen_text = parse_json_value(
        caption_on_screen_text_str,
        default_caption,
        list,
        "Caption/On-Screen Text",
    )

    qc_gates = parse_json_value(
        qc_gates_str,
        default_qc,
        list,
        "QC Gates",
    )

    downstream_handoff = parse_json_value(
        downstream_handoff_str,
        default_handoff,
        dict,
        "Downstream Handoff",
    )

    brief_hash = hashlib.sha256(
        creative_brief.strip().encode("utf-8")
    ).hexdigest()[:16]

    project_id = (
        f"JOAT-{brief_hash}-dir-v{DIRECTOR_VERSION}"
    )

    character_reference = {
        "character_id": character_packet["character_id"],
        "character_name": character_packet["character_name"],
        "character_version": character_packet[
            "character_version"
        ],
        "identity_locked": True,
        "identity_lock_asset": character_packet[
            "identity_lock_asset"
        ],
        "supporting_reference_assets": character_packet.get(
            "supporting_reference_assets",
            [],
        ),
        "appearance_rules": character_packet[
            "appearance_rules"
        ],
        "continuity_rules": character_packet[
            "continuity_rules"
        ],
        "negative_rules": character_packet[
            "negative_rules"
        ],
        "source_asset_hashes": character_packet[
            "source_asset_hashes"
        ],
        "constraints_applied": True,
    }

    per_shot: list[dict[str, Any]] = []

    for index, scene in enumerate(scene_plan):
        if not isinstance(scene, dict):
            raise ValueError(
                "Every Scene Plan entry must be a JSON object."
            )

        shot_id = scene.get(
            "shot_id",
            f"SHOT-{index + 1:03d}",
        )

        scene_id = scene.get(
            "scene_id",
            f"SCENE-{index + 1:03d}",
        )

        shot = {
            "shot_id": shot_id,
            "scene_id": scene_id,

            "character_ids": [
                character_packet["character_id"]
            ],

            "character_packet_references": [
                character_reference
            ],

            "character_constraints": {
                "identity_locked": True,

                "identity_lock_asset":
                    character_packet[
                        "identity_lock_asset"
                    ],

                "appearance_rules":
                    character_packet[
                        "appearance_rules"
                    ],

                "continuity_rules":
                    character_packet[
                        "continuity_rules"
                    ],

                "negative_rules":
                    character_packet[
                        "negative_rules"
                    ],

                "source_asset_hashes":
                    character_packet[
                        "source_asset_hashes"
                    ],
            },

            "environment_requirements":
                environment_requirements,

            "camera_framing": value_for_shot(
                camera_framing,
                index,
                default_camera[0],
            ),

            "performance_action": value_for_shot(
                performance_action,
                index,
                default_performance[0],
            ),

            "dialogue_narration": value_for_shot(
                dialogue_narration,
                index,
                default_dialogue[0],
            ),

            "audio_music_sfx": value_for_shot(
                audio_music_sfx,
                index,
                default_audio[0],
            ),

            "caption_on_screen_text": value_for_shot(
                caption_on_screen_text,
                index,
                default_caption[0],
            ),

            "duration": duration,
        }

        per_shot.append(shot)

    packet = {
        "schema": DIRECTOR_SCHEMA_VERSION,
        "version": DIRECTOR_VERSION,
        "project_id": project_id,

        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "creative_brief": creative_brief.strip(),

        "production_intent": production_intent,

        "scene_plan": scene_plan,

        "character_refs": [
            character_reference
        ],

        "environment_requirements":
            environment_requirements,

        "camera_framing":
            camera_framing,

        "performance_action":
            performance_action,

        "dialogue_narration":
            dialogue_narration,

        "audio_music_sfx":
            audio_music_sfx,

        "caption_on_screen_text":
            caption_on_screen_text,

        "duration":
            duration,

        "per_shot":
            per_shot,

        "continuity_constraints":
            continuity_constraints,

        "generation_instructions":
            generation_instructions,

        "qc_gates":
            qc_gates,

        "downstream_handoff": {
            **downstream_handoff,

            "source_schema":
                DIRECTOR_SCHEMA_VERSION,

            "source_version":
                DIRECTOR_VERSION,

            "registry_mutation":
                "not_applicable_director_only",
        },
    }

    return packet


# ============================================================================
# ACCEPTANCE TESTS
# ============================================================================

def run_acceptance_tests() -> dict[str, Any]:
    """Run Director Worker acceptance tests."""

    results: dict[str, Any] = {
        "acceptance_test_version": "1.2.0",
        "director_version": DIRECTOR_VERSION,
        "tests": [],
        "all_passed": True,
    }

    def run_test(name: str, function) -> None:
        try:
            detail = function()

            passed = (
                detail
                if isinstance(detail, bool)
                else True
            )

            results["tests"].append(
                {
                    "test": name,
                    "pass": bool(passed),
                    "detail": detail,
                }
            )

            if not passed:
                results["all_passed"] = False

        except Exception as exc:
            results["tests"].append(
                {
                    "test": name,
                    "pass": False,
                    "detail": str(exc),
                }
            )

            results["all_passed"] = False

    test_character_id = get_test_character_id()

    # ------------------------------------------------------------------
    # 1. Registry
    # ------------------------------------------------------------------

    def test_registry():
        registry = load_registry()
        return len(
            registry.get("characters", [])
        ) > 0

    run_test(
        "1. Character registry loads",
        test_registry,
    )

    # ------------------------------------------------------------------
    # 2. Character packet
    # ------------------------------------------------------------------

    def test_character_packet():
        packet = build_character_packet(
            test_character_id
        )

        valid, errors = validate_character_packet(
            packet
        )

        if not valid:
            raise ValueError("; ".join(errors))

        return True

    run_test(
        "2. Locked character packet validates",
        test_character_packet,
    )

    # ------------------------------------------------------------------
    # 3. Director schema
    # ------------------------------------------------------------------

    def test_schema_generation():
        packet = build_character_packet(
            test_character_id
        )

        director = generate_director_packet(
            "Test brief for schema validation",
            json.dumps(packet),
        )

        required_fields = [
            "schema",
            "version",
            "project_id",
            "created_at",
            "creative_brief",
            "production_intent",
            "scene_plan",
            "character_refs",
            "environment_requirements",
            "camera_framing",
            "performance_action",
            "dialogue_narration",
            "audio_music_sfx",
            "caption_on_screen_text",
            "duration",
            "per_shot",
            "continuity_constraints",
            "generation_instructions",
            "qc_gates",
            "downstream_handoff",
        ]

        return (
            director["schema"]
            == DIRECTOR_SCHEMA_VERSION
            and all(
                field in director
                for field in required_fields
            )
            and len(director["per_shot"]) >= 1
        )

    run_test(
        "3. Director schema generation",
        test_schema_generation,
    )

    # ------------------------------------------------------------------
    # 4. Reject unlocked packet
    # ------------------------------------------------------------------

    def test_reject_unlocked():
        packet = build_character_packet(
            test_character_id
        )

        packet["identity_locked"] = False

        try:
            generate_director_packet(
                "Unlocked packet test",
                json.dumps(packet),
            )

            return False

        except ValueError:
            return True

    run_test(
        "4. Reject unlocked character packet",
        test_reject_unlocked,
    )

    # ------------------------------------------------------------------
    # 5. Reject malformed packet
    # ------------------------------------------------------------------

    def test_reject_malformed():
        try:
            generate_director_packet(
                "Malformed packet test",
                json.dumps(
                    {
                        "not":
                            "a character packet"
                    }
                ),
            )

            return False

        except ValueError:
            return True

    run_test(
        "5. Reject malformed character packet",
        test_reject_malformed,
    )

    # ------------------------------------------------------------------
    # 6. Constraint preservation
    # ------------------------------------------------------------------

    def test_constraint_preservation():
        packet = build_character_packet(
            test_character_id
        )

        director = generate_director_packet(
            "Constraint preservation test",
            json.dumps(packet),
        )

        constraints = director[
            "per_shot"
        ][0]["character_constraints"]

        return (
            constraints["identity_locked"] is True
            and constraints[
                "identity_lock_asset"
            ]
            == packet["identity_lock_asset"]
            and constraints[
                "appearance_rules"
            ]
            == packet["appearance_rules"]
            and constraints[
                "continuity_rules"
            ]
            == packet["continuity_rules"]
            and constraints[
                "negative_rules"
            ]
            == packet["negative_rules"]
            and constraints[
                "source_asset_hashes"
            ]
            == packet["source_asset_hashes"]
        )

    run_test(
        "6. Character constraints preserved",
        test_constraint_preservation,
    )

    # ------------------------------------------------------------------
    # 7. Required shot fields
    # ------------------------------------------------------------------

    def test_required_shot_fields():
        packet = build_character_packet(
            test_character_id
        )

        director = generate_director_packet(
            "Required shot field test",
            json.dumps(packet),
        )

        shot = director["per_shot"][0]

        required = [
            "shot_id",
            "scene_id",
            "character_ids",
            "character_packet_references",
            "character_constraints",
            "environment_requirements",
            "camera_framing",
            "performance_action",
            "dialogue_narration",
            "audio_music_sfx",
            "caption_on_screen_text",
            "duration",
        ]

        return all(
            field in shot
            for field in required
        )

    run_test(
        "7. Required per-shot fields present",
        test_required_shot_fields,
    )

    # ------------------------------------------------------------------
    # 8. Deterministic project ID
    # ------------------------------------------------------------------

    def test_deterministic_id():
        packet = build_character_packet(
            test_character_id
        )

        packet_json = json.dumps(packet)

        first = generate_director_packet(
            "Deterministic ID test",
            packet_json,
        )

        second = generate_director_packet(
            "Deterministic ID test",
            packet_json,
        )

        return (
            first["project_id"]
            == second["project_id"]
        )

    run_test(
        "8. Deterministic project ID",
        test_deterministic_id,
    )

    # ------------------------------------------------------------------
    # 9. Empty arrays cannot crash per-shot generation
    # ------------------------------------------------------------------

    def test_empty_arrays():
        packet = build_character_packet(
            test_character_id
        )

        director = generate_director_packet(
            creative_brief="Empty array test",
            character_packet_json=json.dumps(
                packet
            ),
            scene_plan_str="[]",
            camera_framing_str="[]",
            performance_action_str="[]",
            dialogue_narration_str="[]",
            audio_music_sfx_str="[]",
            caption_on_screen_text_str="[]",
        )

        return len(
            director["per_shot"]
        ) == 1

    run_test(
        "9. Empty shot arrays handled safely",
        test_empty_arrays,
    )

    # ------------------------------------------------------------------
    # 10. Registry mutation protection
    # ------------------------------------------------------------------

    def test_no_registry_mutation():
        before = CHARACTERS_JSON_PATH.read_bytes()

        packet = build_character_packet(
            test_character_id
        )

        generate_director_packet(
            "Registry mutation test",
            json.dumps(packet),
        )

        after = CHARACTERS_JSON_PATH.read_bytes()

        return before == after

    run_test(
        "10. Character registry not mutated",
        test_no_registry_mutation,
    )

    return results


# ============================================================================
# UI HELPERS
# ============================================================================

def get_character_choices() -> list[tuple[str, str]]:
    """Return Gradio dropdown choices."""

    try:
        registry = load_registry()
    except Exception:
        return [(f"Canonical CHAR-{i:03d}", f"CHAR-{i:03d}") for i in range(1, 8)]

    choices: list[tuple[str, str]] = [(f"Canonical CHAR-{i:03d}", f"CHAR-{i:03d}") for i in range(1, 8)]

    for character in registry.get(
        "characters",
        [],
    ):
        character_id = character.get("id")
        character_name = character.get(
            "name",
            "Unnamed",
        )

        if character_id:
            label = (
                f"{character_name} "
                f"({character_id})"
            )

            choices.append(
                (
                    label,
                    character_id,
                )
            )

    return choices


def preview_character_packet(
    character_id: str,
) -> str:
    """Preview selected character packet."""

    if not character_id:
        return "Select a character."

    try:
        packet = fetch_master_character(character_id) if character_id.startswith("CHAR-") else build_character_packet(character_id)

        return json.dumps(
            packet,
            indent=2,
            ensure_ascii=False,
        )

    except Exception as exc:
        return f"Error: {exc}"


def generate_director_ui(
    creative_brief: str,
    character_id: str,
    production_intent: str,
    scene_plan: str,
    environment_requirements: str,
    camera_framing: str,
    performance_action: str,
    dialogue_narration: str,
    audio_music_sfx: str,
    caption_on_screen_text: str,
    duration: str,
    continuity_constraints: str,
    generation_instructions: str,
    qc_gates: str,
    downstream_handoff: str,
    character_packet_json: str = "",
) -> tuple[str, str, str]:
    """UI wrapper."""

    if not creative_brief or not creative_brief.strip():
        return (
            "ERROR: Creative brief is required.",
            "",
            "",
        )

    if not character_id:
        return (
            "ERROR: Select a character.",
            "",
            "",
        )

    try:
        if character_packet_json.strip():
            character_packet = json.loads(character_packet_json)
            valid, errors = validate_character_packet(character_packet)
            if not valid or character_packet.get("character_id") != character_id:
                raise ValueError("Exact Character Master input rejected: " + "; ".join(errors))
        elif character_id.startswith("CHAR-"):
            character_packet = fetch_master_character(character_id)
        else:
            character_packet = build_character_packet(character_id)

        director_packet = generate_director_packet(
            creative_brief=creative_brief,
            character_packet_json=json.dumps(
                character_packet,
                ensure_ascii=False,
            ),
            production_intent=production_intent,
            scene_plan_str=scene_plan,
            environment_requirements=environment_requirements,
            camera_framing_str=camera_framing,
            performance_action_str=performance_action,
            dialogue_narration_str=dialogue_narration,
            audio_music_sfx_str=audio_music_sfx,
            caption_on_screen_text_str=caption_on_screen_text,
            duration=duration,
            continuity_constraints=continuity_constraints,
            generation_instructions=generation_instructions,
            qc_gates_str=qc_gates,
            downstream_handoff_str=downstream_handoff,
        )

        output = json.dumps(
            director_packet,
            indent=2,
            ensure_ascii=False,
        )

        summary = (
            "Director packet generated successfully.\n"
            f"Project ID: "
            f"{director_packet['project_id']}\n"
            f"Schema: "
            f"{director_packet['schema']}\n"
            f"Version: "
            f"{director_packet['version']}"
        )

        return (
            "OK: Character packet VALID",
            output,
            summary,
        )

    except Exception as exc:
        return (
            f"ERROR: {exc}",
            "",
            "",
        )


def run_tests_ui() -> str:
    """Run tests and return formatted JSON."""

    try:
        results = run_acceptance_tests()

        return json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        )

    except Exception as exc:
        return json.dumps(
            {
                "all_passed": False,
                "fatal_error": str(exc),
            },
            indent=2,
        )


# ============================================================================
# GRADIO APPLICATION
# ============================================================================


# Production source connection. Existing registry and generation functions remain intact.
def production_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def fetch_master_character(character_id):
    import urllib.request
    if character_id not in [f"CHAR-{i:03d}" for i in range(1, 8)]:
        raise ValueError("Select an approved Character Master ID.")
    base = "https://dezz-9-10-j-o-a-t-character-asset-master.hf.space/gradio_api/call/packet"
    request = urllib.request.Request(base, data=json.dumps({"data": [character_id, "scene"]}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        event_id = json.load(response)["event_id"]
    if not isinstance(event_id, str) or not event_id.isalnum():
        raise ValueError("Character Master returned an invalid event ID.")
    with urllib.request.urlopen(base + "/" + event_id, timeout=60) as response:
        event = ""
        for raw in response:
            line = raw.decode().strip()
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:") and event == "error":
                raise ValueError("Character Master could not return the locked packet.")
            elif line.startswith("data:") and event == "complete":
                packet = json.loads(line[5:].strip())[0]
                if isinstance(packet, str):
                    packet = json.loads(packet)
                valid, errors = validate_character_packet(packet)
                if not valid or packet.get("character_id") != character_id:
                    raise ValueError("Character Master packet validation failed: " + "; ".join(errors))
                return packet
    raise ValueError("Character Master did not complete the packet request.")


def prepare_production_director(character_id, brief, spec_json, reference_file=None):
    import inspect
    spec = json.loads(spec_json)
    if not isinstance(spec, dict):
        raise ValueError("Shot specification must be a JSON object.")
    allowed = set(inspect.signature(generate_director_packet).parameters) - {"creative_brief", "character_packet_json"}
    if set(spec) - allowed or any(not isinstance(value, str) for value in spec.values()):
        raise ValueError("Use the displayed Director parameter names and string values.")
    character = fetch_master_character(character_id)
    draft = generate_director_packet(brief, json.dumps(character, ensure_ascii=False), **spec)
    if reference_file:
        reference = read_manifest(reference_file)
        descriptor = bind_character(reference, character)
        load_approved_frame(reference)
        scope = descriptor["scope"]
        matches = [shot for shot in draft["per_shot"] if shot.get("scene_id") == scope["scene_id"] and shot.get("shot_id") == scope["shot_id"]]
        if len(matches) != 1:
            raise ValueError("Approved opening frame does not match a shot in this draft.")
        if scope["environment_id"] not in draft["environment_requirements"]:
            raise ValueError("Name the approved frame's environment ID in environment requirements.")
        # This is a NEW owner-reviewed draft. Never mutate a previously locked packet.
        draft["project_id"] = scope["project_id"]
        draft["approved_job_references"] = [reference]
    state = {"character": character, "draft": draft,
             "draft_hash": production_hash(draft), "character_hash": production_hash(character)}
    return state, json.dumps(draft, ensure_ascii=False, indent=2), False, None, None


def approve_production_director(state, approved, profile: Optional[gr.OAuthProfile]):
    import copy
    import tempfile
    if profile is None or profile.username != "Dezz-9-10":
        raise gr.Error("Sign in as the studio owner Dezz-9-10.")
    if approved is not True:
        raise gr.Error("Review the draft and explicitly approve its creative decisions.")
    if not state or production_hash(state["draft"]) != state["draft_hash"] or production_hash(state["character"]) != state["character_hash"]:
        raise gr.Error("Build a fresh draft before approving.")
    packet = copy.deepcopy(state["draft"])
    for reference in packet.get("approved_job_references", []):
        bind_character(reference, state["character"])
        load_approved_frame(reference)
    packet["approval"] = {"creative_intent_locked": True, "approved_by": profile.username,
                          "approved_at": datetime.now(timezone.utc).isoformat(),
                          "reviewed_draft_sha256": state["draft_hash"],
                          "character_packet_sha256": state["character_hash"],
                          "source_space": "Dezz-9-10/J.O.A.T.-Character-Asset-Master"}
    packet["packet_fingerprint"] = production_hash(packet)
    directory = Path(tempfile.mkdtemp(prefix="joat-director-"))
    char_path = directory / "character_packet.json"
    director_path = directory / "approved_director_packet.json"
    char_path.write_text(json.dumps(state["character"], ensure_ascii=False, indent=2), encoding="utf-8")
    director_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.dumps(packet, ensure_ascii=False, indent=2), str(char_path), str(director_path)


def invalidate_production_director():
    return None, "", False, None, None


def build_app() -> gr.Blocks:
    """Build Director UI."""

    character_choices = get_character_choices()

    default_character = (
        character_choices[0][1]
        if character_choices
        else None
    )

    with gr.Blocks(
        title="J.O.A.T. Director Creative Intelligence"
    ) as app:

        gr.Markdown(
            "# J.O.A.T. Director Creative Intelligence"
        )

        gr.Markdown(
            f"**Director Worker v{DIRECTOR_VERSION}**  \n"
            "Consumes locked character packets and produces "
            "deterministic director packets."
        )

        with gr.Tabs():

            with gr.Tab("Production Character Master Connection"):
                gr.Markdown("Build a draft using the actual locked Character Master packet. Review all creative decisions, then sign in and approve. This does not render video.")
                production_character = gr.Dropdown([f"CHAR-{i:03d}" for i in range(1, 8)], value="CHAR-001", label="Character Master ID")
                production_brief = gr.Textbox(label="Creative brief for owner review", value="CHAR-001 remains in approved ENV-001 executive office for one six-second shot with a calm neutral expression and natural blink. Static eye-level medium camera. Preserve approved identity rules. No dialogue, music, captions or additional effects.", lines=4)
                production_spec = gr.Code(label="Director shot specification (JSON)", language="json", value='{\n  "production_intent": "animation",\n  "environment_requirements": "ENV-001 Executive Office; preserve approved identity anchor",\n  "camera_framing_str": "[{\\"shot_id\\": \\"SHOT-001\\", \\"framing\\": \\"medium\\", \\"angle\\": \\"eye-level\\", \\"movement\\": \\"static\\"}]",\n  "performance_action_str": "[{\\"shot_id\\": \\"SHOT-001\\", \\"action\\": \\"Remain still in a calm neutral pose; blink naturally once; do not speak.\\"}]",\n  "duration": "00:06",\n  "continuity_constraints": "Preserve approved character identity and environment geometry.",\n  "generation_instructions": "Follow the approved creative decisions exactly; no additional effects."\n}')
                production_reference = gr.File(label="Saved approved_job_reference.json (optional opening frame)", type="filepath", file_types=[".json"])
                production_state = gr.State(None)
                production_build = gr.Button("Fetch Character Master and Build Draft")
                production_output = gr.Code(label="Director packet — draft until approved", language="json", interactive=False)
                gr.LoginButton()
                production_approved = gr.Checkbox(value=False, label="I reviewed and approve this draft's creative decisions")
                production_confirm = gr.Button("Approve and Lock Director Packet")
                production_character_file = gr.File(label="Exact Character Master packet", interactive=False)
                production_director_file = gr.File(label="Approved Director packet", interactive=False)
                production_build.click(prepare_production_director,
                    [production_character, production_brief, production_spec, production_reference],
                    [production_state, production_output, production_approved, production_character_file, production_director_file], api_name=False)
                production_confirm.click(approve_production_director,
                    [production_state, production_approved],
                    [production_output, production_character_file, production_director_file], api_name=False)
                for production_input in [production_character, production_brief, production_spec, production_reference]:
                    production_input.change(invalidate_production_director, [],
                        [production_state, production_output, production_approved, production_character_file, production_director_file], api_name=False)



            # ============================================================
            # DIRECTOR GENERATION TAB
            # ============================================================

            with gr.Tab("Director Generation"):

                gr.Markdown(
                    "## Input Parameters"
                )

                with gr.Row():

                    with gr.Column(scale=2):

                        creative_brief = gr.Textbox(
                            label="Creative Brief / Idea",
                            placeholder=(
                                "Describe the creative vision..."
                            ),
                            lines=4,
                        )

                        character_dropdown = gr.Dropdown(
                            choices=character_choices,
                            value=default_character,
                            label="Character Packet",
                            interactive=True,
                        )

                        production_intent = gr.Dropdown(
                            choices=[
                                "animation",
                                "live_action",
                                "mixed",
                                "stop_motion",
                                "other",
                            ],
                            value="animation",
                            label="Production Intent",
                        )

                    with gr.Column(scale=1):

                        preview_btn = gr.Button(
                            "Preview Character Packet"
                        )

                        packet_preview = gr.Textbox(
                            label="Character Packet Preview",
                            lines=12,
                            interactive=False,
                        )

                gr.Markdown(
                    "## Scene and Shot Parameters"
                )

                scene_plan = gr.Textbox(
                    label="Scene Plan (JSON)",
                    value=json.dumps(
                        [
                            {
                                "shot_id":
                                    "SHOT-001",
                                "scene_id":
                                    "SCENE-001",
                            }
                        ],
                        indent=2,
                    ),
                    lines=5,
                )

                environment_requirements = gr.Textbox(
                    label="Environment Requirements",
                    value="none",
                    lines=2,
                )

                with gr.Row():

                    with gr.Column():

                        camera_framing = gr.Textbox(
                            label="Camera Framing (JSON)",
                            value=json.dumps(
                                [
                                    {
                                        "shot_id":
                                            "SHOT-001",
                                        "framing":
                                            "medium",
                                        "angle":
                                            "eye-level",
                                        "movement":
                                            "static",
                                    }
                                ],
                                indent=2,
                            ),
                            lines=7,
                        )

                        performance_action = gr.Textbox(
                            label="Performance / Action (JSON)",
                            value=json.dumps(
                                [
                                    {
                                        "shot_id":
                                            "SHOT-001",
                                        "action":
                                            "standard",
                                    }
                                ],
                                indent=2,
                            ),
                            lines=5,
                        )

                    with gr.Column():

                        dialogue_narration = gr.Textbox(
                            label="Dialogue / Narration (JSON)",
                            value=json.dumps(
                                [
                                    {
                                        "shot_id":
                                            "SHOT-001",
                                        "dialogue":
                                            "",
                                        "narration":
                                            "",
                                    }
                                ],
                                indent=2,
                            ),
                            lines=6,
                        )

                        audio_music_sfx = gr.Textbox(
                            label="Audio / Music / SFX (JSON)",
                            value=json.dumps(
                                [
                                    {
                                        "shot_id":
                                            "SHOT-001",
                                        "audio":
                                            "",
                                        "music":
                                            "",
                                        "sfx":
                                            "",
                                    }
                                ],
                                indent=2,
                            ),
                            lines=6,
                        )

                caption_on_screen_text = gr.Textbox(
                    label="Caption / On-Screen Text (JSON)",
                    value=json.dumps(
                        [
                            {
                                "shot_id":
                                    "SHOT-001",
                                "caption":
                                    "",
                                "on_screen_text":
                                    "",
                            }
                        ],
                        indent=2,
                    ),
                    lines=6,
                )

                duration = gr.Textbox(
                    label="Duration",
                    value="00:00",
                )

                gr.Markdown(
                    "## Quality and Handoff"
                )

                continuity_constraints = gr.Textbox(
                    label="Continuity Constraints",
                    value="none",
                    lines=2,
                )

                generation_instructions = gr.Textbox(
                    label="Generation Instructions",
                    value="standard",
                    lines=2,
                )

                qc_gates = gr.Textbox(
                    label="QC Gates (JSON)",
                    value=json.dumps(
                        [
                            "identity_anchor_match",
                            "source_hash_integrity",
                            "continuity_check",
                            "negative_rule_check",
                        ],
                        indent=2,
                    ),
                    lines=6,
                )

                downstream_handoff = gr.Textbox(
                    label="Downstream Handoff (JSON)",
                    value=json.dumps(
                        {
                            "target":
                                "joat-animation-studio",
                            "format":
                                DIRECTOR_SCHEMA_VERSION,
                        },
                        indent=2,
                    ),
                    lines=5,
                )

                generate_btn = gr.Button(
                    "Generate Director Packet",
                    variant="primary",
                )

                validation_output = gr.Textbox(
                    label="Validation Status",
                    lines=2,
                    interactive=False,
                )

                director_output = gr.Textbox(
                    label=(
                        "Generated Director Packet "
                        "(joat.director_packet.v1)"
                    ),
                    lines=24,
                    interactive=False,
                )

                summary_output = gr.Textbox(
                    label="Summary",
                    lines=4,
                    interactive=False,
                )

                preview_btn.click(
                    fn=preview_character_packet,
                    inputs=character_dropdown,
                    outputs=packet_preview,
                )

                exact_character_input = gr.Textbox(value="", visible=False, label="Exact Character Master packet JSON (optional)")
                generate_btn.click(
                    fn=generate_director_ui,
                    inputs=[
                        creative_brief,
                        character_dropdown,
                        production_intent,
                        scene_plan,
                        environment_requirements,
                        camera_framing,
                        performance_action,
                        dialogue_narration,
                        audio_music_sfx,
                        caption_on_screen_text,
                        duration,
                        continuity_constraints,
                        generation_instructions,
                        qc_gates,
                        downstream_handoff,
                        exact_character_input,
                    ],
                    outputs=[
                        validation_output,
                        director_output,
                        summary_output,
                    ],
                )

            # ============================================================
            # ACCEPTANCE TEST TAB
            # ============================================================

            with gr.Tab("Acceptance Tests"):

                gr.Markdown(
                    "## J.O.A.T. Director Acceptance Tests"
                )

                run_tests_btn = gr.Button(
                    "Run Acceptance Tests",
                    variant="primary",
                )

                test_output = gr.Textbox(
                    label="Test Results",
                    lines=25,
                    interactive=False,
                )

                run_tests_btn.click(
                    fn=run_tests_ui,
                    inputs=None,
                    outputs=test_output,
                )

            # ============================================================
            # ABOUT TAB
            # ============================================================

            with gr.Tab("About"):

                gr.Markdown(
                    f"""
## J.O.A.T. Director Creative Intelligence

**Version:** {DIRECTOR_VERSION}

**Input Schema:** `{CHARACTER_PACKET_SCHEMA}`

**Output Schema:** `{DIRECTOR_SCHEMA_VERSION}`

The Director worker consumes approved, identity-locked
character packets and produces production-ready director packets.

### Protection Rules

- Character identity remains locked.
- Approved SHA-256 references are preserved.
- Character Asset Master is read-only.
- Registry mutation is prohibited.
- Human approval remains required for registry changes.
"""
                )

    return app


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

app = build_app()

if __name__ == "__main__":
    app.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
    )