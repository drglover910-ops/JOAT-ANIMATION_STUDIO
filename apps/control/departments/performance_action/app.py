"""
J.O.A.T. Performance / Action Master v1.0.0

Roadmap Stage #5

Purpose:
- Translate approved Director intent into precise character performance
- Preserve locked Character identity
- Preserve locked Environment identity
- Preserve approved Shot / Camera instructions
- Control emotion, expression, body language, gaze, blocking, action,
  interaction, timing, and shot-to-shot performance continuity
- Produce deterministic joat.performance_action_packet.v1 packets
- Hand controlled performance packets downstream to LTX / Generation
- Never silently mutate upstream locked masters
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Optional

import gradio as gr


# =============================================================================
# CONFIG
# =============================================================================

APP_VERSION = "1.0.0"
PACKET_SCHEMA = "joat.performance_action_packet.v1"

ALLOWED_INTENSITIES = [
    "subtle",
    "low",
    "moderate",
    "strong",
    "extreme",
]

ALLOWED_PACING = [
    "very_slow",
    "slow",
    "natural",
    "quick",
    "very_quick",
]

ALLOWED_GAZE_TYPES = [
    "director_defined",
    "camera",
    "character",
    "object",
    "off_screen",
    "down",
    "up",
    "left",
    "right",
    "forward",
]

ALLOWED_INTERACTION_TYPES = [
    "none",
    "character",
    "object",
    "environment",
    "multiple",
]


# =============================================================================
# HELPERS
# =============================================================================

def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_json(
    raw: Any,
    expected_type: Optional[type] = None,
    field_name: str = "JSON",
) -> Any:
    if isinstance(raw, (dict, list)):
        value = deepcopy(raw)
    elif raw is None or not str(raw).strip():
        raise ValueError(f"{field_name} is required.")
    else:
        try:
            value = json.loads(str(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{field_name} contains invalid JSON: {exc}"
            ) from exc

    if expected_type is not None and not isinstance(value, expected_type):
        raise ValueError(
            f"{field_name} must be a JSON {expected_type.__name__}."
        )

    return value


def first_present(
    source: dict[str, Any],
    paths: list[list[str]],
    default: Any = None,
) -> Any:
    for path in paths:
        current: Any = source
        found = True

        for key in path:
            if not isinstance(current, dict) or key not in current:
                found = False
                break
            current = current[key]

        if found:
            return current

    return default


def packet_reference(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": packet.get("schema"),
        "packet_fingerprint": packet.get("packet_fingerprint"),
        "project_id": packet.get("project_id"),
        "scene_id": packet.get("scene_id")
        or first_present(
            packet,
            [["scene_context", "scene_id"]],
        ),
        "shot_id": packet.get("shot_id")
        or first_present(
            packet,
            [["scene_context", "shot_id"]],
        ),
    }


# =============================================================================
# PERFORMANCE MASTER
# =============================================================================

class PerformanceActionMaster:

    # -------------------------------------------------------------------------
    # UPSTREAM VALIDATION
    # -------------------------------------------------------------------------

    def validate_character_packet(
        self,
        packet: dict[str, Any],
    ) -> None:
        locked = first_present(
            packet,
            [
                ["character_locked"],
                ["identity_locked"],
                ["locked"],
            ],
            False,
        )

        if locked is not True:
            raise ValueError(
                "Character packet rejected: character identity is not locked."
            )

    def validate_environment_packet(
        self,
        packet: dict[str, Any],
    ) -> None:
        locked = first_present(
            packet,
            [
                ["environment_locked"],
                ["identity_locked"],
                ["locked"],
            ],
            False,
        )

        if locked is not True:
            raise ValueError(
                "Environment packet rejected: environment identity is not locked."
            )

    def validate_director_packet(
        self,
        packet: dict[str, Any],
    ) -> None:
        if not isinstance(packet, dict) or not packet:
            raise ValueError("Director packet rejected: packet is empty.")

        if not packet.get("schema"):
            raise ValueError(
                "Director packet rejected: schema is missing."
            )

    def validate_shot_camera_packet(
        self,
        packet: dict[str, Any],
    ) -> None:
        if packet.get("schema") != "joat.shot_camera_packet.v1":
            raise ValueError(
                "Shot/Camera packet rejected: unsupported schema."
            )

        camera_locked = first_present(
            packet,
            [
                ["camera_locked"],
                ["shot_camera_locked"],
                ["locked"],
            ],
            False,
        )

        if camera_locked is not True:
            raise ValueError(
                "Shot/Camera packet rejected: camera instructions are not locked."
            )

    # -------------------------------------------------------------------------
    # PERFORMANCE VALIDATION
    # -------------------------------------------------------------------------

    def validate_performance_spec(
        self,
        spec: dict[str, Any],
    ) -> None:
        required = [
            "emotion",
            "expression",
            "body_language",
            "action",
            "gaze",
            "blocking",
            "interaction",
            "timing",
        ]

        missing = [
            field
            for field in required
            if field not in spec
        ]

        if missing:
            raise ValueError(
                "Performance specification rejected. Missing fields: "
                + ", ".join(missing)
            )

        intensity = spec.get("intensity", "moderate")
        if intensity not in ALLOWED_INTENSITIES:
            raise ValueError(
                f"Unsupported performance intensity: {intensity}"
            )

        timing = spec.get("timing", {})
        if not isinstance(timing, dict):
            raise ValueError("timing must be an object.")

        pacing = timing.get("pacing", "natural")
        if pacing not in ALLOWED_PACING:
            raise ValueError(
                f"Unsupported performance pacing: {pacing}"
            )

        gaze = spec.get("gaze", {})
        if not isinstance(gaze, dict):
            raise ValueError("gaze must be an object.")

        gaze_type = gaze.get("type", "director_defined")
        if gaze_type not in ALLOWED_GAZE_TYPES:
            raise ValueError(
                f"Unsupported gaze type: {gaze_type}"
            )

        interaction = spec.get("interaction", {})
        if not isinstance(interaction, dict):
            raise ValueError("interaction must be an object.")

        interaction_type = interaction.get("type", "none")
        if interaction_type not in ALLOWED_INTERACTION_TYPES:
            raise ValueError(
                f"Unsupported interaction type: {interaction_type}"
            )

        beats = spec.get("performance_beats", [])
        if not isinstance(beats, list):
            raise ValueError("performance_beats must be an array.")

        previous = -1.0

        for beat in beats:
            if not isinstance(beat, dict):
                raise ValueError(
                    "Each performance beat must be an object."
                )

            at_seconds = beat.get("at_seconds")

            if not isinstance(at_seconds, (int, float)):
                raise ValueError(
                    "Each performance beat requires numeric at_seconds."
                )

            if at_seconds < 0:
                raise ValueError(
                    "Performance beat timing cannot be negative."
                )

            if at_seconds < previous:
                raise ValueError(
                    "Performance beats must be chronological."
                )

            previous = float(at_seconds)

    # -------------------------------------------------------------------------
    # CONTINUITY
    # -------------------------------------------------------------------------

    def build_continuity(
        self,
        spec: dict[str, Any],
        previous_performance: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        previous = previous_performance or {}

        return {
            "previous_shot_id": previous.get("shot_id"),
            "previous_emotion": previous.get("ending_emotion"),
            "previous_body_state": previous.get("ending_body_state"),
            "previous_gaze_target": previous.get("ending_gaze_target"),
            "previous_position": previous.get("ending_position"),
            "previous_action_state": previous.get("ending_action_state"),

            "starting_emotion": spec.get("emotion"),
            "starting_body_language": spec.get("body_language"),
            "starting_gaze": deepcopy(spec.get("gaze")),
            "starting_blocking": deepcopy(spec.get("blocking")),
            "starting_action": spec.get("action"),

            "continuity_rules": [
                (
                    "Emotional changes must follow the approved Director "
                    "intent and cannot jump randomly between continuity-linked shots."
                ),
                (
                    "Body position, gaze, hand state, held objects, and active "
                    "actions must logically continue from the previous shot."
                ),
                (
                    "Character interaction must preserve who is touching, "
                    "holding, facing, following, approaching, or reacting to whom."
                ),
                (
                    "Performance continuity cannot change locked character "
                    "identity, wardrobe identity, environment identity, or "
                    "approved camera instructions."
                ),
            ],
        }

    # -------------------------------------------------------------------------
    # PACKET GENERATION
    # -------------------------------------------------------------------------

    def build_packet(
        self,
        character_packet: dict[str, Any],
        environment_packet: dict[str, Any],
        director_packet: dict[str, Any],
        shot_camera_packet: dict[str, Any],
        performance_spec: dict[str, Any],
        previous_performance: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:

        # Validate without mutating upstream packets.
        self.validate_character_packet(character_packet)
        self.validate_environment_packet(environment_packet)
        self.validate_director_packet(director_packet)
        self.validate_shot_camera_packet(shot_camera_packet)
        self.validate_performance_spec(performance_spec)

        character_before = sha256_text(stable_json(character_packet))
        environment_before = sha256_text(stable_json(environment_packet))
        director_before = sha256_text(stable_json(director_packet))
        shot_before = sha256_text(stable_json(shot_camera_packet))

        project_id = first_present(
            shot_camera_packet,
            [
                ["project_id"],
                ["director_reference", "project_id"],
            ],
            first_present(
                director_packet,
                [["project_id"]],
            ),
        )

        scene_id = first_present(
            shot_camera_packet,
            [
                ["scene_id"],
                ["scene_context", "scene_id"],
            ],
            first_present(
                director_packet,
                [["scene_id"]],
            ),
        )

        shot_id = first_present(
            shot_camera_packet,
            [
                ["shot_id"],
                ["scene_context", "shot_id"],
            ],
        )

        character_id = first_present(
            character_packet,
            [
                ["character_id"],
                ["id"],
            ],
        )

        environment_id = first_present(
            environment_packet,
            [
                ["environment_id"],
                ["id"],
            ],
        )

        packet_core = {
            "schema": PACKET_SCHEMA,
            "app_version": APP_VERSION,

            "project_id": project_id,
            "scene_id": scene_id,
            "shot_id": shot_id,
            "character_id": character_id,
            "environment_id": environment_id,

            "performance_locked": True,

            "upstream_locks": {
                "character_identity_locked": True,
                "environment_identity_locked": True,
                "director_intent_preserved": True,
                "shot_camera_preserved": True,
            },

            "upstream_references": {
                "character": packet_reference(character_packet),
                "environment": packet_reference(environment_packet),
                "director": packet_reference(director_packet),
                "shot_camera": packet_reference(shot_camera_packet),
            },

            "performance": {
                "emotion": performance_spec["emotion"],
                "expression": performance_spec["expression"],
                "body_language": performance_spec["body_language"],
                "action": performance_spec["action"],
                "gaze": deepcopy(performance_spec["gaze"]),
                "blocking": deepcopy(performance_spec["blocking"]),
                "interaction": deepcopy(performance_spec["interaction"]),
                "intensity": performance_spec.get(
                    "intensity",
                    "moderate",
                ),
                "timing": deepcopy(performance_spec["timing"]),
                "performance_beats": deepcopy(
                    performance_spec.get(
                        "performance_beats",
                        [],
                    )
                ),
            },

            "continuity": self.build_continuity(
                performance_spec,
                previous_performance,
            ),

            "constraints": {
                "preserve_character_identity": True,
                "preserve_environment_identity": True,
                "preserve_director_intent": True,
                "preserve_camera_instructions": True,
                "prevent_random_emotional_drift": True,
                "prevent_random_action_drift": True,
                "prevent_random_gaze_drift": True,
                "prevent_random_blocking_drift": True,
                "prevent_impossible_pose_transition": True,
                "prevent_unapproved_interaction_change": True,
            },

            "negative_rules": [
                (
                    "Do not alter locked character identity, face, body identity, "
                    "or approved character-master constraints."
                ),
                (
                    "Do not alter the locked environment identity or permanent "
                    "environment geometry."
                ),
                (
                    "Do not rewrite Director intent."
                ),
                (
                    "Do not replace or contradict approved Shot/Camera instructions."
                ),
                (
                    "Do not invent unexplained emotional changes between "
                    "continuity-linked shots."
                ),
                (
                    "Do not teleport characters or objects between positions."
                ),
                (
                    "Do not switch gaze targets, held objects, interaction "
                    "partners, or action states without an approved performance beat."
                ),
                (
                    "Do not create physically impossible body transitions unless "
                    "the Director explicitly requires stylized/impossible motion."
                ),
            ],

            "downstream_handoff": {
                "ltx_compatible": True,
                "generation_supervisor_compatible": True,
                "qc_compatible": True,
                "timeline_compatible": True,
                "upstream_mutation_allowed": False,
            },
        }

        packet_core["packet_fingerprint"] = sha256_text(
            stable_json(packet_core)
        )

        # Confirm generation did not mutate any upstream master.
        if character_before != sha256_text(stable_json(character_packet)):
            raise RuntimeError("Character packet was mutated.")

        if environment_before != sha256_text(stable_json(environment_packet)):
            raise RuntimeError("Environment packet was mutated.")

        if director_before != sha256_text(stable_json(director_packet)):
            raise RuntimeError("Director packet was mutated.")

        if shot_before != sha256_text(stable_json(shot_camera_packet)):
            raise RuntimeError("Shot/Camera packet was mutated.")

        return packet_core

    # -------------------------------------------------------------------------
    # ACCEPTANCE TEST
    # -------------------------------------------------------------------------

    def acceptance_test(self) -> dict[str, Any]:
        tests: list[dict[str, Any]] = []

        def add(
            name: str,
            passed: bool,
            detail: Any = None,
        ) -> None:
            tests.append(
                {
                    "test": name,
                    "pass": bool(passed),
                    "detail": (
                        detail
                        if detail is not None
                        else bool(passed)
                    ),
                }
            )

        character = {
            "schema": "joat.character_packet.v1",
            "character_id": "CHAR-001",
            "character_locked": True,
            "constraints": {
                "identity_preserved": True,
            },
        }

        environment = {
            "schema": "joat.environment_packet.v1",
            "environment_id": "ENV-001",
            "environment_locked": True,
            "asset_identity_lock_ready": True,
        }

        director = {
            "schema": "joat.director_packet.v1",
            "project_id": "PROJECT-TEST-001",
            "scene_id": "SCENE-001",
            "creative_intent": {
                "emotion": "controlled concern",
                "purpose": "Character realizes something is wrong.",
            },
        }

        shot = {
            "schema": "joat.shot_camera_packet.v1",
            "project_id": "PROJECT-TEST-001",
            "scene_id": "SCENE-001",
            "shot_id": "SHOT-001",
            "camera_locked": True,
            "camera": {
                "shot_size": "medium_close_up",
                "angle": "eye_level",
                "movement": "slow_push_in",
            },
        }

        performance = {
            "emotion": "controlled concern",
            "expression": (
                "Brows tighten slightly; lips stop moving; "
                "eyes become more focused."
            ),
            "body_language": (
                "Shoulders become still and torso leans forward slightly."
            ),
            "action": (
                "Character pauses mid-task and slowly turns attention "
                "toward the off-screen sound."
            ),
            "gaze": {
                "type": "off_screen",
                "target": "sound source",
            },
            "blocking": {
                "start_position": "seated at desk",
                "end_position": "seated at desk, torso turned slightly right",
            },
            "interaction": {
                "type": "object",
                "target": "desk paperwork",
                "action": "stops handling paperwork",
            },
            "intensity": "moderate",
            "timing": {
                "pacing": "slow",
                "hold_seconds": 0.5,
            },
            "performance_beats": [
                {
                    "at_seconds": 0.0,
                    "beat": "working normally",
                },
                {
                    "at_seconds": 1.0,
                    "beat": "hears sound and freezes",
                },
                {
                    "at_seconds": 1.5,
                    "beat": "eyes move toward sound source",
                },
                {
                    "at_seconds": 2.0,
                    "beat": "torso turns slightly toward sound",
                },
            ],
        }

        previous = {
            "shot_id": "SHOT-000",
            "ending_emotion": "neutral focus",
            "ending_body_state": "seated upright",
            "ending_gaze_target": "desk paperwork",
            "ending_position": "seated at desk",
            "ending_action_state": "sorting paperwork",
        }

        # 1
        try:
            packet = self.build_packet(
                character,
                environment,
                director,
                shot,
                performance,
                previous,
            )
            add(
                "1. Performance/Action packet generates",
                True,
            )
        except Exception as exc:
            packet = {}
            add(
                "1. Performance/Action packet generates",
                False,
                str(exc),
            )

        # 2
        required_packet_fields = [
            "schema",
            "project_id",
            "scene_id",
            "shot_id",
            "character_id",
            "environment_id",
            "performance_locked",
            "upstream_locks",
            "upstream_references",
            "performance",
            "continuity",
            "constraints",
            "negative_rules",
            "downstream_handoff",
            "packet_fingerprint",
        ]

        add(
            "2. Required packet fields present",
            all(
                field in packet
                for field in required_packet_fields
            ),
        )

        # 3
        required_performance_fields = [
            "emotion",
            "expression",
            "body_language",
            "action",
            "gaze",
            "blocking",
            "interaction",
            "intensity",
            "timing",
            "performance_beats",
        ]

        add(
            "3. Required performance fields present",
            all(
                field in packet.get("performance", {})
                for field in required_performance_fields
            ),
        )

        # 4
        add(
            "4. Character identity lock preserved",
            packet.get(
                "upstream_locks",
                {},
            ).get(
                "character_identity_locked"
            ) is True
            and packet.get(
                "constraints",
                {},
            ).get(
                "preserve_character_identity"
            ) is True,
        )

        # 5
        add(
            "5. Environment identity lock preserved",
            packet.get(
                "upstream_locks",
                {},
            ).get(
                "environment_identity_locked"
            ) is True
            and packet.get(
                "constraints",
                {},
            ).get(
                "preserve_environment_identity"
            ) is True,
        )

        # 6
        add(
            "6. Director intent preserved",
            packet.get(
                "upstream_locks",
                {},
            ).get(
                "director_intent_preserved"
            ) is True
            and packet.get(
                "constraints",
                {},
            ).get(
                "preserve_director_intent"
            ) is True,
        )

        # 7
        add(
            "7. Shot/Camera instructions preserved",
            packet.get(
                "upstream_locks",
                {},
            ).get(
                "shot_camera_preserved"
            ) is True
            and packet.get(
                "constraints",
                {},
            ).get(
                "preserve_camera_instructions"
            ) is True,
        )

        # 8
        second = self.build_packet(
            deepcopy(character),
            deepcopy(environment),
            deepcopy(director),
            deepcopy(shot),
            deepcopy(performance),
            deepcopy(previous),
        )

        add(
            "8. Deterministic packet fingerprint",
            packet.get("packet_fingerprint")
            == second.get("packet_fingerprint"),
        )

        # 9
        unlocked_character = deepcopy(character)
        unlocked_character["character_locked"] = False

        try:
            self.build_packet(
                unlocked_character,
                environment,
                director,
                shot,
                performance,
                previous,
            )
            rejected = False
        except ValueError:
            rejected = True

        add(
            "9. Unlocked character packet rejected",
            rejected,
        )

        # 10
        unlocked_environment = deepcopy(environment)
        unlocked_environment["environment_locked"] = False

        try:
            self.build_packet(
                character,
                unlocked_environment,
                director,
                shot,
                performance,
                previous,
            )
            rejected = False
        except ValueError:
            rejected = True

        add(
            "10. Unlocked environment packet rejected",
            rejected,
        )

        # 11
        unlocked_shot = deepcopy(shot)
        unlocked_shot["camera_locked"] = False

        try:
            self.build_packet(
                character,
                environment,
                director,
                unlocked_shot,
                performance,
                previous,
            )
            rejected = False
        except ValueError:
            rejected = True

        add(
            "11. Unlocked Shot/Camera packet rejected",
            rejected,
        )

        # 12
        bad_performance = deepcopy(performance)
        bad_performance.pop("action")

        try:
            self.build_packet(
                character,
                environment,
                director,
                shot,
                bad_performance,
                previous,
            )
            rejected = False
        except ValueError:
            rejected = True

        add(
            "12. Malformed performance specification rejected",
            rejected,
        )

        # 13
        bad_intensity = deepcopy(performance)
        bad_intensity["intensity"] = "random_uncontrolled"

        try:
            self.build_packet(
                character,
                environment,
                director,
                shot,
                bad_intensity,
                previous,
            )
            rejected = False
        except ValueError:
            rejected = True

        add(
            "13. Unsupported performance intensity rejected",
            rejected,
        )

        # 14
        continuity = packet.get("continuity", {})

        add(
            "14. Shot-to-shot emotional/action continuity tracked",
            continuity.get("previous_shot_id") == "SHOT-000"
            and continuity.get("previous_emotion") == "neutral focus"
            and continuity.get("previous_action_state")
            == "sorting paperwork",
        )

        # 15
        bad_beats = deepcopy(performance)
        bad_beats["performance_beats"] = [
            {
                "at_seconds": 2.0,
                "beat": "second",
            },
            {
                "at_seconds": 1.0,
                "beat": "impossible backwards timing",
            },
        ]

        try:
            self.build_packet(
                character,
                environment,
                director,
                shot,
                bad_beats,
                previous,
            )
            rejected = False
        except ValueError:
            rejected = True

        add(
            "15. Invalid performance beat timing rejected",
            rejected,
        )

        # 16
        constraints = packet.get("constraints", {})

        drift_protection = all(
            constraints.get(key) is True
            for key in [
                "prevent_random_emotional_drift",
                "prevent_random_action_drift",
                "prevent_random_gaze_drift",
                "prevent_random_blocking_drift",
                "prevent_impossible_pose_transition",
                "prevent_unapproved_interaction_change",
            ]
        )

        add(
            "16. Performance drift protection active",
            drift_protection,
        )

        # 17
        handoff = packet.get("downstream_handoff", {})

        add(
            "17. LTX / Generation downstream handoff enabled",
            handoff.get("ltx_compatible") is True
            and handoff.get(
                "generation_supervisor_compatible"
            ) is True
            and handoff.get("qc_compatible") is True
            and handoff.get("timeline_compatible") is True
            and handoff.get(
                "upstream_mutation_allowed"
            ) is False,
        )

        # 18
        originals = {
            "character": deepcopy(character),
            "environment": deepcopy(environment),
            "director": deepcopy(director),
            "shot": deepcopy(shot),
        }

        self.build_packet(
            character,
            environment,
            director,
            shot,
            performance,
            previous,
        )

        immutable = (
            character == originals["character"]
            and environment == originals["environment"]
            and director == originals["director"]
            and shot == originals["shot"]
        )

        add(
            "18. Locked upstream masters protected from mutation",
            immutable,
        )

        all_passed = all(
            test["pass"]
            for test in tests
        )

        return {
            "acceptance_test_version": "1.0.0",
            "app_version": APP_VERSION,
            "packet_schema": PACKET_SCHEMA,
            "tests": tests,
            "all_passed": all_passed,
            "production_ready": all_passed,
            "note": (
                "Performance/Action Master is production-ready when all "
                "acceptance tests pass and Character, Environment, Director, "
                "and Shot/Camera inputs remain locked and immutable."
            ),
        }


MASTER = PerformanceActionMaster()


# =============================================================================
# UI FUNCTIONS
# =============================================================================

def build_packet_ui(
    character_json: str,
    environment_json: str,
    director_json: str,
    shot_json: str,
    performance_json: str,
    previous_json: str,
) -> dict[str, Any]:

    character = parse_json(
        character_json,
        dict,
        "Character packet",
    )

    environment = parse_json(
        environment_json,
        dict,
        "Environment packet",
    )

    director = parse_json(
        director_json,
        dict,
        "Director packet",
    )

    shot = parse_json(
        shot_json,
        dict,
        "Shot/Camera packet",
    )

    performance = parse_json(
        performance_json,
        dict,
        "Performance specification",
    )

    previous = None

    if previous_json and str(previous_json).strip():
        previous = parse_json(
            previous_json,
            dict,
            "Previous performance state",
        )

    return MASTER.build_packet(
        character_packet=character,
        environment_packet=environment,
        director_packet=director,
        shot_camera_packet=shot,
        performance_spec=performance,
        previous_performance=previous,
    )


def tests_ui() -> dict[str, Any]:
    return MASTER.acceptance_test()


def example_inputs() -> tuple[str, str, str, str, str, str]:

    character = {
        "schema": "joat.character_packet.v1",
        "character_id": "CHAR-001",
        "character_locked": True,
        "constraints": {
            "identity_preserved": True,
        },
    }

    environment = {
        "schema": "joat.environment_packet.v1",
        "environment_id": "ENV-001",
        "environment_locked": True,
        "asset_identity_lock_ready": True,
    }

    director = {
        "schema": "joat.director_packet.v1",
        "project_id": "PROJECT-DEMO-001",
        "scene_id": "SCENE-001",
        "creative_intent": {
            "emotion": "controlled concern",
            "purpose": "Character realizes something is wrong.",
        },
    }

    shot = {
        "schema": "joat.shot_camera_packet.v1",
        "project_id": "PROJECT-DEMO-001",
        "scene_id": "SCENE-001",
        "shot_id": "SHOT-001",
        "camera_locked": True,
        "camera": {
            "shot_size": "medium_close_up",
            "angle": "eye_level",
            "movement": "slow_push_in",
        },
    }

    performance = {
        "emotion": "controlled concern",
        "expression": (
            "Brows tighten slightly; lips stop moving; "
            "eyes become more focused."
        ),
        "body_language": (
            "Shoulders become still and torso leans forward slightly."
        ),
        "action": (
            "Character pauses mid-task and turns attention "
            "toward the off-screen sound."
        ),
        "gaze": {
            "type": "off_screen",
            "target": "sound source",
        },
        "blocking": {
            "start_position": "seated at desk",
            "end_position": "seated at desk, torso turned slightly right",
        },
        "interaction": {
            "type": "object",
            "target": "desk paperwork",
            "action": "stops handling paperwork",
        },
        "intensity": "moderate",
        "timing": {
            "pacing": "slow",
            "hold_seconds": 0.5,
        },
        "performance_beats": [
            {
                "at_seconds": 0.0,
                "beat": "working normally",
            },
            {
                "at_seconds": 1.0,
                "beat": "hears sound and freezes",
            },
            {
                "at_seconds": 1.5,
                "beat": "eyes move toward sound source",
            },
            {
                "at_seconds": 2.0,
                "beat": "torso turns slightly toward sound",
            },
        ],
    }

    previous = {
        "shot_id": "SHOT-000",
        "ending_emotion": "neutral focus",
        "ending_body_state": "seated upright",
        "ending_gaze_target": "desk paperwork",
        "ending_position": "seated at desk",
        "ending_action_state": "sorting paperwork",
    }

    return tuple(
        json.dumps(x, indent=2)
        for x in [
            character,
            environment,
            director,
            shot,
            performance,
            previous,
        ]
    )


# =============================================================================
# GRADIO APP
# =============================================================================

def build_app() -> gr.Blocks:

    examples = example_inputs()

    with gr.Blocks(
        title=f"J.O.A.T. Performance / Action Master v{APP_VERSION}"
    ) as app:

        gr.Markdown(
            f"# J.O.A.T. Performance / Action Master — v{APP_VERSION}\n\n"
            "**Roadmap Stage #5**  \n"
            "Translates approved creative direction into controlled "
            "character emotion, expression, body language, action, gaze, "
            "blocking, interaction, timing, and continuity while protecting "
            "all locked upstream masters."
        )

        with gr.Tab("Performance Packet"):

            gr.Markdown(
                "### Locked Upstream Inputs\n"
                "Character + Environment + Director + Shot/Camera are "
                "treated as protected inputs. This worker may interpret "
                "performance, but may not rewrite those masters."
            )

            character_input = gr.Textbox(
                value=examples[0],
                lines=12,
                label="Character Packet JSON",
            )

            environment_input = gr.Textbox(
                value=examples[1],
                lines=12,
                label="Environment Packet JSON",
            )

            director_input = gr.Textbox(
                value=examples[2],
                lines=12,
                label="Director Packet JSON",
            )

            shot_input = gr.Textbox(
                value=examples[3],
                lines=14,
                label="Shot / Camera Packet JSON",
            )

            gr.Markdown(
                "### Performance Instructions"
            )

            performance_input = gr.Textbox(
                value=examples[4],
                lines=28,
                label="Performance Specification JSON",
            )

            previous_input = gr.Textbox(
                value=examples[5],
                lines=14,
                label="Previous Shot Performance State JSON (optional)",
            )

            packet_output = gr.JSON(
                label="Performance / Action Packet",
            )

            gr.Button(
                "Build Performance Packet",
                variant="primary",
            ).click(
                fn=build_packet_ui,
                inputs=[
                    character_input,
                    environment_input,
                    director_input,
                    shot_input,
                    performance_input,
                    previous_input,
                ],
                outputs=packet_output,
            )

        with gr.Tab("Acceptance Tests"):

            gr.Markdown(
                "Runs the complete Stage #5 production-readiness test."
            )

            test_output = gr.JSON(
                label="Performance / Action Acceptance Test"
            )

            gr.Button(
                "Run Acceptance Tests",
                variant="primary",
            ).click(
                fn=tests_ui,
                inputs=None,
                outputs=test_output,
            )

        with gr.Tab("Responsibilities"):

            gr.Markdown(
                """
## Performance / Action Responsibilities

This worker owns:

- Emotion
- Facial expression
- Body language
- Character action
- Gesture
- Gaze / eye target
- Blocking and physical position
- Character-to-character interaction
- Character-to-object interaction
- Performance intensity
- Performance timing and beats
- Emotional continuity
- Action continuity
- Physical continuity between shots

## Authority Boundary

This worker **cannot** independently change:

- Locked Character identity
- Locked Environment identity
- Director creative intent
- Approved Shot / Camera instructions

If one of those needs changing, the job must return to the responsible
upstream department.

## Downstream

Approved packets are designed for:

**Performance / Action → LTX / Generation → QC / Continuity → Post**
"""
            )

        with gr.Tab("About"):

            gr.Markdown(
                f"""
## J.O.A.T. Performance / Action Master

**Version:** {APP_VERSION}

**Packet:** `{PACKET_SCHEMA}`

This is Roadmap Stage #5.

The Performance / Action Master acts like the studio's performance
instruction layer. It converts approved creative intent into explicit,
machine-readable acting and movement instructions while preserving
identity, environment, cinematography, and continuity locks.
"""
            )

    return app


if __name__ == "__main__":
    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )