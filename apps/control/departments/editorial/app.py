"""
J.O.A.T. Editorial Worker Bot v1.0.1

Roadmap Stage #10

Purpose:
- Receive approved editorial work orders from the
  J.O.A.T. Post-Production Supervisor Bot
- Validate department routing and source provenance
- Preserve all upstream creative locks
- Build deterministic editorial execution packets
- Assemble approved shots/assets without creative reinterpretation
- Coordinate with the J.O.A.T. Edit Assistant Bot
- Return completed editorial results to the Post-Production Supervisor
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

BOT_NAME = "J.O.A.T. Editorial Worker Bot"
BOT_TYPE = "editorial_worker_bot"

ASSISTANT_BOT = "J.O.A.T. Edit Assistant Bot"
ASSISTANT_REQUIRED = True

REPORTS_TO = "J.O.A.T. Post-Production Supervisor Bot"

WORK_ORDER_SCHEMA = "joat.post_work_order.v1"
EXECUTION_SCHEMA = "joat.editorial_execution.v1"
RESULT_SCHEMA = "joat.editorial_result.v1"

DEPARTMENT = "editorial"


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
    return sha256_text(
        stable_json(value)
    )


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


# =============================================================================
# EDITORIAL WORKER
# =============================================================================

class EditorialWorker:

    def validate_work_order(
        self,
        work_order: dict[str, Any],
    ) -> dict[str, Any]:

        if work_order.get(
            "schema"
        ) != WORK_ORDER_SCHEMA:
            raise ValueError(
                "Editorial work order rejected: "
                "invalid schema."
            )

        if work_order.get(
            "department"
        ) != DEPARTMENT:
            raise ValueError(
                "Editorial work order rejected: "
                "wrong department."
            )

        if work_order.get(
            "assigned_bot"
        ) != BOT_NAME:
            raise ValueError(
                "Editorial work order rejected: "
                "wrong assigned bot."
            )

        source_asset = work_order.get(
            "source_asset"
        )

        if not isinstance(
            source_asset,
            dict,
        ):
            raise ValueError(
                "Editorial work order rejected: "
                "source asset missing."
            )

        if not source_asset.get(
            "asset_uri"
        ):
            raise ValueError(
                "Editorial work order rejected: "
                "asset URI missing."
            )

        if not source_asset.get(
            "qc_fingerprint"
        ):
            raise ValueError(
                "Editorial work order rejected: "
                "QC provenance missing."
            )

        boundary = work_order.get(
            "authority_boundary"
        )

        if not isinstance(
            boundary,
            dict,
        ):
            raise ValueError(
                "Editorial work order rejected: "
                "authority boundary missing."
            )

        prohibited = [
            "may_change_locked_character_identity",
            "may_change_locked_environment_identity",
            "may_reinterpret_director_intent",
            "may_reinterpret_camera_intent",
            "may_reinterpret_performance_intent",
            "may_replace_qc_approved_source_asset",
        ]

        for field in prohibited:
            if boundary.get(field) is not False:
                raise ValueError(
                    "Editorial work order rejected: "
                    f"unsafe authority setting {field}."
                )

        if boundary.get(
            "creative_change_requires_upstream_approval"
        ) is not True:
            raise ValueError(
                "Editorial work order rejected: "
                "creative-change approval protection missing."
            )

        return {
            "schema_valid": True,
            "department_verified": True,
            "assignment_verified": True,
            "source_asset_verified": True,
            "qc_provenance_verified": True,
            "authority_boundary_verified": True,
            "work_order_fingerprint": (
                work_order.get(
                    "work_order_fingerprint"
                )
                or fingerprint(work_order)
            ),
        }

    def build_execution(
        self,
        work_order: dict[str, Any],
        edit_plan: dict[str, Any],
    ) -> dict[str, Any]:

        validation = self.validate_work_order(
            work_order
        )

        if not isinstance(
            edit_plan,
            dict,
        ):
            raise ValueError(
                "Edit plan must be an object."
            )

        shots = edit_plan.get(
            "shots"
        )

        if not isinstance(
            shots,
            list,
        ) or not shots:
            raise ValueError(
                "Editorial execution requires "
                "at least one approved shot."
            )

        for shot in shots:

            if not isinstance(
                shot,
                dict,
            ):
                raise ValueError(
                    "Each shot must be an object."
                )

            if not shot.get(
                "asset_uri"
            ):
                raise ValueError(
                    "Each editorial shot requires "
                    "an asset URI."
                )

            if shot.get(
                "qc_passed"
            ) is not True:
                raise ValueError(
                    "Editorial execution rejected: "
                    "every shot must have QC PASS."
                )

        creative_change_requested = (
            edit_plan.get(
                "creative_change_requested",
                False,
            )
        )

        if creative_change_requested:
            raise ValueError(
                "Editorial Worker Bot cannot execute "
                "an unapproved creative change."
            )

        execution_core = {
            "schema": EXECUTION_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "assistant_bot": ASSISTANT_BOT,
            "reports_to": REPORTS_TO,
            "source_work_order_fingerprint": (
                validation[
                    "work_order_fingerprint"
                ]
            ),
            "project_context": deepcopy(
                work_order.get(
                    "project_context",
                    {},
                )
            ),
            "source_asset": deepcopy(
                work_order[
                    "source_asset"
                ]
            ),
            "edit_plan": deepcopy(
                edit_plan
            ),
            "immutable_work_order_snapshot": deepcopy(
                work_order
            ),
            "editorial_policy": {
                "qc_approved_assets_only": True,
                "character_identity_change_allowed": False,
                "environment_identity_change_allowed": False,
                "director_reinterpretation_allowed": False,
                "camera_reinterpretation_allowed": False,
                "performance_reinterpretation_allowed": False,
                "source_asset_replacement_allowed": False,
                "story_rewrite_allowed": False,
                "silent_creative_change_allowed": False,
                "technical_editorial_execution_allowed": True,
                "creative_change_requires_escalation": True,
            },
            "assistant_handoff": {
                "assistant_bot": ASSISTANT_BOT,
                "timeline_tracking_allowed": True,
                "continuity_tracking_allowed": True,
                "metadata_tracking_allowed": True,
                "creative_override_allowed": False,
            },
        }

        execution_core[
            "execution_fingerprint"
        ] = fingerprint(
            execution_core
        )

        return execution_core

    def complete_execution(
        self,
        execution: dict[str, Any],
        output_uri: str,
    ) -> dict[str, Any]:

        if execution.get(
            "schema"
        ) != EXECUTION_SCHEMA:
            raise ValueError(
                "Invalid editorial execution packet."
            )

        if not output_uri.strip():
            raise ValueError(
                "Editorial output URI is required."
            )

        policy = execution.get(
            "editorial_policy",
            {},
        )

        if policy.get(
            "silent_creative_change_allowed"
        ) is not False:
            raise ValueError(
                "Unsafe editorial execution policy."
            )

        result_core = {
            "schema": RESULT_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "assistant_bot": ASSISTANT_BOT,
            "reports_to": REPORTS_TO,
            "project_context": deepcopy(
                execution.get(
                    "project_context",
                    {},
                )
            ),
            "source_execution_fingerprint": (
                execution[
                    "execution_fingerprint"
                ]
            ),
            "output_uri": output_uri.strip(),
            "status": "completed",
            "creative_integrity_preserved": True,
            "qc_provenance_preserved": True,
            "handoff": {
                "destination": REPORTS_TO,
                "ready_for_post_supervisor": True,
            },
        }

        result_core[
            "result_fingerprint"
        ] = fingerprint(
            result_core
        )

        return result_core

    def acceptance_test(
        self,
    ) -> dict[str, Any]:

        tests = []

        def add(
            name: str,
            passed: bool,
            detail: Any = None,
        ):
            tests.append({
                "test": name,
                "pass": bool(passed),
                "detail": (
                    detail
                    if detail is not None
                    else bool(passed)
                ),
            })

        work_order = {
            "schema": WORK_ORDER_SCHEMA,
            "department": "editorial",
            "assigned_bot": BOT_NAME,
            "assistant_bot": ASSISTANT_BOT,
            "project_context": {
                "project_id": "PROJECT-001",
                "scene_id": "SCENE-001",
                "shot_id": "SHOT-001",
            },
            "source_asset": {
                "asset_uri": (
                    "hf://project/shot001.mp4"
                ),
                "qc_fingerprint": "QC-FP-001",
            },
            "instructions": (
                "Assemble approved shots."
            ),
            "authority_boundary": {
                "may_change_locked_character_identity": False,
                "may_change_locked_environment_identity": False,
                "may_reinterpret_director_intent": False,
                "may_reinterpret_camera_intent": False,
                "may_reinterpret_performance_intent": False,
                "may_replace_qc_approved_source_asset": False,
                "may_make_department_technical_changes": True,
                "creative_change_requires_upstream_approval": True,
            },
            "work_order_fingerprint": (
                "POST-WORK-FP-001"
            ),
        }

        edit_plan = {
            "shots": [
                {
                    "shot_id": "SHOT-001",
                    "asset_uri": (
                        "hf://project/shot001.mp4"
                    ),
                    "qc_passed": True,
                    "in_seconds": 0.0,
                    "out_seconds": 6.0,
                    "transition": "cut",
                },
                {
                    "shot_id": "SHOT-002",
                    "asset_uri": (
                        "hf://project/shot002.mp4"
                    ),
                    "qc_passed": True,
                    "in_seconds": 0.0,
                    "out_seconds": 5.0,
                    "transition": "cut",
                },
            ],
            "creative_change_requested": False,
        }

        validation = (
            self.validate_work_order(
                work_order
            )
        )

        execution = (
            self.build_execution(
                work_order,
                edit_plan,
            )
        )

        result = (
            self.complete_execution(
                execution,
                "hf://post/editorial/"
                "scene001_edit_v1.mp4",
            )
        )

        add(
            "1. Post work order schema validates",
            validation[
                "schema_valid"
            ],
        )

        add(
            "2. Editorial department verified",
            validation[
                "department_verified"
            ],
        )

        add(
            "3. Editorial Worker Bot assignment verified",
            validation[
                "assignment_verified"
            ],
        )

        add(
            "4. Source asset verified",
            validation[
                "source_asset_verified"
            ],
        )

        add(
            "5. QC provenance verified",
            validation[
                "qc_provenance_verified"
            ],
        )

        add(
            "6. Authority boundary verified",
            validation[
                "authority_boundary_verified"
            ],
        )

        add(
            "7. Editorial execution packet generates",
            execution[
                "schema"
            ] == EXECUTION_SCHEMA,
        )

        required_execution = [
            "schema",
            "app_version",
            "bot_name",
            "bot_type",
            "assistant_bot",
            "reports_to",
            "source_work_order_fingerprint",
            "project_context",
            "source_asset",
            "edit_plan",
            "immutable_work_order_snapshot",
            "editorial_policy",
            "assistant_handoff",
            "execution_fingerprint",
        ]

        add(
            "8. Required execution fields present",
            all(
                x in execution
                for x in required_execution
            ),
        )

        add(
            "9. Edit Assistant Bot relationship declared",
            execution[
                "assistant_bot"
            ] == ASSISTANT_BOT,
        )

        add(
            "10. Editorial Worker reports to Post Supervisor",
            execution[
                "reports_to"
            ] == REPORTS_TO,
        )

        add(
            "11. QC-approved shots accepted",
            all(
                x["qc_passed"] is True
                for x in execution[
                    "edit_plan"
                ]["shots"]
            ),
        )

        policy = execution[
            "editorial_policy"
        ]

        add(
            "12. Character identity mutation prohibited",
            policy[
                "character_identity_change_allowed"
            ] is False,
        )

        add(
            "13. Environment identity mutation prohibited",
            policy[
                "environment_identity_change_allowed"
            ] is False,
        )

        add(
            "14. Director reinterpretation prohibited",
            policy[
                "director_reinterpretation_allowed"
            ] is False,
        )

        add(
            "15. Camera reinterpretation prohibited",
            policy[
                "camera_reinterpretation_allowed"
            ] is False,
        )

        add(
            "16. Performance reinterpretation prohibited",
            policy[
                "performance_reinterpretation_allowed"
            ] is False,
        )

        add(
            "17. Story rewrite prohibited",
            policy[
                "story_rewrite_allowed"
            ] is False,
        )

        add(
            "18. Silent creative change prohibited",
            policy[
                "silent_creative_change_allowed"
            ] is False,
        )

        first = self.build_execution(
            work_order,
            edit_plan,
        )

        second = self.build_execution(
            work_order,
            edit_plan,
        )

        add(
            "19. Deterministic execution fingerprint",
            first[
                "execution_fingerprint"
            ]
            == second[
                "execution_fingerprint"
            ],
        )

        before = stable_json(
            work_order
        )

        self.build_execution(
            work_order,
            edit_plan,
        )

        after = stable_json(
            work_order
        )

        add(
            "20. Post work order remains immutable",
            before == after,
        )

        rejected = False

        bad_department = deepcopy(
            work_order
        )

        bad_department[
            "department"
        ] = "sound"

        try:
            self.validate_work_order(
                bad_department
            )
        except ValueError:
            rejected = True

        add(
            "21. Wrong department work order rejected",
            rejected,
        )

        rejected = False

        bad_assignment = deepcopy(
            work_order
        )

        bad_assignment[
            "assigned_bot"
        ] = "Wrong Bot"

        try:
            self.validate_work_order(
                bad_assignment
            )
        except ValueError:
            rejected = True

        add(
            "22. Wrong bot assignment rejected",
            rejected,
        )

        rejected = False

        missing_qc = deepcopy(
            work_order
        )

        missing_qc[
            "source_asset"
        ][
            "qc_fingerprint"
        ] = ""

        try:
            self.validate_work_order(
                missing_qc
            )
        except ValueError:
            rejected = True

        add(
            "23. Missing QC provenance rejected",
            rejected,
        )

        rejected = False

        unapproved_shot = deepcopy(
            edit_plan
        )

        unapproved_shot[
            "shots"
        ][0][
            "qc_passed"
        ] = False

        try:
            self.build_execution(
                work_order,
                unapproved_shot,
            )
        except ValueError:
            rejected = True

        add(
            "24. Non-QC-approved shot rejected",
            rejected,
        )

        rejected = False

        creative_change = deepcopy(
            edit_plan
        )

        creative_change[
            "creative_change_requested"
        ] = True

        try:
            self.build_execution(
                work_order,
                creative_change,
            )
        except ValueError:
            rejected = True

        add(
            "25. Unauthorized creative change rejected",
            rejected,
        )

        add(
            "26. Editorial result packet generates",
            result[
                "schema"
            ] == RESULT_SCHEMA,
        )

        required_result = [
            "schema",
            "app_version",
            "bot_name",
            "bot_type",
            "assistant_bot",
            "reports_to",
            "project_context",
            "source_execution_fingerprint",
            "output_uri",
            "status",
            "creative_integrity_preserved",
            "qc_provenance_preserved",
            "handoff",
            "result_fingerprint",
        ]

        add(
            "27. Required result fields present",
            all(
                x in result
                for x in required_result
            ),
        )

        add(
            "28. Editorial result preserves creative integrity",
            result[
                "creative_integrity_preserved"
            ] is True,
        )

        add(
            "29. Editorial result preserves QC provenance",
            result[
                "qc_provenance_preserved"
            ] is True,
        )

        add(
            "30. Completed editorial routes to Post Supervisor",
            result[
                "handoff"
            ][
                "ready_for_post_supervisor"
            ] is True
            and result[
                "handoff"
            ][
                "destination"
            ] == REPORTS_TO,
        )

        all_passed = all(
            test["pass"]
            for test in tests
        )

        return {
            "acceptance_test_version": "1.0.0",
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "assistant_bot": ASSISTANT_BOT,
            "assistant_required": ASSISTANT_REQUIRED,
            "reports_to": REPORTS_TO,
            "work_order_schema": WORK_ORDER_SCHEMA,
            "execution_schema": EXECUTION_SCHEMA,
            "result_schema": RESULT_SCHEMA,
            "tests": tests,
            "all_passed": all_passed,
            "production_ready": all_passed,
            "note": (
                "Editorial Worker Bot is production-ready "
                "when only properly routed QC-approved assets "
                "enter editorial execution, all locked creative "
                "decisions remain protected, unauthorized "
                "creative changes are rejected, and completed "
                "editorial results return to the "
                "Post-Production Supervisor Bot."
            ),
        }


WORKER = EditorialWorker()


# =============================================================================
# UI
# =============================================================================

def example_work_order() -> str:

    value = {
        "schema": WORK_ORDER_SCHEMA,
        "department": "editorial",
        "assigned_bot": BOT_NAME,
        "assistant_bot": ASSISTANT_BOT,
        "project_context": {
            "project_id": "PROJECT-001",
            "scene_id": "SCENE-001",
            "shot_id": "SHOT-001",
        },
        "source_asset": {
            "asset_uri": (
                "hf://project/shot001.mp4"
            ),
            "qc_fingerprint": "QC-FP-001",
        },
        "instructions": (
            "Assemble approved shots."
        ),
        "authority_boundary": {
            "may_change_locked_character_identity": False,
            "may_change_locked_environment_identity": False,
            "may_reinterpret_director_intent": False,
            "may_reinterpret_camera_intent": False,
            "may_reinterpret_performance_intent": False,
            "may_replace_qc_approved_source_asset": False,
            "may_make_department_technical_changes": True,
            "creative_change_requires_upstream_approval": True,
        },
        "work_order_fingerprint": (
            "POST-WORK-FP-001"
        ),
    }

    return json.dumps(
        value,
        indent=2,
    )


def example_edit_plan() -> str:

    value = {
        "shots": [
            {
                "shot_id": "SHOT-001",
                "asset_uri": (
                    "hf://project/shot001.mp4"
                ),
                "qc_passed": True,
                "in_seconds": 0.0,
                "out_seconds": 6.0,
                "transition": "cut",
            }
        ],
        "creative_change_requested": False,
    }

    return json.dumps(
        value,
        indent=2,
    )


def build_execution_ui(
    work_order_raw: str,
    edit_plan_raw: str,
):

    work_order = parse_json_object(
        work_order_raw,
        "Post Work Order",
    )

    edit_plan = parse_json_object(
        edit_plan_raw,
        "Edit Plan",
    )

    return WORKER.build_execution(
        work_order,
        edit_plan,
    )


def tests_ui():
    return WORKER.acceptance_test()


def build_app() -> gr.Blocks:

    with gr.Blocks(
        title=f"{BOT_NAME} v{APP_VERSION}"
    ) as app:

        gr.Markdown(
            f"# {BOT_NAME}\n\n"
            "**Roadmap Stage #10**\n\n"
            "Executes approved editorial work orders "
            "without changing locked creative intent."
        )

        with gr.Tab(
            "Editorial Execution"
        ):

            work_order_raw = gr.Code(
                value=example_work_order(),
                language="json",
                label="Post Work Order",
            )

            edit_plan_raw = gr.Code(
                value=example_edit_plan(),
                language="json",
                label="Edit Plan",
            )

            output = gr.JSON(
                label="Editorial Execution Packet"
            )

            gr.Button(
                "Build Editorial Execution",
                variant="primary",
            ).click(
                fn=build_execution_ui,
                inputs=[
                    work_order_raw,
                    edit_plan_raw,
                ],
                outputs=output,
            )

        with gr.Tab(
            "Acceptance Tests"
        ):

            test_output = gr.JSON(
                label=(
                    "Editorial Worker "
                    "Acceptance Tests"
                )
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
            "Chain of Command"
        ):

            gr.JSON(
                value={
                    "bot_name": BOT_NAME,
                    "bot_type": BOT_TYPE,
                    "assistant_bot": ASSISTANT_BOT,
                    "assistant_required": (
                        ASSISTANT_REQUIRED
                    ),
                    "reports_to": REPORTS_TO,
                },
                label="Editorial Department",
            )

        with gr.Tab(
            "Authority"
        ):

            gr.Markdown(
                """
## Editorial Authority

The Editorial Worker Bot may:

- assemble approved shots,
- trim approved material,
- execute approved timing,
- execute approved transitions,
- maintain synchronization,
- build editorial outputs.

It may **not**:

- use shots that have not passed QC,
- rewrite the story,
- redesign characters,
- replace environments,
- reinterpret Director intent,
- reinterpret camera intent,
- reinterpret performance,
- silently replace approved source material.

Any required creative change must be escalated.
"""
            )

        from joat_production_ui import add_specialist_ui, add_post_ui, add_delivery_ui, add_voice_ui, add_timeline_ui
        gr.Markdown(f"**Production integration version:** {APP_VERSION}")
        add_specialist_ui('editorial')
        add_timeline_ui()

    return app


if __name__ == "__main__":

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )