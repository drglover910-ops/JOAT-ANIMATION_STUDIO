"""
J.O.A.T. Delivery/Archive Bot v1.0.1
Roadmap Stage #16

Purpose:
- Receive completed Post-Production results
- Verify Post completion and creative-integrity preservation
- Preserve final-master provenance
- Create deterministic delivery/archive packages
- Control master naming and version records
- Track deliverables, metadata, storage and handoff authorization
- Never modify creative content
- Never replace the approved final master
- Never authorize incomplete Post results
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

BOT_NAME = "J.O.A.T. Delivery/Archive Bot"
BOT_TYPE = "delivery_archive_bot"

REPORTS_TO = "J.O.A.T. Executive Producer Bot"
RECEIVES_FROM = "J.O.A.T. Post-Production Supervisor Bot"

POST_RESULT_SCHEMA = "joat.post_production_result.v1"
DELIVERY_PACKET_SCHEMA = "joat.delivery_archive_packet.v1"
DELIVERABLE_SCHEMA = "joat.deliverable_record.v1"
ARCHIVE_SCHEMA = "joat.archive_record.v1"

ALLOWED_DELIVERY_STATUS = [
    "READY_FOR_DELIVERY",
    "ARCHIVED",
]

REQUIRED_SPECIALIST_RESULTS = [
    "editorial",
    "sound",
    "music",
    "compositing_vfx",
    "color_finish",
    "titles_graphics",
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


def fingerprint(value: dict[str, Any]) -> str:
    existing = value.get("packet_fingerprint")
    if existing:
        return str(existing)

    existing = value.get("result_fingerprint")
    if existing:
        return str(existing)

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


# =============================================================================
# VALIDATION
# =============================================================================

def validate_post_result(
    post_result: dict[str, Any],
) -> dict[str, Any]:

    if post_result.get("schema") != POST_RESULT_SCHEMA:
        raise ValueError(
            "Post result schema rejected."
        )

    if post_result.get("post_complete") is not True:
        raise ValueError(
            "Delivery blocked: Post-Production "
            "is not complete."
        )

    if (
        post_result.get("creative_integrity_preserved")
        is not True
    ):
        raise ValueError(
            "Delivery blocked: creative integrity "
            "was not preserved."
        )

    if (
        post_result.get("delivery_authorized")
        is not True
    ):
        raise ValueError(
            "Delivery blocked: Post-Production "
            "did not authorize Delivery/Archive."
        )

    final_master = post_result.get("final_master")

    if not isinstance(final_master, dict):
        raise ValueError(
            "Delivery blocked: final_master missing."
        )

    if not final_master.get("asset_id"):
        raise ValueError(
            "Delivery blocked: final master asset_id "
            "missing."
        )

    specialist_results = post_result.get(
        "specialist_results"
    )

    if not isinstance(specialist_results, dict):
        raise ValueError(
            "Delivery blocked: specialist results missing."
        )

    missing = [
        name
        for name in REQUIRED_SPECIALIST_RESULTS
        if name not in specialist_results
    ]

    if missing:
        raise ValueError(
            "Delivery blocked: missing specialist "
            f"results: {missing}"
        )

    return {
        "schema_verified": True,
        "post_complete_verified": True,
        "creative_integrity_verified": True,
        "delivery_authorization_verified": True,
        "final_master_verified": True,
        "specialist_results_verified": True,
        "post_result_fingerprint": fingerprint(
            post_result
        ),
    }


# =============================================================================
# DELIVERY / ARCHIVE BOT
# =============================================================================

class DeliveryArchiveBot:

    def build_package(
        self,
        post_result: dict[str, Any],
        project_id: str,
        title: str,
        version: str,
        master_filename: str,
        storage_location: str,
        delivery_destination: str,
        metadata_locked: bool,
    ) -> dict[str, Any]:

        validation = validate_post_result(
            post_result
        )

        if not project_id.strip():
            raise ValueError(
                "Project ID is required."
            )

        if not title.strip():
            raise ValueError(
                "Project title is required."
            )

        if not version.strip():
            raise ValueError(
                "Version is required."
            )

        if not master_filename.strip():
            raise ValueError(
                "Master filename is required."
            )

        if not storage_location.strip():
            raise ValueError(
                "Storage location is required."
            )

        if metadata_locked is not True:
            raise ValueError(
                "Delivery blocked: final metadata "
                "must be locked."
            )

        immutable_post_snapshot = deepcopy(
            post_result
        )

        final_master = deepcopy(
            post_result["final_master"]
        )

        deliverable_core = {
            "schema": DELIVERABLE_SCHEMA,
            "project_id": project_id.strip(),
            "title": title.strip(),
            "version": version.strip(),
            "master_filename": master_filename.strip(),
            "final_master": final_master,
            "delivery_destination": (
                delivery_destination.strip()
                if delivery_destination
                else None
            ),
            "metadata_locked": True,
            "creative_content_mutation_allowed": False,
            "master_replacement_allowed": False,
        }

        deliverable_core[
            "deliverable_fingerprint"
        ] = sha256_text(
            stable_json(deliverable_core)
        )

        archive_core = {
            "schema": ARCHIVE_SCHEMA,
            "project_id": project_id.strip(),
            "version": version.strip(),
            "storage_location": storage_location.strip(),
            "source_master_asset_id": (
                final_master["asset_id"]
            ),
            "source_post_fingerprint": (
                validation[
                    "post_result_fingerprint"
                ]
            ),
            "archive_immutable": True,
            "overwrite_without_new_version_allowed": False,
        }

        archive_core[
            "archive_fingerprint"
        ] = sha256_text(
            stable_json(archive_core)
        )

        packet_core = {
            "schema": DELIVERY_PACKET_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "reports_to": REPORTS_TO,
            "receives_from": RECEIVES_FROM,
            "post_validation": validation,
            "deliverable": deliverable_core,
            "archive_record": archive_core,
            "immutable_post_snapshot": (
                immutable_post_snapshot
            ),
            "authority_boundary": {
                "may_edit_final_master": False,
                "may_replace_final_master": False,
                "may_rewrite_locked_metadata": False,
                "may_change_creative_intent": False,
                "may_modify_post_result": False,
                "may_create_delivery_records": True,
                "may_create_archive_records": True,
                "may_assign_version_records": True,
            },
            "handoff_policy": {
                "post_completion_required": True,
                "creative_integrity_required": True,
                "delivery_authorization_required": True,
                "metadata_lock_required": True,
            },
            "delivery_status": (
                "READY_FOR_DELIVERY"
                if delivery_destination.strip()
                else "ARCHIVED"
            ),
            "production_ready": True,
        }

        packet_core[
            "packet_fingerprint"
        ] = sha256_text(
            stable_json(packet_core)
        )

        return packet_core


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

        specialist_results = {
            name: {
                "status": "complete",
                "creative_integrity_preserved": True,
            }
            for name in REQUIRED_SPECIALIST_RESULTS
        }

        post_result = {
            "schema": POST_RESULT_SCHEMA,
            "post_complete": True,
            "creative_integrity_preserved": True,
            "delivery_authorized": True,
            "final_master": {
                "asset_id": "MASTER-001",
                "format": "mp4",
                "aspect_ratio": "16:9",
            },
            "specialist_results": specialist_results,
            "result_fingerprint": "POST-FP-001",
        }

        kwargs = {
            "post_result": post_result,
            "project_id": "PROJECT-001",
            "title": "J.O.A.T. Production",
            "version": "v1.0.0",
            "master_filename": (
                "JOAT_PROJECT-001_MASTER_v1.0.0.mp4"
            ),
            "storage_location": (
                "joat://archive/PROJECT-001/v1.0.0"
            ),
            "delivery_destination": (
                "authorized_delivery_target"
            ),
            "metadata_locked": True,
        }

        packet = self.build_package(**kwargs)

        # 1
        add(
            "1. Post-Production result schema validates",
            packet["post_validation"][
                "schema_verified"
            ] is True,
        )

        # 2
        add(
            "2. Post completion verified",
            packet["post_validation"][
                "post_complete_verified"
            ] is True,
        )

        # 3
        add(
            "3. Creative integrity verified",
            packet["post_validation"][
                "creative_integrity_verified"
            ] is True,
        )

        # 4
        add(
            "4. Delivery authorization verified",
            packet["post_validation"][
                "delivery_authorization_verified"
            ] is True,
        )

        # 5
        add(
            "5. Final master verified",
            packet["post_validation"][
                "final_master_verified"
            ] is True,
        )

        # 6
        add(
            "6. All Post specialist results verified",
            packet["post_validation"][
                "specialist_results_verified"
            ] is True,
        )

        # 7
        add(
            "7. Delivery/Archive packet generates",
            packet.get("schema")
            == DELIVERY_PACKET_SCHEMA,
        )

        # 8
        required_fields = [
            "schema",
            "app_version",
            "bot_name",
            "bot_type",
            "reports_to",
            "receives_from",
            "post_validation",
            "deliverable",
            "archive_record",
            "immutable_post_snapshot",
            "authority_boundary",
            "handoff_policy",
            "delivery_status",
            "production_ready",
            "packet_fingerprint",
        ]

        add(
            "8. Required Delivery/Archive fields present",
            all(
                field in packet
                for field in required_fields
            ),
        )

        # 9
        add(
            "9. Delivery Bot receives from Post Supervisor",
            packet["receives_from"]
            == "J.O.A.T. Post-Production Supervisor Bot",
        )

        # 10
        add(
            "10. Deliverable record generates",
            packet["deliverable"]["schema"]
            == DELIVERABLE_SCHEMA,
        )

        # 11
        add(
            "11. Archive record generates",
            packet["archive_record"]["schema"]
            == ARCHIVE_SCHEMA,
        )

        # 12
        add(
            "12. Final master identity preserved",
            (
                packet["deliverable"]["final_master"][
                    "asset_id"
                ]
                == post_result["final_master"][
                    "asset_id"
                ]
            ),
        )

        # 13
        add(
            "13. Final master replacement prohibited",
            packet["authority_boundary"][
                "may_replace_final_master"
            ] is False,
        )

        # 14
        add(
            "14. Final master editing prohibited",
            packet["authority_boundary"][
                "may_edit_final_master"
            ] is False,
        )

        # 15
        add(
            "15. Locked metadata rewrite prohibited",
            packet["authority_boundary"][
                "may_rewrite_locked_metadata"
            ] is False,
        )

        # 16
        add(
            "16. Creative reinterpretation prohibited",
            packet["authority_boundary"][
                "may_change_creative_intent"
            ] is False,
        )

        # 17
        add(
            "17. Post result mutation prohibited",
            packet["authority_boundary"][
                "may_modify_post_result"
            ] is False,
        )

        # 18
        add(
            "18. Version record preserved",
            packet["deliverable"]["version"]
            == "v1.0.0",
        )

        # 19
        add(
            "19. Master filename preserved",
            packet["deliverable"][
                "master_filename"
            ]
            == "JOAT_PROJECT-001_MASTER_v1.0.0.mp4",
        )

        # 20
        add(
            "20. Archive source master preserved",
            packet["archive_record"][
                "source_master_asset_id"
            ]
            == "MASTER-001",
        )

        # 21
        add(
            "21. Archive is immutable",
            packet["archive_record"][
                "archive_immutable"
            ] is True,
        )

        # 22
        add(
            "22. Archive overwrite prohibited",
            packet["archive_record"][
                "overwrite_without_new_version_allowed"
            ] is False,
        )

        # 23
        first = self.build_package(**kwargs)
        second = self.build_package(**kwargs)

        add(
            "23. Deterministic Delivery/Archive fingerprint",
            first["packet_fingerprint"]
            == second["packet_fingerprint"],
        )

        # 24
        before = stable_json(post_result)

        self.build_package(**kwargs)

        after = stable_json(post_result)

        add(
            "24. Post result remains immutable",
            before == after,
        )

        # 25
        rejected = False

        bad = deepcopy(post_result)
        bad["post_complete"] = False

        try:
            self.build_package(
                **{
                    **kwargs,
                    "post_result": bad,
                }
            )
        except ValueError:
            rejected = True

        add(
            "25. Incomplete Post result rejected",
            rejected,
        )

        # 26
        rejected = False

        bad = deepcopy(post_result)
        bad["creative_integrity_preserved"] = False

        try:
            self.build_package(
                **{
                    **kwargs,
                    "post_result": bad,
                }
            )
        except ValueError:
            rejected = True

        add(
            "26. Creative-integrity failure rejected",
            rejected,
        )

        # 27
        rejected = False

        bad = deepcopy(post_result)
        bad["delivery_authorized"] = False

        try:
            self.build_package(
                **{
                    **kwargs,
                    "post_result": bad,
                }
            )
        except ValueError:
            rejected = True

        add(
            "27. Missing delivery authorization rejected",
            rejected,
        )

        # 28
        rejected = False

        bad = deepcopy(post_result)
        del bad["final_master"]

        try:
            self.build_package(
                **{
                    **kwargs,
                    "post_result": bad,
                }
            )
        except ValueError:
            rejected = True

        add(
            "28. Missing final master rejected",
            rejected,
        )

        # 29
        rejected = False

        bad = deepcopy(post_result)

        del bad["specialist_results"]["editorial"]

        try:
            self.build_package(
                **{
                    **kwargs,
                    "post_result": bad,
                }
            )
        except ValueError:
            rejected = True

        add(
            "29. Missing specialist result rejected",
            rejected,
        )

        # 30
        rejected = False

        try:
            self.build_package(
                **{
                    **kwargs,
                    "metadata_locked": False,
                }
            )
        except ValueError:
            rejected = True

        add(
            "30. Unlocked final metadata rejected",
            rejected,
        )

        # 31
        add(
            "31. Deliverable fingerprint generated",
            bool(
                packet["deliverable"].get(
                    "deliverable_fingerprint"
                )
            ),
        )

        # 32
        add(
            "32. Archive fingerprint generated",
            bool(
                packet["archive_record"].get(
                    "archive_fingerprint"
                )
            ),
        )

        # 33
        add(
            "33. Delivery destination preserved",
            packet["deliverable"][
                "delivery_destination"
            ]
            == "authorized_delivery_target",
        )

        # 34
        add(
            "34. Authorized package marked ready for delivery",
            packet["delivery_status"]
            == "READY_FOR_DELIVERY",
        )

        # 35
        archive_only = self.build_package(
            **{
                **kwargs,
                "delivery_destination": "",
            }
        )

        add(
            "35. Archive-only package supported",
            archive_only["delivery_status"]
            == "ARCHIVED",
        )

        # 36
        add(
            "36. Production-ready flag set",
            packet["production_ready"] is True,
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
            "assistant_required": False,
            "receives_from": RECEIVES_FROM,
            "reports_to": REPORTS_TO,
            "post_result_schema": POST_RESULT_SCHEMA,
            "delivery_packet_schema": (
                DELIVERY_PACKET_SCHEMA
            ),
            "deliverable_schema": DELIVERABLE_SCHEMA,
            "archive_schema": ARCHIVE_SCHEMA,
            "tests": tests,
            "all_passed": all_passed,
            "production_ready": all_passed,
            "note": (
                "Delivery/Archive Bot is production-ready "
                "when only completed and authorized "
                "Post-Production masters enter delivery, "
                "the approved master and metadata remain "
                "immutable, version and provenance records "
                "are preserved, and archive/delivery records "
                "are deterministic."
            ),
        }


BOT = DeliveryArchiveBot()


# =============================================================================
# UI
# =============================================================================

def example_post_result() -> str:

    specialist_results = {
        name: {
            "status": "complete",
            "creative_integrity_preserved": True,
        }
        for name in REQUIRED_SPECIALIST_RESULTS
    }

    value = {
        "schema": POST_RESULT_SCHEMA,
        "post_complete": True,
        "creative_integrity_preserved": True,
        "delivery_authorized": True,
        "final_master": {
            "asset_id": "MASTER-001",
            "format": "mp4",
            "aspect_ratio": "16:9",
        },
        "specialist_results": specialist_results,
        "result_fingerprint": "POST-FP-001",
    }

    return json.dumps(
        value,
        indent=2,
    )


def build_package_ui(
    post_raw: str,
    project_id: str,
    title: str,
    version: str,
    master_filename: str,
    storage_location: str,
    delivery_destination: str,
    metadata_locked: bool,
) -> dict[str, Any]:

    post_result = parse_json_object(
        post_raw,
        "Post-Production Result",
    )

    return BOT.build_package(
        post_result=post_result,
        project_id=project_id,
        title=title,
        version=version,
        master_filename=master_filename,
        storage_location=storage_location,
        delivery_destination=delivery_destination,
        metadata_locked=metadata_locked,
    )


def tests_ui() -> dict[str, Any]:
    return BOT.acceptance_test()


def build_app() -> gr.Blocks:

    with gr.Blocks(
        title=f"{BOT_NAME} v{APP_VERSION}"
    ) as app:

        gr.Markdown(
            f"# {BOT_NAME}\n\n"
            "**Roadmap Stage #16**\n\n"
            "Receives completed Post-Production masters, "
            "protects the approved master, creates versioned "
            "delivery/archive records, and preserves provenance."
        )

        with gr.Tab("Delivery / Archive"):

            post_raw = gr.Code(
                value=example_post_result(),
                language="json",
                label="Post-Production Result",
            )

            with gr.Row():

                project_id = gr.Textbox(
                    value="PROJECT-001",
                    label="Project ID",
                )

                title = gr.Textbox(
                    value="J.O.A.T. Production",
                    label="Project Title",
                )

                version = gr.Textbox(
                    value="v1.0.0",
                    label="Version",
                )

            master_filename = gr.Textbox(
                value=(
                    "JOAT_PROJECT-001_MASTER_v1.0.0.mp4"
                ),
                label="Master Filename",
            )

            storage_location = gr.Textbox(
                value=(
                    "joat://archive/PROJECT-001/v1.0.0"
                ),
                label="Archive Storage Location",
            )

            delivery_destination = gr.Textbox(
                value="authorized_delivery_target",
                label="Delivery Destination",
            )

            metadata_locked = gr.Checkbox(
                value=True,
                label="Final Metadata Locked",
            )

            output = gr.JSON(
                label="Delivery / Archive Packet",
            )

            gr.Button(
                "Build Delivery / Archive Package",
                variant="primary",
            ).click(
                fn=build_package_ui,
                inputs=[
                    post_raw,
                    project_id,
                    title,
                    version,
                    master_filename,
                    storage_location,
                    delivery_destination,
                    metadata_locked,
                ],
                outputs=output,
            )

        with gr.Tab("Acceptance Tests"):

            test_output = gr.JSON(
                label=(
                    "Delivery/Archive Acceptance Test"
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

        with gr.Tab("Authority Boundary"):

            gr.JSON(
                value={
                    "bot": BOT_NAME,
                    "receives_from": RECEIVES_FROM,
                    "may": [
                        "verify completed Post results",
                        "create deliverable records",
                        "create archive records",
                        "assign version records",
                        "preserve final-master provenance",
                        "package authorized deliverables",
                    ],
                    "may_not": [
                        "edit the final master",
                        "replace the approved final master",
                        "rewrite locked metadata",
                        "change creative intent",
                        "modify Post-Production results",
                        "authorize incomplete productions",
                    ],
                },
                label="Delivery/Archive Authority",
            )

        with gr.Tab("About"):

            gr.Markdown(
                f"""
## {BOT_NAME}

**Version:** {APP_VERSION}

**Receives from:**  
{RECEIVES_FROM}

**Delivery packet:**  
`{DELIVERY_PACKET_SCHEMA}`

**Deliverable record:**  
`{DELIVERABLE_SCHEMA}`

**Archive record:**  
`{ARCHIVE_SCHEMA}`

### Chain

Post-Production Supervisor Bot  
↓  
**Delivery/Archive Bot**  
↓  
Archive / Authorized Delivery / Publishing Handoff

### Core Rule

The approved final master is immutable.

A new creative or technical revision must return through the
responsible production pipeline and become a **new version**.

Delivery/Archive does not secretly modify the existing master.
"""
            )

        from joat_production_ui import add_specialist_ui, add_post_ui, add_delivery_ui, add_voice_ui, add_timeline_ui
        gr.Markdown(f"**Production integration version:** {APP_VERSION}")
        add_delivery_ui()

    return app


if __name__ == "__main__":

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )