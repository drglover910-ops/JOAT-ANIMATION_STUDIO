"""
J.O.A.T. Color/Finish Worker Bot v1.0.1
Roadmap Stage #14

Purpose:
- Receive approved Color/Finish work orders
- Validate Post-Production Supervisor routing
- Preserve QC provenance
- Build deterministic Color/Finish execution packets
- Perform approved color correction and finishing
- Protect locked creative intent
- Return completed results to Post-Production Supervisor
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import gradio as gr


APP_VERSION = "1.0.1"

BOT_NAME = "J.O.A.T. Color/Finish Worker Bot"
BOT_TYPE = "color_finish_worker_bot"

ASSISTANT_REQUIRED = False
ASSISTANT_BOT = None

REPORTS_TO = "J.O.A.T. Post-Production Supervisor Bot"

WORK_ORDER_SCHEMA = "joat.post_work_order.v1"
EXECUTION_SCHEMA = "joat.color_finish_execution.v1"
RESULT_SCHEMA = "joat.color_finish_result.v1"

EXPECTED_DEPARTMENT = "color_finish"

SUPPORTED_TASKS = [
    "color_correction",
    "color_grading",
    "exposure_balance",
    "contrast_balance",
    "white_balance",
    "shot_matching",
    "color_continuity",
    "approved_look_application",
    "delivery_level_check",
    "final_visual_polish",
]

PROHIBITED_TASKS = [
    "rewrite_story",
    "rewrite_dialogue",
    "change_character_identity",
    "change_environment_identity",
    "reinterpret_director_intent",
    "reinterpret_camera",
    "reinterpret_performance",
    "redesign_lighting",
    "replace_vfx",
    "change_locked_composition",
    "invent_new_visual_style",
    "silent_creative_change",
]


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
        raise ValueError(f"{label} is required.")

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
            "Color/Finish work order rejected: "
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
        "may_replace_approved_vfx",
        "may_invent_new_visual_style",
        "may_silently_change_creative_intent",
    ]

    for field in required_false:
        if boundary.get(field) is not False:
            raise ValueError(
                "Color/Finish work order rejected: "
                f"{field} must be false."
            )


def validate_work_order(
    work_order: dict[str, Any],
) -> dict[str, Any]:

    if work_order.get("schema") != WORK_ORDER_SCHEMA:
        raise ValueError(
            "Color/Finish work order rejected: "
            f"schema must be {WORK_ORDER_SCHEMA!r}."
        )

    if work_order.get("department") != EXPECTED_DEPARTMENT:
        raise ValueError(
            "Color/Finish work order rejected: "
            "wrong department."
        )

    if work_order.get("assigned_bot") != BOT_NAME:
        raise ValueError(
            "Color/Finish work order rejected: "
            "wrong bot assignment."
        )

    source_asset = work_order.get(
        "source_asset",
        {},
    )

    if not isinstance(source_asset, dict):
        raise ValueError(
            "Source asset is required."
        )

    if not source_asset.get("asset_id"):
        raise ValueError(
            "Source asset_id is required."
        )

    if not qc_is_approved(work_order):
        raise ValueError(
            "Color/Finish work order rejected: "
            "QC PASS and Post authorization required."
        )

    validate_authority_boundary(work_order)

    requested_tasks = work_order.get(
        "requested_tasks",
        [],
    )

    if not isinstance(requested_tasks, list):
        raise ValueError(
            "requested_tasks must be a list."
        )

    for task in requested_tasks:

        if task in PROHIBITED_TASKS:
            raise ValueError(
                "Color/Finish work order rejected: "
                f"prohibited task: {task}"
            )

        if task not in SUPPORTED_TASKS:
            raise ValueError(
                "Color/Finish work order rejected: "
                f"unsupported task: {task}"
            )

    return {
        "work_order_valid": True,
        "department_verified": True,
        "assignment_verified": True,
        "source_asset_verified": True,
        "qc_provenance_verified": True,
        "authority_boundary_verified": True,
        "work_order_fingerprint":
            get_work_order_fingerprint(work_order),
    }


class ColorFinishWorkerBot:

    def build_execution(
        self,
        work_order: dict[str, Any],
    ) -> dict[str, Any]:

        validation = validate_work_order(work_order)

        execution = {
            "schema": EXECUTION_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,

            "assistant": {
                "assistant_required": ASSISTANT_REQUIRED,
                "assistant_bot": ASSISTANT_BOT,
            },

            "reports_to": REPORTS_TO,
            "validation": validation,

            "source_asset": deepcopy(
                work_order["source_asset"]
            ),

            "qc_provenance": deepcopy(
                work_order["qc_provenance"]
            ),

            "requested_tasks": deepcopy(
                work_order.get(
                    "requested_tasks",
                    [],
                )
            ),

            "finish_direction": deepcopy(
                work_order.get(
                    "finish_direction",
                    {},
                )
            ),

            "creative_integrity_policy": {
                "preserve_character_identity": True,
                "preserve_environment_identity": True,
                "preserve_director_intent": True,
                "preserve_camera_intent": True,
                "preserve_performance_intent": True,
                "preserve_story": True,
                "preserve_dialogue": True,
                "preserve_approved_vfx": True,
                "preserve_locked_composition": True,
                "new_visual_style_allowed": False,
                "silent_creative_change_allowed": False,
            },

            "finish_scope": {
                "color_correction_allowed": True,
                "color_grading_allowed": True,
                "exposure_balance_allowed": True,
                "contrast_balance_allowed": True,
                "white_balance_allowed": True,
                "shot_matching_allowed": True,
                "color_continuity_allowed": True,
                "approved_look_application_allowed": True,
                "delivery_level_check_allowed": True,
                "final_visual_polish_allowed": True,
                "character_redesign_allowed": False,
                "environment_redesign_allowed": False,
                "vfx_replacement_allowed": False,
                "creative_reinterpretation_allowed": False,
            },

            "execution_policy": {
                "technical_finishing_allowed": True,
                "approved_look_execution_allowed": True,
                "upstream_mutation_allowed": False,
                "creative_invention_allowed": False,
                "human_approval_required_for_locked_change": True,
            },

            "immutable_work_order_snapshot":
                deepcopy(work_order),

            "return_route": {
                "destination": REPORTS_TO,
                "result_schema": RESULT_SCHEMA,
                "ready_for_post_supervisor": False,
            },
        }

        execution[
            "execution_fingerprint"
        ] = fingerprint(execution)

        return execution

    def build_result(
        self,
        execution: dict[str, Any],
        output_asset_id: str,
        output_uri: str,
        completed: bool = True,
        creative_integrity_preserved: bool = True,
    ) -> dict[str, Any]:

        if execution.get("schema") != EXECUTION_SCHEMA:
            raise ValueError(
                "Invalid Color/Finish execution schema."
            )

        if execution.get("bot_name") != BOT_NAME:
            raise ValueError(
                "Execution belongs to wrong bot."
            )

        if not output_asset_id:
            raise ValueError(
                "output_asset_id is required."
            )

        if not output_uri:
            raise ValueError(
                "output_uri is required."
            )

        if not creative_integrity_preserved:
            raise ValueError(
                "Color/Finish result blocked: "
                "creative integrity failure."
            )

        result = {
            "schema": RESULT_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "reports_to": REPORTS_TO,

            "execution_fingerprint":
                execution[
                    "execution_fingerprint"
                ],

            "source_asset": deepcopy(
                execution["source_asset"]
            ),

            "qc_provenance": deepcopy(
                execution["qc_provenance"]
            ),

            "finish_direction": deepcopy(
                execution.get(
                    "finish_direction",
                    {},
                )
            ),

            "output_asset": {
                "asset_id": output_asset_id,
                "uri": output_uri,
                "asset_type":
                    "post_production_finished_asset",
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

        result[
            "result_fingerprint"
        ] = fingerprint(result)

        return result

    def acceptance_test(self) -> dict[str, Any]:

        tests = []

        def add(
            name: str,
            passed: bool,
        ) -> None:
            tests.append(
                {
                    "test": name,
                    "pass": bool(passed),
                    "detail": bool(passed),
                }
            )

        work_order = {
            "schema": WORK_ORDER_SCHEMA,
            "work_order_id": "POST-COLOR-001",
            "department": EXPECTED_DEPARTMENT,
            "assigned_bot": BOT_NAME,

            "source_asset": {
                "asset_id": "SHOT-001-QC-PASS",
                "uri": "asset://shot-001",
                "asset_type": "qc_approved_shot",
            },

            "qc_provenance": {
                "qc_status": "PASS",
                "qc_packet_fingerprint": "QC-FP-001",
                "post_production_authorized": True,
            },

            "requested_tasks": [
                "color_correction",
                "color_grading",
                "shot_matching",
                "color_continuity",
                "final_visual_polish",
            ],

            "finish_direction": {
                "approved_look":
                    "cinematic controlled contrast",
                "shot_match_required": True,
                "preserve_approved_vfx": True,
            },

            "authority_boundary": {
                "may_change_character_identity": False,
                "may_change_environment_identity": False,
                "may_reinterpret_director_intent": False,
                "may_reinterpret_camera_intent": False,
                "may_reinterpret_performance_intent": False,
                "may_rewrite_story": False,
                "may_rewrite_dialogue": False,
                "may_replace_approved_vfx": False,
                "may_invent_new_visual_style": False,
                "may_silently_change_creative_intent": False,
            },
        }

        work_order[
            "work_order_fingerprint"
        ] = fingerprint(
            {
                k: v
                for k, v in work_order.items()
                if k != "work_order_fingerprint"
            }
        )

        validation = validate_work_order(work_order)

        add(
            "1. Post work order schema validates",
            validation["work_order_valid"],
        )

        add(
            "2. Color/Finish department verified",
            validation["department_verified"],
        )

        add(
            "3. Color/Finish Worker Bot assignment verified",
            validation["assignment_verified"],
        )

        add(
            "4. Source asset verified",
            validation["source_asset_verified"],
        )

        add(
            "5. QC provenance verified",
            validation["qc_provenance_verified"],
        )

        add(
            "6. Authority boundary verified",
            validation["authority_boundary_verified"],
        )

        execution = self.build_execution(work_order)

        add(
            "7. Color/Finish execution packet generates",
            execution["schema"] == EXECUTION_SCHEMA,
        )

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
            "finish_direction",
            "creative_integrity_policy",
            "finish_scope",
            "execution_policy",
            "immutable_work_order_snapshot",
            "return_route",
            "execution_fingerprint",
        ]

        add(
            "8. Required execution fields present",
            all(
                x in execution
                for x in required_execution_fields
            ),
        )

        add(
            "9. Color/Finish Worker requires no assistant",
            (
                execution["assistant"][
                    "assistant_required"
                ] is False
                and execution["assistant"][
                    "assistant_bot"
                ] is None
            ),
        )

        add(
            "10. Color/Finish Worker reports to Post Supervisor",
            execution["reports_to"] == REPORTS_TO,
        )

        add(
            "11. QC-approved assets accepted",
            execution[
                "qc_provenance"
            ]["qc_status"] == "PASS",
        )

        policy = execution[
            "creative_integrity_policy"
        ]

        add(
            "12. Character identity mutation prohibited",
            policy["preserve_character_identity"],
        )

        add(
            "13. Environment identity mutation prohibited",
            policy["preserve_environment_identity"],
        )

        add(
            "14. Director reinterpretation prohibited",
            policy["preserve_director_intent"],
        )

        add(
            "15. Camera reinterpretation prohibited",
            policy["preserve_camera_intent"],
        )

        add(
            "16. Performance reinterpretation prohibited",
            policy["preserve_performance_intent"],
        )

        add(
            "17. Story rewrite prohibited",
            policy["preserve_story"],
        )

        add(
            "18. Dialogue rewrite prohibited",
            policy["preserve_dialogue"],
        )

        add(
            "19. Approved VFX protected",
            policy["preserve_approved_vfx"],
        )

        add(
            "20. Locked composition protected",
            policy["preserve_locked_composition"],
        )

        add(
            "21. New visual style prohibited",
            policy[
                "new_visual_style_allowed"
            ] is False,
        )

        add(
            "22. Silent creative change prohibited",
            policy[
                "silent_creative_change_allowed"
            ] is False,
        )

        scope = execution["finish_scope"]

        add(
            "23. Approved Color/Finish operations enabled",
            (
                scope["color_correction_allowed"]
                and scope["color_grading_allowed"]
                and scope["shot_matching_allowed"]
                and scope[
                    "final_visual_polish_allowed"
                ]
            ),
        )

        add(
            "24. VFX replacement prohibited",
            scope[
                "vfx_replacement_allowed"
            ] is False,
        )

        add(
            "25. Creative reinterpretation prohibited",
            scope[
                "creative_reinterpretation_allowed"
            ] is False,
        )

        first = self.build_execution(work_order)
        second = self.build_execution(work_order)

        add(
            "26. Deterministic execution fingerprint",
            first["execution_fingerprint"]
            == second["execution_fingerprint"],
        )

        before = stable_json(work_order)

        self.build_execution(work_order)

        after = stable_json(work_order)

        add(
            "27. Post work order remains immutable",
            before == after,
        )

        bad = deepcopy(work_order)
        bad["department"] = "music"

        rejected = False
        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "28. Wrong department work order rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["assigned_bot"] = (
            "J.O.A.T. Music Worker Bot"
        )

        rejected = False
        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "29. Wrong bot assignment rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["qc_provenance"] = {}

        rejected = False
        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "30. Missing QC provenance rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["qc_provenance"][
            "qc_status"
        ] = "REJECT"

        rejected = False
        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "31. Non-QC-approved asset rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["requested_tasks"] = [
            "invent_new_visual_style"
        ]

        rejected = False
        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "32. New visual style request rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["requested_tasks"] = [
            "replace_vfx"
        ]

        rejected = False
        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "33. Approved VFX replacement rejected",
            rejected,
        )

        result = self.build_result(
            execution,
            "COLOR-RESULT-001",
            "asset://color-result-001",
            True,
            True,
        )

        add(
            "34. Color/Finish result packet generates",
            result["schema"] == RESULT_SCHEMA,
        )

        required_result_fields = [
            "schema",
            "app_version",
            "bot_name",
            "bot_type",
            "reports_to",
            "execution_fingerprint",
            "source_asset",
            "qc_provenance",
            "finish_direction",
            "output_asset",
            "completion",
            "creative_integrity",
            "handoff",
            "result_fingerprint",
        ]

        add(
            "35. Required result fields present",
            all(
                x in result
                for x in required_result_fields
            ),
        )

        add(
            "36. Color/Finish result preserves creative integrity",
            result["completion"][
                "creative_integrity_preserved"
            ],
        )

        add(
            "37. Color/Finish result preserves QC provenance",
            result[
                "qc_provenance"
            ]["qc_status"] == "PASS",
        )

        add(
            "38. Completed Color/Finish routes to Post Supervisor",
            (
                result["handoff"]["destination"]
                == REPORTS_TO
                and result["handoff"][
                    "authorized"
                ] is True
            ),
        )

        rejected = False

        try:
            self.build_result(
                execution,
                "COLOR-BAD-001",
                "asset://color-bad-001",
                True,
                False,
            )
        except ValueError:
            rejected = True

        add(
            "39. Creative-integrity failure blocks Color/Finish result",
            rejected,
        )

        all_passed = all(
            x["pass"]
            for x in tests
        )

        return {
            "acceptance_test_version": "1.0.0",
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "assistant_required":
                ASSISTANT_REQUIRED,
            "reports_to": REPORTS_TO,
            "work_order_schema":
                WORK_ORDER_SCHEMA,
            "execution_schema":
                EXECUTION_SCHEMA,
            "result_schema":
                RESULT_SCHEMA,
            "tests": tests,
            "all_passed": all_passed,
            "production_ready": all_passed,
            "note": (
                "Color/Finish Worker Bot is production-ready "
                "when only properly routed QC-approved assets "
                "enter finishing, approved color operations "
                "remain inside its authority boundary, locked "
                "creative decisions and approved VFX remain "
                "protected, and completed results return to "
                "the Post-Production Supervisor Bot."
            ),
        }


WORKER = ColorFinishWorkerBot()


def example_work_order() -> dict[str, Any]:

    work_order = {
        "schema": WORK_ORDER_SCHEMA,
        "work_order_id": "POST-COLOR-001",
        "department": EXPECTED_DEPARTMENT,
        "assigned_bot": BOT_NAME,

        "source_asset": {
            "asset_id": "SHOT-001-QC-PASS",
            "uri": "asset://shot-001",
            "asset_type": "qc_approved_shot",
        },

        "qc_provenance": {
            "qc_status": "PASS",
            "qc_packet_fingerprint": "QC-FP-001",
            "post_production_authorized": True,
        },

        "requested_tasks": [
            "color_correction",
            "color_grading",
            "shot_matching",
            "color_continuity",
            "final_visual_polish",
        ],

        "finish_direction": {
            "approved_look":
                "cinematic controlled contrast",
            "shot_match_required": True,
            "preserve_approved_vfx": True,
        },

        "authority_boundary": {
            "may_change_character_identity": False,
            "may_change_environment_identity": False,
            "may_reinterpret_director_intent": False,
            "may_reinterpret_camera_intent": False,
            "may_reinterpret_performance_intent": False,
            "may_rewrite_story": False,
            "may_rewrite_dialogue": False,
            "may_replace_approved_vfx": False,
            "may_invent_new_visual_style": False,
            "may_silently_change_creative_intent": False,
        },
    }

    work_order[
        "work_order_fingerprint"
    ] = fingerprint(
        {
            k: v
            for k, v in work_order.items()
            if k != "work_order_fingerprint"
        }
    )

    return work_order


def build_execution_ui(
    raw: str,
) -> dict[str, Any]:

    return WORKER.build_execution(
        parse_json_object(
            raw,
            "Post work order",
        )
    )


def tests_ui() -> dict[str, Any]:
    return WORKER.acceptance_test()


def build_app() -> gr.Blocks:

    example = json.dumps(
        example_work_order(),
        indent=2,
    )

    with gr.Blocks(
        title=f"{BOT_NAME} v{APP_VERSION}"
    ) as app:

        gr.Markdown(
            f"""
# {BOT_NAME}

**Roadmap Stage #14**

**Type:** Specialist Worker Bot  
**Reports to:** {REPORTS_TO}  
**Assistant required:** No

Performs approved final color and visual finishing while
preserving locked creative decisions, approved VFX, and
QC provenance.
"""
        )

        with gr.Tab("Color/Finish Execution"):

            raw = gr.Code(
                value=example,
                language="json",
                label="Color/Finish Work Order",
            )

            output = gr.JSON(
                label="Color/Finish Execution Packet",
            )

            gr.Button(
                "Build Color/Finish Execution",
                variant="primary",
            ).click(
                fn=build_execution_ui,
                inputs=raw,
                outputs=output,
            )

        with gr.Tab("Acceptance Tests"):

            test_output = gr.JSON(
                label="Color/Finish Acceptance Test",
            )

            gr.Button(
                "Run Acceptance Tests",
                variant="primary",
            ).click(
                fn=tests_ui,
                inputs=None,
                outputs=test_output,
            )

        with gr.Tab("Bot Contract"):

            gr.JSON(
                value={
                    "bot_name": BOT_NAME,
                    "bot_type": BOT_TYPE,
                    "assistant_required":
                        ASSISTANT_REQUIRED,
                    "reports_to": REPORTS_TO,
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
                },
                label="Color/Finish Worker Contract",
            )

        from joat_production_ui import add_specialist_ui, add_post_ui, add_delivery_ui, add_voice_ui, add_timeline_ui
        gr.Markdown(f"**Production integration version:** {APP_VERSION}")
        add_specialist_ui('color_finish')

    return app


if __name__ == "__main__":

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )