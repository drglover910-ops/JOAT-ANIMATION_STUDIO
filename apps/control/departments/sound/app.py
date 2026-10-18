"""
J.O.A.T. Sound Worker Bot v1.0.1

Roadmap Stage #11

Bot Type:
- Specialist Worker Bot

Reports To:
- J.O.A.T. Post-Production Supervisor Bot

Assistant:
- J.O.A.T. Audio Assistant Bot

Purpose:
- Receive approved Sound Department work orders
- Validate Post-Production Supervisor routing
- Preserve QC provenance
- Prepare deterministic sound execution instructions
- Manage dialogue, ambience, Foley, SFX, synchronization, and levels
- Protect all locked creative decisions
- Return completed sound results to the Post-Production Supervisor
- Never compose or replace the musical score
- Never rewrite dialogue or reinterpret approved performance
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import gradio as gr


# =============================================================================
# CONFIG
# =============================================================================

APP_VERSION = "1.0.1"

BOT_NAME = "J.O.A.T. Sound Worker Bot"
BOT_TYPE = "sound_worker_bot"

ASSISTANT_BOT = "J.O.A.T. Audio Assistant Bot"
ASSISTANT_REQUIRED = True

REPORTS_TO = "J.O.A.T. Post-Production Supervisor Bot"

WORK_ORDER_SCHEMA = "joat.post_work_order.v1"
EXECUTION_SCHEMA = "joat.sound_execution.v1"
RESULT_SCHEMA = "joat.sound_result.v1"

EXPECTED_DEPARTMENT = "sound"

SUPPORTED_SOUND_TASKS = [
    "dialogue",
    "dialogue_editing",
    "dialogue_cleanup",
    "ambience",
    "foley",
    "sound_effects",
    "sfx",
    "sync",
    "audio_sync",
    "leveling",
    "mix_preparation",
    "sound_edit",
]

PROHIBITED_TASKS = [
    "music_composition",
    "score_composition",
    "rewrite_dialogue",
    "rewrite_story",
    "change_character_identity",
    "change_environment_identity",
    "reinterpret_director_intent",
    "reinterpret_camera",
    "reinterpret_performance",
    "replace_voice_identity",
    "silent_creative_change",
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
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def fingerprint(value: Any) -> str:
    return sha256_text(stable_json(value))


def parse_json_object(
    raw: str,
    label: str,
) -> dict[str, Any]:
    if raw is None or not str(raw).strip():
        raise ValueError(
            f"{label} is required."
        )

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label} contains invalid JSON: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise ValueError(
            f"{label} must be a JSON object."
        )

    return value


def get_work_order_fingerprint(
    work_order: dict[str, Any],
) -> str:
    existing = work_order.get(
        "work_order_fingerprint"
    )

    if existing:
        return str(existing)

    return fingerprint(work_order)


def qc_is_approved(
    work_order: dict[str, Any],
) -> bool:
    provenance = work_order.get(
        "qc_provenance",
        {},
    )

    if not isinstance(provenance, dict):
        return False

    return (
        provenance.get("qc_status") == "PASS"
        and provenance.get(
            "post_production_authorized"
        ) is True
    )


def validate_authority_boundary(
    work_order: dict[str, Any],
) -> None:
    boundary = work_order.get(
        "authority_boundary",
        {},
    )

    if not isinstance(boundary, dict):
        raise ValueError(
            "Sound work order rejected: "
            "authority_boundary is required."
        )

    required_false = [
        "may_change_character_identity",
        "may_change_environment_identity",
        "may_reinterpret_director_intent",
        "may_reinterpret_camera_intent",
        "may_reinterpret_performance_intent",
        "may_rewrite_story",
        "may_rewrite_dialogue",
        "may_silently_change_creative_intent",
    ]

    for field in required_false:
        if boundary.get(field) is not False:
            raise ValueError(
                "Sound work order rejected: "
                f"{field} must be false."
            )


def validate_work_order(
    work_order: dict[str, Any],
) -> dict[str, Any]:

    if work_order.get("schema") != WORK_ORDER_SCHEMA:
        raise ValueError(
            "Sound work order rejected: "
            f"schema must be {WORK_ORDER_SCHEMA!r}."
        )

    if (
        work_order.get("department")
        != EXPECTED_DEPARTMENT
    ):
        raise ValueError(
            "Sound work order rejected: "
            "department must be 'sound'."
        )

    if (
        work_order.get("assigned_bot")
        != BOT_NAME
    ):
        raise ValueError(
            "Sound work order rejected: "
            f"assigned_bot must be {BOT_NAME!r}."
        )

    source_asset = work_order.get(
        "source_asset",
        {},
    )

    if not isinstance(source_asset, dict):
        raise ValueError(
            "Sound work order rejected: "
            "source_asset is required."
        )

    if not source_asset.get("asset_id"):
        raise ValueError(
            "Sound work order rejected: "
            "source asset_id is required."
        )

    if not qc_is_approved(work_order):
        raise ValueError(
            "Sound work order rejected: "
            "source asset must have QC PASS and "
            "Post-Production authorization."
        )

    validate_authority_boundary(work_order)

    requested_tasks = work_order.get(
        "requested_tasks",
        [],
    )

    if not isinstance(requested_tasks, list):
        raise ValueError(
            "Sound work order rejected: "
            "requested_tasks must be a list."
        )

    for task in requested_tasks:
        if task in PROHIBITED_TASKS:
            raise ValueError(
                "Sound work order rejected: "
                f"prohibited task requested: {task}"
            )

    return {
        "work_order_valid": True,
        "department_verified": True,
        "assignment_verified": True,
        "source_asset_verified": True,
        "qc_provenance_verified": True,
        "authority_boundary_verified": True,
        "work_order_fingerprint":
            get_work_order_fingerprint(
                work_order
            ),
    }


# =============================================================================
# SOUND WORKER
# =============================================================================

class SoundWorkerBot:

    def build_execution(
        self,
        work_order: dict[str, Any],
    ) -> dict[str, Any]:

        validation = validate_work_order(
            work_order
        )

        immutable_snapshot = deepcopy(
            work_order
        )

        requested_tasks = deepcopy(
            work_order.get(
                "requested_tasks",
                [],
            )
        )

        execution_core = {
            "schema": EXECUTION_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,

            "assistant": {
                "assistant_bot": ASSISTANT_BOT,
                "assistant_required":
                    ASSISTANT_REQUIRED,
                "authority": {
                    "may_prepare_audio_assets":
                        True,
                    "may_organize_tracks":
                        True,
                    "may_prepare_sync_metadata":
                        True,
                    "may_prepare_level_metadata":
                        True,
                    "may_make_final_sound_decision":
                        False,
                    "may_change_creative_intent":
                        False,
                },
            },

            "reports_to": REPORTS_TO,

            "validation": validation,

            "source_asset": deepcopy(
                work_order["source_asset"]
            ),

            "qc_provenance": deepcopy(
                work_order["qc_provenance"]
            ),

            "requested_tasks": requested_tasks,

            "sound_scope": {
                "dialogue_editing_allowed":
                    True,
                "dialogue_cleanup_allowed":
                    True,
                "ambience_allowed":
                    True,
                "foley_allowed":
                    True,
                "sound_effects_allowed":
                    True,
                "synchronization_allowed":
                    True,
                "level_preparation_allowed":
                    True,
                "mix_preparation_allowed":
                    True,

                "music_composition_allowed":
                    False,
                "score_replacement_allowed":
                    False,
                "dialogue_rewrite_allowed":
                    False,
                "voice_identity_change_allowed":
                    False,
            },

            "creative_integrity_policy": {
                "preserve_character_identity":
                    True,
                "preserve_environment_identity":
                    True,
                "preserve_director_intent":
                    True,
                "preserve_camera_intent":
                    True,
                "preserve_performance_intent":
                    True,
                "preserve_story":
                    True,
                "preserve_dialogue_content":
                    True,
                "preserve_voice_identity":
                    True,
                "silent_creative_change_allowed":
                    False,
            },

            "execution_policy": {
                "technical_audio_cleanup_allowed":
                    True,
                "technical_sync_adjustment_allowed":
                    True,
                "technical_level_adjustment_allowed":
                    True,
                "creative_rewrite_allowed":
                    False,
                "music_department_override_allowed":
                    False,
                "upstream_mutation_allowed":
                    False,
                "human_approval_required_for_locked_change":
                    True,
            },

            "immutable_work_order_snapshot":
                immutable_snapshot,

            "return_route": {
                "destination": REPORTS_TO,
                "result_schema": RESULT_SCHEMA,
                "ready_for_post_supervisor":
                    False,
            },
        }

        execution_core[
            "execution_fingerprint"
        ] = fingerprint(execution_core)

        return execution_core

    def build_result(
        self,
        execution: dict[str, Any],
        output_asset_id: str,
        output_uri: str,
        completed: bool = True,
        creative_integrity_preserved: bool = True,
    ) -> dict[str, Any]:

        if (
            execution.get("schema")
            != EXECUTION_SCHEMA
        ):
            raise ValueError(
                "Sound result rejected: "
                "invalid execution schema."
            )

        if (
            execution.get("bot_name")
            != BOT_NAME
        ):
            raise ValueError(
                "Sound result rejected: "
                "execution belongs to wrong bot."
            )

        if not output_asset_id:
            raise ValueError(
                "Sound result rejected: "
                "output_asset_id is required."
            )

        if not output_uri:
            raise ValueError(
                "Sound result rejected: "
                "output_uri is required."
            )

        if not creative_integrity_preserved:
            raise ValueError(
                "Sound result rejected: "
                "creative integrity failure."
            )

        result_core = {
            "schema": RESULT_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,

            "reports_to": REPORTS_TO,

            "execution_fingerprint":
                execution.get(
                    "execution_fingerprint"
                ),

            "source_asset": deepcopy(
                execution.get(
                    "source_asset",
                    {},
                )
            ),

            "qc_provenance": deepcopy(
                execution.get(
                    "qc_provenance",
                    {},
                )
            ),

            "output_asset": {
                "asset_id":
                    output_asset_id,
                "uri":
                    output_uri,
                "asset_type":
                    "post_production_sound",
            },

            "completion": {
                "completed": bool(completed),
                "creative_integrity_preserved":
                    bool(
                        creative_integrity_preserved
                    ),
            },

            "creative_integrity": deepcopy(
                execution[
                    "creative_integrity_policy"
                ]
            ),

            "handoff": {
                "destination": REPORTS_TO,
                "authorized": (
                    bool(completed)
                    and bool(
                        creative_integrity_preserved
                    )
                ),
            },
        }

        result_core[
            "result_fingerprint"
        ] = fingerprint(result_core)

        return result_core

    def acceptance_test(
        self,
    ) -> dict[str, Any]:

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

        work_order = {
            "schema": WORK_ORDER_SCHEMA,
            "work_order_id":
                "POST-SOUND-001",
            "department": "sound",
            "assigned_bot": BOT_NAME,

            "source_asset": {
                "asset_id":
                    "SHOT-001-QC-PASS",
                "uri":
                    "asset://shot-001",
                "asset_type":
                    "qc_approved_shot",
            },

            "qc_provenance": {
                "qc_status": "PASS",
                "qc_packet_fingerprint":
                    "QC-FP-001",
                "post_production_authorized":
                    True,
            },

            "requested_tasks": [
                "dialogue_editing",
                "ambience",
                "foley",
                "sound_effects",
                "audio_sync",
                "leveling",
            ],

            "authority_boundary": {
                "may_change_character_identity":
                    False,
                "may_change_environment_identity":
                    False,
                "may_reinterpret_director_intent":
                    False,
                "may_reinterpret_camera_intent":
                    False,
                "may_reinterpret_performance_intent":
                    False,
                "may_rewrite_story":
                    False,
                "may_rewrite_dialogue":
                    False,
                "may_silently_change_creative_intent":
                    False,
            },
        }

        work_order[
            "work_order_fingerprint"
        ] = fingerprint(
            {
                k: v
                for k, v
                in work_order.items()
                if k
                != "work_order_fingerprint"
            }
        )

        # 1
        validation = validate_work_order(
            work_order
        )

        add(
            "1. Post work order schema validates",
            validation[
                "work_order_valid"
            ] is True,
        )

        # 2
        add(
            "2. Sound department verified",
            validation[
                "department_verified"
            ] is True,
        )

        # 3
        add(
            "3. Sound Worker Bot assignment verified",
            validation[
                "assignment_verified"
            ] is True,
        )

        # 4
        add(
            "4. Source asset verified",
            validation[
                "source_asset_verified"
            ] is True,
        )

        # 5
        add(
            "5. QC provenance verified",
            validation[
                "qc_provenance_verified"
            ] is True,
        )

        # 6
        add(
            "6. Authority boundary verified",
            validation[
                "authority_boundary_verified"
            ] is True,
        )

        # 7
        execution = self.build_execution(
            work_order
        )

        add(
            "7. Sound execution packet generates",
            execution.get("schema")
            == EXECUTION_SCHEMA,
        )

        # 8
        required_execution_fields = [
            "schema",
            "app_version",
            "bot_name",
            "bot_type",
            "assistant",
            "reports_to",
            "validation",
            "source_asset",
            "qc_provenance",
            "requested_tasks",
            "sound_scope",
            "creative_integrity_policy",
            "execution_policy",
            "immutable_work_order_snapshot",
            "return_route",
            "execution_fingerprint",
        ]

        add(
            "8. Required execution fields present",
            all(
                field in execution
                for field
                in required_execution_fields
            ),
        )

        # 9
        add(
            "9. Audio Assistant Bot relationship declared",
            (
                execution["assistant"][
                    "assistant_bot"
                ]
                == ASSISTANT_BOT
                and execution[
                    "assistant"
                ][
                    "assistant_required"
                ] is True
            ),
        )

        # 10
        add(
            "10. Sound Worker reports to Post Supervisor",
            execution["reports_to"]
            == REPORTS_TO,
        )

        # 11
        add(
            "11. QC-approved assets accepted",
            (
                execution[
                    "qc_provenance"
                ]["qc_status"]
                == "PASS"
                and execution[
                    "qc_provenance"
                ][
                    "post_production_authorized"
                ] is True
            ),
        )

        policy = execution[
            "creative_integrity_policy"
        ]

        # 12
        add(
            "12. Character identity mutation prohibited",
            policy[
                "preserve_character_identity"
            ] is True,
        )

        # 13
        add(
            "13. Environment identity mutation prohibited",
            policy[
                "preserve_environment_identity"
            ] is True,
        )

        # 14
        add(
            "14. Director reinterpretation prohibited",
            policy[
                "preserve_director_intent"
            ] is True,
        )

        # 15
        add(
            "15. Camera reinterpretation prohibited",
            policy[
                "preserve_camera_intent"
            ] is True,
        )

        # 16
        add(
            "16. Performance reinterpretation prohibited",
            policy[
                "preserve_performance_intent"
            ] is True,
        )

        # 17
        add(
            "17. Dialogue rewrite prohibited",
            (
                policy[
                    "preserve_dialogue_content"
                ] is True
                and execution[
                    "sound_scope"
                ][
                    "dialogue_rewrite_allowed"
                ] is False
            ),
        )

        # 18
        add(
            "18. Music composition prohibited",
            execution[
                "sound_scope"
            ][
                "music_composition_allowed"
            ] is False,
        )

        # 19
        add(
            "19. Voice identity mutation prohibited",
            (
                policy[
                    "preserve_voice_identity"
                ] is True
                and execution[
                    "sound_scope"
                ][
                    "voice_identity_change_allowed"
                ] is False
            ),
        )

        # 20
        add(
            "20. Silent creative change prohibited",
            policy[
                "silent_creative_change_allowed"
            ] is False,
        )

        # 21
        first = self.build_execution(
            work_order
        )
        second = self.build_execution(
            work_order
        )

        add(
            "21. Deterministic execution fingerprint",
            first[
                "execution_fingerprint"
            ]
            == second[
                "execution_fingerprint"
            ],
        )

        # 22
        before = stable_json(
            work_order
        )

        self.build_execution(
            work_order
        )

        after = stable_json(
            work_order
        )

        add(
            "22. Post work order remains immutable",
            before == after,
        )

        # 23
        rejected = False

        bad = deepcopy(work_order)
        bad["department"] = "editorial"

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "23. Wrong department work order rejected",
            rejected,
        )

        # 24
        rejected = False

        bad = deepcopy(work_order)
        bad["assigned_bot"] = (
            "J.O.A.T. Music Worker Bot"
        )

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "24. Wrong bot assignment rejected",
            rejected,
        )

        # 25
        rejected = False

        bad = deepcopy(work_order)
        bad["qc_provenance"] = {}

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "25. Missing QC provenance rejected",
            rejected,
        )

        # 26
        rejected = False

        bad = deepcopy(work_order)
        bad["qc_provenance"][
            "qc_status"
        ] = "REJECT"

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "26. Non-QC-approved asset rejected",
            rejected,
        )

        # 27
        rejected = False

        bad = deepcopy(work_order)
        bad[
            "requested_tasks"
        ] = [
            "rewrite_dialogue"
        ]

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "27. Dialogue rewrite request rejected",
            rejected,
        )

        # 28
        rejected = False

        bad = deepcopy(work_order)
        bad[
            "requested_tasks"
        ] = [
            "music_composition"
        ]

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "28. Music composition request rejected",
            rejected,
        )

        # 29
        result = self.build_result(
            execution=execution,
            output_asset_id=(
                "SOUND-RESULT-001"
            ),
            output_uri=(
                "asset://sound-result-001"
            ),
            completed=True,
            creative_integrity_preserved=True,
        )

        add(
            "29. Sound result packet generates",
            result.get("schema")
            == RESULT_SCHEMA,
        )

        # 30
        required_result_fields = [
            "schema",
            "app_version",
            "bot_name",
            "bot_type",
            "reports_to",
            "execution_fingerprint",
            "source_asset",
            "qc_provenance",
            "output_asset",
            "completion",
            "creative_integrity",
            "handoff",
            "result_fingerprint",
        ]

        add(
            "30. Required result fields present",
            all(
                field in result
                for field
                in required_result_fields
            ),
        )

        # 31
        add(
            "31. Sound result preserves creative integrity",
            result[
                "completion"
            ][
                "creative_integrity_preserved"
            ] is True,
        )

        # 32
        add(
            "32. Sound result preserves QC provenance",
            (
                result[
                    "qc_provenance"
                ]["qc_status"]
                == "PASS"
            ),
        )

        # 33
        add(
            "33. Completed sound routes to Post Supervisor",
            (
                result[
                    "handoff"
                ]["destination"]
                == REPORTS_TO
                and result[
                    "handoff"
                ]["authorized"]
                is True
            ),
        )

        # 34
        rejected = False

        try:
            self.build_result(
                execution=execution,
                output_asset_id=(
                    "SOUND-BAD-001"
                ),
                output_uri=(
                    "asset://sound-bad-001"
                ),
                completed=True,
                creative_integrity_preserved=False,
            )
        except ValueError:
            rejected = True

        add(
            "34. Creative-integrity failure blocks sound result",
            rejected,
        )

        all_passed = all(
            test["pass"]
            for test in tests
        )

        return {
            "acceptance_test_version":
                "1.0.0",
            "app_version":
                APP_VERSION,
            "bot_name":
                BOT_NAME,
            "bot_type":
                BOT_TYPE,
            "assistant_bot":
                ASSISTANT_BOT,
            "assistant_required":
                ASSISTANT_REQUIRED,
            "reports_to":
                REPORTS_TO,
            "work_order_schema":
                WORK_ORDER_SCHEMA,
            "execution_schema":
                EXECUTION_SCHEMA,
            "result_schema":
                RESULT_SCHEMA,
            "tests":
                tests,
            "all_passed":
                all_passed,
            "production_ready":
                all_passed,
            "note": (
                "Sound Worker Bot is production-ready "
                "when only properly routed QC-approved "
                "assets enter sound execution, dialogue "
                "and voice identity remain protected, "
                "music composition stays outside the "
                "Sound Department, creative changes are "
                "prohibited, and completed sound results "
                "return to the Post-Production Supervisor Bot."
            ),
        }


SOUND_WORKER = SoundWorkerBot()


# =============================================================================
# EXAMPLE
# =============================================================================

def example_work_order() -> dict[str, Any]:

    work_order = {
        "schema": WORK_ORDER_SCHEMA,
        "work_order_id":
            "POST-SOUND-001",
        "department":
            "sound",
        "assigned_bot":
            BOT_NAME,

        "source_asset": {
            "asset_id":
                "SHOT-001-QC-PASS",
            "uri":
                "asset://shot-001",
            "asset_type":
                "qc_approved_shot",
        },

        "qc_provenance": {
            "qc_status":
                "PASS",
            "qc_packet_fingerprint":
                "QC-FP-001",
            "post_production_authorized":
                True,
        },

        "requested_tasks": [
            "dialogue_editing",
            "ambience",
            "foley",
            "sound_effects",
            "audio_sync",
            "leveling",
        ],

        "authority_boundary": {
            "may_change_character_identity":
                False,
            "may_change_environment_identity":
                False,
            "may_reinterpret_director_intent":
                False,
            "may_reinterpret_camera_intent":
                False,
            "may_reinterpret_performance_intent":
                False,
            "may_rewrite_story":
                False,
            "may_rewrite_dialogue":
                False,
            "may_silently_change_creative_intent":
                False,
        },
    }

    work_order[
        "work_order_fingerprint"
    ] = fingerprint(
        {
            k: v
            for k, v
            in work_order.items()
            if k
            != "work_order_fingerprint"
        }
    )

    return work_order


# =============================================================================
# UI FUNCTIONS
# =============================================================================

def build_execution_ui(
    work_order_raw: str,
) -> dict[str, Any]:

    work_order = parse_json_object(
        work_order_raw,
        "Post work order",
    )

    return SOUND_WORKER.build_execution(
        work_order
    )


def build_result_ui(
    execution_raw: str,
    output_asset_id: str,
    output_uri: str,
) -> dict[str, Any]:

    execution = parse_json_object(
        execution_raw,
        "Sound execution",
    )

    return SOUND_WORKER.build_result(
        execution=execution,
        output_asset_id=output_asset_id,
        output_uri=output_uri,
        completed=True,
        creative_integrity_preserved=True,
    )


def tests_ui() -> dict[str, Any]:
    return SOUND_WORKER.acceptance_test()


# =============================================================================
# UI
# =============================================================================

def build_app() -> gr.Blocks:

    example = json.dumps(
        example_work_order(),
        indent=2,
    )

    with gr.Blocks(
        title=(
            f"{BOT_NAME} v{APP_VERSION}"
        )
    ) as app:

        gr.Markdown(
            f"""
# {BOT_NAME}

**Roadmap Stage #11**

**Type:** Specialist Worker Bot  
**Reports to:** {REPORTS_TO}  
**Assistant:** {ASSISTANT_BOT}

Receives QC-approved Sound Department work orders from the
Post-Production Supervisor and prepares deterministic sound
execution without changing locked creative decisions.

### Sound Department Scope

- Dialogue editing and cleanup
- Ambience
- Foley
- Sound effects
- Audio synchronization
- Level preparation
- Mix preparation

### Authority Boundary

The Sound Worker Bot cannot:

- rewrite dialogue,
- replace character voice identity,
- change character or environment identity,
- reinterpret Director intent,
- reinterpret camera intent,
- reinterpret performance intent,
- rewrite the story,
- compose the musical score,
- silently alter approved creative decisions.

Music composition belongs to the separate
**J.O.A.T. Music Worker Bot**.
"""
        )

        with gr.Tab(
            "Sound Execution"
        ):

            work_order_raw = gr.Code(
                value=example,
                language="json",
                label=(
                    "Post-Production Sound Work Order"
                ),
            )

            execution_output = gr.JSON(
                label=(
                    "Sound Execution Packet"
                ),
            )

            gr.Button(
                "Build Sound Execution",
                variant="primary",
            ).click(
                fn=build_execution_ui,
                inputs=[
                    work_order_raw,
                ],
                outputs=[
                    execution_output,
                ],
            )

        with gr.Tab(
            "Sound Result"
        ):

            execution_raw = gr.Code(
                value="{}",
                language="json",
                label=(
                    "Sound Execution Packet"
                ),
            )

            output_asset_id = gr.Textbox(
                value="SOUND-RESULT-001",
                label="Output Asset ID",
            )

            output_uri = gr.Textbox(
                value=(
                    "asset://sound-result-001"
                ),
                label="Output Asset URI",
            )

            result_output = gr.JSON(
                label="Sound Result Packet",
            )

            gr.Button(
                "Build Sound Result",
                variant="primary",
            ).click(
                fn=build_result_ui,
                inputs=[
                    execution_raw,
                    output_asset_id,
                    output_uri,
                ],
                outputs=[
                    result_output,
                ],
            )

        with gr.Tab(
            "Acceptance Tests"
        ):

            test_output = gr.JSON(
                label=(
                    "Sound Worker Acceptance Test"
                ),
            )

            gr.Button(
                "Run Acceptance Tests",
                variant="primary",
            ).click(
                fn=tests_ui,
                inputs=None,
                outputs=test_output,
            )

        with gr.Tab(
            "Bot Contract"
        ):

            gr.JSON(
                value={
                    "bot_name":
                        BOT_NAME,
                    "bot_type":
                        BOT_TYPE,
                    "assistant_bot":
                        ASSISTANT_BOT,
                    "assistant_required":
                        ASSISTANT_REQUIRED,
                    "reports_to":
                        REPORTS_TO,
                    "department":
                        EXPECTED_DEPARTMENT,
                    "schemas": {
                        "work_order":
                            WORK_ORDER_SCHEMA,
                        "execution":
                            EXECUTION_SCHEMA,
                        "result":
                            RESULT_SCHEMA,
                    },
                    "responsibilities": [
                        "dialogue editing",
                        "dialogue cleanup",
                        "ambience",
                        "foley",
                        "sound effects",
                        "audio synchronization",
                        "level preparation",
                        "mix preparation",
                    ],
                    "prohibited": [
                        "music composition",
                        "dialogue rewriting",
                        "voice identity replacement",
                        "character identity mutation",
                        "environment identity mutation",
                        "Director reinterpretation",
                        "camera reinterpretation",
                        "performance reinterpretation",
                        "story rewriting",
                        "silent creative changes",
                    ],
                },
                label="Sound Worker Contract",
            )

        from joat_production_ui import add_specialist_ui, add_post_ui, add_delivery_ui, add_voice_ui, add_timeline_ui
        gr.Markdown(f"**Production integration version:** {APP_VERSION}")
        add_specialist_ui('sound')

    return app


if __name__ == "__main__":

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )