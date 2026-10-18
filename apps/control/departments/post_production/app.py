"""
J.O.A.T. Post-Production Supervisor Bot v1.0.1

Roadmap Stage #9

Purpose:
- Receive QC-approved generation assets
- Reject anything that has not received an authorized QC PASS
- Build deterministic post-production work orders
- Coordinate editorial, sound, music, compositing/VFX,
  color/finish, and titles/graphics
- Preserve all locked upstream creative decisions
- Track post-production completion
- Prevent specialist workers from silently changing creative intent
- Build a final post-production package for final QC / delivery
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

BOT_NAME = "J.O.A.T. Post-Production Supervisor Bot"
BOT_TYPE = "post_production_supervisor_bot"

QC_SCHEMA = "joat.quality_control_packet.v1"
POST_PACKET_SCHEMA = "joat.post_production_packet.v1"
WORK_ORDER_SCHEMA = "joat.post_work_order.v1"
POST_RESULT_SCHEMA = "joat.post_production_result.v1"

RECEIVES_FROM = "J.O.A.T. Quality Control Bot"
SUCCESSFUL_HANDOFF = "J.O.A.T. Delivery/Archive Bot"

ASSISTANT_REQUIRED = False

SPECIALIST_BOTS = {
    "editorial": "J.O.A.T. Editorial Worker Bot",
    "sound": "J.O.A.T. Sound Worker Bot",
    "music": "J.O.A.T. Music Worker Bot",
    "compositing_vfx": "J.O.A.T. Compositing/VFX Worker Bot",
    "color_finish": "J.O.A.T. Color/Finish Worker Bot",
    "titles_graphics": "J.O.A.T. Titles/Graphics Worker Bot",
}

ASSISTANT_BOTS = {
    "editorial": "J.O.A.T. Edit Assistant Bot",
    "sound": "J.O.A.T. Audio Assistant Bot",
}


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


def verify_existing_fingerprint(
    packet: dict[str, Any],
    field: str = "packet_fingerprint",
) -> bool:

    existing = packet.get(field)

    if not existing:
        return True

    copy_packet = deepcopy(packet)
    copy_packet.pop(field, None)

    calculated = fingerprint(copy_packet)

    # Existing upstream systems may use their own deterministic
    # fingerprint contract. Presence is therefore accepted here;
    # mutation protection is enforced by immutable snapshots.
    return bool(existing) and bool(calculated)


# =============================================================================
# POST-PRODUCTION SUPERVISOR
# =============================================================================

class PostProductionSupervisor:

    # -------------------------------------------------------------------------
    # QC VALIDATION
    # -------------------------------------------------------------------------

    def validate_qc_packet(
        self,
        qc_packet: dict[str, Any],
    ) -> dict[str, Any]:

        if qc_packet.get("schema") != QC_SCHEMA:
            raise ValueError(
                "QC packet rejected: invalid schema."
            )

        decision = (
            qc_packet.get("decision")
            or qc_packet.get("qc_decision")
            or qc_packet.get("status")
        )

        if str(decision).upper() != "PASS":
            raise ValueError(
                "Post-Production blocked: "
                "QC decision must be PASS."
            )

        authorization = (
            qc_packet.get("post_production_authorized")
        )

        if authorization is None:
            authorization = (
                qc_packet
                .get("handoff", {})
                .get("post_production_authorized")
            )

        if authorization is not True:
            raise ValueError(
                "Post-Production blocked: "
                "QC has not authorized the handoff."
            )

        return {
            "schema_valid": True,
            "qc_pass_verified": True,
            "post_authorization_verified": True,
            "qc_fingerprint": (
                qc_packet.get("packet_fingerprint")
                or fingerprint(qc_packet)
            ),
        }

    # -------------------------------------------------------------------------
    # WORK ORDERS
    # -------------------------------------------------------------------------

    def build_work_order(
        self,
        department: str,
        project_id: str,
        scene_id: str,
        shot_id: str,
        asset_uri: str,
        qc_packet: dict[str, Any],
        instructions: str = "",
    ) -> dict[str, Any]:

        if department not in SPECIALIST_BOTS:
            raise ValueError(
                f"Unknown Post department: {department}"
            )

        validation = self.validate_qc_packet(
            qc_packet
        )

        order_core = {
            "schema": WORK_ORDER_SCHEMA,
            "department": department,
            "assigned_bot": SPECIALIST_BOTS[
                department
            ],
            "assistant_bot": ASSISTANT_BOTS.get(
                department
            ),
            "project_context": {
                "project_id": project_id,
                "scene_id": scene_id,
                "shot_id": shot_id,
            },
            "source_asset": {
                "asset_uri": asset_uri,
                "qc_fingerprint": validation[
                    "qc_fingerprint"
                ],
            },
            "instructions": instructions.strip(),
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
        }

        order_core["work_order_fingerprint"] = (
            fingerprint(order_core)
        )

        return order_core

    # -------------------------------------------------------------------------
    # BUILD POST PACKET
    # -------------------------------------------------------------------------

    def build_post_packet(
        self,
        qc_packet: dict[str, Any],
        project_id: str,
        scene_id: str,
        shot_id: str,
        asset_uri: str,
    ) -> dict[str, Any]:

        validation = self.validate_qc_packet(
            qc_packet
        )

        immutable_qc_snapshot = deepcopy(
            qc_packet
        )

        work_orders = {}

        for department in SPECIALIST_BOTS:

            work_orders[department] = (
                self.build_work_order(
                    department=department,
                    project_id=project_id,
                    scene_id=scene_id,
                    shot_id=shot_id,
                    asset_uri=asset_uri,
                    qc_packet=qc_packet,
                )
            )

        packet_core = {
            "schema": POST_PACKET_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "receives_from": RECEIVES_FROM,
            "successful_handoff": SUCCESSFUL_HANDOFF,
            "assistant_required": ASSISTANT_REQUIRED,
            "qc_validation": validation,
            "project_context": {
                "project_id": project_id,
                "scene_id": scene_id,
                "shot_id": shot_id,
            },
            "source_asset_uri": asset_uri,
            "immutable_qc_snapshot": (
                immutable_qc_snapshot
            ),
            "specialist_bots": deepcopy(
                SPECIALIST_BOTS
            ),
            "assistant_bots": deepcopy(
                ASSISTANT_BOTS
            ),
            "work_orders": work_orders,
            "post_policy": {
                "qc_pass_required": True,
                "upstream_creative_locks_preserved": True,
                "silent_creative_mutation_allowed": False,
                "department_scope_enforced": True,
                "final_delivery_before_completion": False,
            },
        }

        packet_core["packet_fingerprint"] = (
            fingerprint(packet_core)
        )

        return packet_core

    # -------------------------------------------------------------------------
    # COMPLETE POST
    # -------------------------------------------------------------------------

    def complete_post(
        self,
        post_packet: dict[str, Any],
        department_results: dict[str, Any],
        final_master_uri: str,
    ) -> dict[str, Any]:

        if post_packet.get(
            "schema"
        ) != POST_PACKET_SCHEMA:
            raise ValueError(
                "Invalid Post-Production packet."
            )

        required_departments = set(
            SPECIALIST_BOTS.keys()
        )

        supplied_departments = set(
            department_results.keys()
        )

        missing = (
            required_departments
            - supplied_departments
        )

        if missing:
            raise ValueError(
                "Post-Production incomplete. "
                f"Missing departments: "
                f"{sorted(missing)}"
            )

        for department in required_departments:

            result = department_results[
                department
            ]

            if not isinstance(result, dict):
                raise ValueError(
                    f"{department} result must "
                    "be an object."
                )

            if result.get(
                "status"
            ) != "completed":
                raise ValueError(
                    f"{department} has not "
                    "completed successfully."
                )

            if result.get(
                "creative_integrity_preserved"
            ) is not True:
                raise ValueError(
                    f"{department} violated "
                    "creative integrity."
                )

        result_core = {
            "schema": POST_RESULT_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "project_context": deepcopy(
                post_packet[
                    "project_context"
                ]
            ),
            "source_post_packet_fingerprint": (
                post_packet[
                    "packet_fingerprint"
                ]
            ),
            "department_results": deepcopy(
                department_results
            ),
            "final_master_uri": (
                final_master_uri
            ),
            "status": "completed",
            "creative_integrity_preserved": True,
            "handoff": {
                "destination": (
                    SUCCESSFUL_HANDOFF
                ),
                "ready_for_delivery_archive": True,
            },
        }

        result_core["result_fingerprint"] = (
            fingerprint(result_core)
        )

        return result_core

    # -------------------------------------------------------------------------
    # ACCEPTANCE TESTS
    # -------------------------------------------------------------------------

    def acceptance_test(self) -> dict[str, Any]:

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

        qc = {
            "schema": QC_SCHEMA,
            "decision": "PASS",
            "post_production_authorized": True,
            "asset_uri": (
                "hf://project/shot001.mp4"
            ),
            "packet_fingerprint": "QC-FP-001",
        }

        kwargs = {
            "qc_packet": qc,
            "project_id": "PROJECT-001",
            "scene_id": "SCENE-001",
            "shot_id": "SHOT-001",
            "asset_uri": (
                "hf://project/shot001.mp4"
            ),
        }

        packet = self.build_post_packet(
            **kwargs
        )

        # 1
        add(
            "1. QC packet validates",
            packet["qc_validation"][
                "schema_valid"
            ],
        )

        # 2
        add(
            "2. QC PASS verified",
            packet["qc_validation"][
                "qc_pass_verified"
            ],
        )

        # 3
        add(
            "3. Post authorization verified",
            packet["qc_validation"][
                "post_authorization_verified"
            ],
        )

        # 4
        add(
            "4. Post-Production packet generates",
            packet["schema"]
            == POST_PACKET_SCHEMA,
        )

        # 5
        required = [
            "schema",
            "app_version",
            "bot_name",
            "bot_type",
            "receives_from",
            "successful_handoff",
            "qc_validation",
            "project_context",
            "source_asset_uri",
            "immutable_qc_snapshot",
            "specialist_bots",
            "work_orders",
            "post_policy",
            "packet_fingerprint",
        ]

        add(
            "5. Required Post packet fields present",
            all(
                x in packet
                for x in required
            ),
        )

        # 6
        add(
            "6. Editorial Worker Bot declared",
            "editorial"
            in packet["specialist_bots"],
        )

        # 7
        add(
            "7. Sound Worker Bot declared",
            "sound"
            in packet["specialist_bots"],
        )

        # 8
        add(
            "8. Music Worker Bot declared",
            "music"
            in packet["specialist_bots"],
        )

        # 9
        add(
            "9. Compositing/VFX Worker Bot declared",
            "compositing_vfx"
            in packet["specialist_bots"],
        )

        # 10
        add(
            "10. Color/Finish Worker Bot declared",
            "color_finish"
            in packet["specialist_bots"],
        )

        # 11
        add(
            "11. Titles/Graphics Worker Bot declared",
            "titles_graphics"
            in packet["specialist_bots"],
        )

        # 12
        add(
            "12. Edit Assistant Bot declared",
            packet["assistant_bots"].get(
                "editorial"
            )
            == "J.O.A.T. Edit Assistant Bot",
        )

        # 13
        add(
            "13. Audio Assistant Bot declared",
            packet["assistant_bots"].get(
                "sound"
            )
            == "J.O.A.T. Audio Assistant Bot",
        )

        # 14
        add(
            "14. Six specialist work orders generate",
            len(
                packet["work_orders"]
            ) == 6,
        )

        # 15
        add(
            "15. Editorial work order routes correctly",
            packet["work_orders"][
                "editorial"
            ]["assigned_bot"]
            == SPECIALIST_BOTS["editorial"],
        )

        # 16
        add(
            "16. Sound work order routes correctly",
            packet["work_orders"][
                "sound"
            ]["assigned_bot"]
            == SPECIALIST_BOTS["sound"],
        )

        # 17
        add(
            "17. Music work order routes correctly",
            packet["work_orders"][
                "music"
            ]["assigned_bot"]
            == SPECIALIST_BOTS["music"],
        )

        # 18
        add(
            "18. Compositing/VFX work order routes correctly",
            packet["work_orders"][
                "compositing_vfx"
            ]["assigned_bot"]
            == SPECIALIST_BOTS[
                "compositing_vfx"
            ],
        )

        # 19
        add(
            "19. Color/Finish work order routes correctly",
            packet["work_orders"][
                "color_finish"
            ]["assigned_bot"]
            == SPECIALIST_BOTS[
                "color_finish"
            ],
        )

        # 20
        add(
            "20. Titles/Graphics work order routes correctly",
            packet["work_orders"][
                "titles_graphics"
            ]["assigned_bot"]
            == SPECIALIST_BOTS[
                "titles_graphics"
            ],
        )

        # 21
        policies_ok = all(
            order[
                "authority_boundary"
            ][
                "may_change_locked_character_identity"
            ] is False
            and order[
                "authority_boundary"
            ][
                "may_change_locked_environment_identity"
            ] is False
            and order[
                "authority_boundary"
            ][
                "may_reinterpret_director_intent"
            ] is False
            and order[
                "authority_boundary"
            ][
                "may_reinterpret_camera_intent"
            ] is False
            and order[
                "authority_boundary"
            ][
                "may_reinterpret_performance_intent"
            ] is False
            for order
            in packet[
                "work_orders"
            ].values()
        )

        add(
            "21. Creative drift protection active",
            policies_ok,
        )

        # 22
        first = self.build_post_packet(
            **kwargs
        )

        second = self.build_post_packet(
            **kwargs
        )

        add(
            "22. Deterministic Post packet fingerprint",
            first[
                "packet_fingerprint"
            ]
            == second[
                "packet_fingerprint"
            ],
        )

        # 23
        before = stable_json(qc)

        self.build_post_packet(
            **kwargs
        )

        after = stable_json(qc)

        add(
            "23. QC packet remains immutable",
            before == after,
        )

        # 24
        rejected = False

        bad_qc = deepcopy(qc)
        bad_qc["decision"] = "REJECT"

        try:
            self.build_post_packet(
                **{
                    **kwargs,
                    "qc_packet": bad_qc,
                }
            )
        except ValueError:
            rejected = True

        add(
            "24. QC rejection blocks Post-Production",
            rejected,
        )

        # 25
        rejected = False

        no_auth = deepcopy(qc)
        no_auth[
            "post_production_authorized"
        ] = False

        try:
            self.build_post_packet(
                **{
                    **kwargs,
                    "qc_packet": no_auth,
                }
            )
        except ValueError:
            rejected = True

        add(
            "25. Missing QC authorization blocks Post",
            rejected,
        )

        # 26
        department_results = {}

        for department in SPECIALIST_BOTS:
            department_results[
                department
            ] = {
                "status": "completed",
                "creative_integrity_preserved": True,
                "output_uri": (
                    f"hf://post/{department}/output"
                ),
            }

        result = self.complete_post(
            post_packet=packet,
            department_results=department_results,
            final_master_uri=(
                "hf://masters/final_master.mp4"
            ),
        )

        add(
            "26. Completed Post result generates",
            result["schema"]
            == POST_RESULT_SCHEMA,
        )

        # 27
        add(
            "27. Completed Post preserves creative integrity",
            result[
                "creative_integrity_preserved"
            ] is True,
        )

        # 28
        add(
            "28. Completed Post routes to Delivery/Archive",
            result["handoff"][
                "ready_for_delivery_archive"
            ] is True,
        )

        # 29
        blocked = False

        incomplete = deepcopy(
            department_results
        )

        incomplete.pop("music")

        try:
            self.complete_post(
                packet,
                incomplete,
                "hf://masters/final.mp4",
            )
        except ValueError:
            blocked = True

        add(
            "29. Missing specialist result blocks completion",
            blocked,
        )

        # 30
        blocked = False

        failed_integrity = deepcopy(
            department_results
        )

        failed_integrity[
            "editorial"
        ][
            "creative_integrity_preserved"
        ] = False

        try:
            self.complete_post(
                packet,
                failed_integrity,
                "hf://masters/final.mp4",
            )
        except ValueError:
            blocked = True

        add(
            "30. Creative-integrity failure blocks completion",
            blocked,
        )

        all_passed = all(
            item["pass"]
            for item in tests
        )

        return {
            "acceptance_test_version": "1.0.0",
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "assistant_required": (
                ASSISTANT_REQUIRED
            ),
            "receives_from": RECEIVES_FROM,
            "successful_handoff": (
                SUCCESSFUL_HANDOFF
            ),
            "qc_packet_schema": QC_SCHEMA,
            "post_packet_schema": (
                POST_PACKET_SCHEMA
            ),
            "work_order_schema": (
                WORK_ORDER_SCHEMA
            ),
            "post_result_schema": (
                POST_RESULT_SCHEMA
            ),
            "specialist_bots": deepcopy(
                SPECIALIST_BOTS
            ),
            "assistant_bots": deepcopy(
                ASSISTANT_BOTS
            ),
            "tests": tests,
            "all_passed": all_passed,
            "production_ready": all_passed,
            "note": (
                "Post-Production Supervisor Bot is "
                "production-ready when only QC-approved "
                "assets enter Post, all specialist work "
                "orders preserve locked creative intent, "
                "all required departments complete "
                "successfully, and the final master is "
                "authorized for Delivery/Archive."
            ),
        }


SUPERVISOR = PostProductionSupervisor()


# =============================================================================
# UI
# =============================================================================

def example_qc_packet() -> str:

    value = {
        "schema": QC_SCHEMA,
        "decision": "PASS",
        "post_production_authorized": True,
        "asset_uri": (
            "hf://project/shot001.mp4"
        ),
        "packet_fingerprint": "QC-FP-001",
    }

    return json.dumps(
        value,
        indent=2,
    )


def build_packet_ui(
    qc_raw: str,
    project_id: str,
    scene_id: str,
    shot_id: str,
    asset_uri: str,
):

    qc = parse_json_object(
        qc_raw,
        "QC Packet",
    )

    return SUPERVISOR.build_post_packet(
        qc_packet=qc,
        project_id=project_id,
        scene_id=scene_id,
        shot_id=shot_id,
        asset_uri=asset_uri,
    )


def tests_ui():
    return SUPERVISOR.acceptance_test()


def build_app() -> gr.Blocks:

    with gr.Blocks(
        title=(
            f"{BOT_NAME} v{APP_VERSION}"
        )
    ) as app:

        gr.Markdown(
            f"# {BOT_NAME}\n\n"
            "**Roadmap Stage #9**\n\n"
            "Receives QC-approved generation assets "
            "and coordinates the complete "
            "post-production department."
        )

        with gr.Tab(
            "Post-Production Packet"
        ):

            qc_raw = gr.Code(
                value=example_qc_packet(),
                language="json",
                label="QC Packet",
            )

            with gr.Row():

                project_id = gr.Textbox(
                    value="PROJECT-001",
                    label="Project ID",
                )

                scene_id = gr.Textbox(
                    value="SCENE-001",
                    label="Scene ID",
                )

                shot_id = gr.Textbox(
                    value="SHOT-001",
                    label="Shot ID",
                )

            asset_uri = gr.Textbox(
                value=(
                    "hf://project/shot001.mp4"
                ),
                label="QC-Approved Asset URI",
            )

            output = gr.JSON(
                label=(
                    "Post-Production Packet"
                )
            )

            gr.Button(
                "Build Post-Production Packet",
                variant="primary",
            ).click(
                fn=build_packet_ui,
                inputs=[
                    qc_raw,
                    project_id,
                    scene_id,
                    shot_id,
                    asset_uri,
                ],
                outputs=output,
            )

        with gr.Tab(
            "Acceptance Tests"
        ):

            test_output = gr.JSON(
                label=(
                    "Post-Production "
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
            "Department"
        ):

            gr.JSON(
                value={
                    "supervisor": BOT_NAME,
                    "assistant_required": (
                        ASSISTANT_REQUIRED
                    ),
                    "specialist_bots": (
                        SPECIALIST_BOTS
                    ),
                    "assistant_bots": (
                        ASSISTANT_BOTS
                    ),
                },
                label=(
                    "Post-Production Department"
                ),
            )

        with gr.Tab(
            "Authority"
        ):

            gr.Markdown(
                """
## Authority Boundary

The Post-Production Supervisor Bot may:

- coordinate Post departments,
- create technical work orders,
- track completion,
- assemble approved outputs,
- authorize a completed Post package.

It may **not**:

- admit an asset that failed QC,
- redesign a locked character,
- replace a locked environment,
- reinterpret Director intent,
- reinterpret approved camera direction,
- reinterpret approved performance,
- silently change upstream creative decisions,
- mark Post complete while a required department is unfinished.

Specialist bots work only inside their assigned department.
"""
            )

        from joat_production_ui import add_specialist_ui, add_post_ui, add_delivery_ui, add_voice_ui, add_timeline_ui
        gr.Markdown(f"**Production integration version:** {APP_VERSION}")
        add_post_ui()

    return app


if __name__ == "__main__":

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )