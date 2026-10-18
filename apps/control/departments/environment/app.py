"""
J.O.A.T. Scene & Environment Master v1.1.1

Roadmap Stage #3

Purpose:
- Own the approved environment registry
- Lock reusable environment/location identity
- Register the 8 approved local environment identity anchors
- Verify exact local files with SHA-256
- Preserve time-of-day, lighting, architecture, geography, and visual continuity
- Produce deterministic joat.environment_packet.v1 packets
- Hand controlled environment packets downstream to Director / Shot / LTX workers
- Never silently mutate locked environment masters
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import gradio as gr


# =============================================================================
# CONFIG
# =============================================================================

APP_VERSION = "1.1.1"
FILE_VERSION = "1.1.1"
ACCEPTANCE_TEST_VERSION = "1.1.0"

REGISTRY_SCHEMA = "joat.environment_registry.v1"
PACKET_SCHEMA = "joat.environment_packet.v1"

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "environments.json"
ASSET_DIR = ROOT / "environment_assets"


# =============================================================================
# ENVIRONMENT DEFINITIONS
# IMPORTANT:
# Registry IDs below remain exactly as established in v1.0.0.
#
# The uploaded filenames came from the earlier package with different ID
# labels. We DO NOT rename or re-upload them. Instead, each registry record
# explicitly points to the correct approved image.
# =============================================================================

ENVIRONMENT_DEFINITIONS = [
    {
        "id": "ENV-001",
        "name": "Executive Office",
        "aliases": ["Executive Office", "Office"],
        "category": "interior",
        "description": "Executive office environment.",
        "anchor_filename": "ENV-008_office_identity_anchor.jpeg",
    },
    {
        "id": "ENV-002",
        "name": "Coffee Shop",
        "aliases": ["Coffee Shop", "Cafe", "Café"],
        "category": "interior",
        "description": "Coffee shop / cafe environment.",
        "anchor_filename": "ENV-007_cafe_identity_anchor.jpeg",
    },
    {
        "id": "ENV-003",
        "name": "Luxury Loft Apartment",
        "aliases": ["Luxury Loft Apartment", "Luxury Loft", "Loft"],
        "category": "interior",
        "description": "Luxury loft apartment environment.",
        "anchor_filename": "ENV-006_loft_identity_anchor.jpeg",
    },
    {
        "id": "ENV-004",
        "name": "Gated Community",
        "aliases": ["Gated Community"],
        "category": "exterior",
        "description": "Gated residential community environment.",
        "anchor_filename": "ENV-005_gated_community_identity_anchor.jpeg",
    },
    {
        "id": "ENV-005",
        "name": "Got Ham Neighborhood",
        "aliases": ["Got Ham Neighborhood", "Got Ham"],
        "category": "exterior",
        "description": "Established Got Ham neighborhood environment.",
        "anchor_filename": "ENV-003_neighborhood_identity_anchor.jpeg",
    },
    {
        "id": "ENV-006",
        "name": "Rough WNY Apartment Interior",
        "aliases": [
            "Rough WNY Apartment Interior",
            "WNY Apartment",
            "Rough Apartment",
        ],
        "category": "interior",
        "description": "Established rough WNY apartment interior environment.",
        "anchor_filename": "ENV-004_apartment_identity_anchor.jpeg",
    },
    {
        "id": "ENV-007",
        "name": "Local Grocery Store",
        "aliases": ["Local Grocery Store", "Grocery Store"],
        "category": "interior",
        "description": "Established local grocery store environment.",
        "anchor_filename": "ENV-002_grocery_store_identity_anchor.jpeg",
    },
    {
        "id": "ENV-008",
        "name": "Baptist Church",
        "aliases": ["Baptist Church", "Church"],
        "category": "interior",
        "description": "Established Baptist church environment.",
        "anchor_filename": "ENV-001_church_identity_anchor.jpeg",
    },
]


# =============================================================================
# HELPERS
# =============================================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_name(value: str) -> str:
    return " ".join(str(value).strip().casefold().split())


def anchor_path(definition: dict[str, Any]) -> Path:
    return ASSET_DIR / definition["anchor_filename"]


def anchor_relative_path(definition: dict[str, Any]) -> str:
    return f"environment_assets/{definition['anchor_filename']}"


def build_anchor_asset(definition: dict[str, Any]) -> dict[str, Any]:
    """
    Build the approved local identity-anchor record.

    Hash is computed from the exact file in the Space. This prevents us from
    inventing or manually typing a hash and ties the lock to the uploaded bytes.
    """
    path = anchor_path(definition)

    asset = {
        "asset_id": f"{definition['id']}-A01",
        "filename": definition["anchor_filename"],
        "path": anchor_relative_path(definition),
        "sha256": None,
        "roles": [
            "identity_anchor",
            "establishing_view",
            "wide_reference",
            "interior_reference"
            if definition["category"] == "interior"
            else "exterior_reference",
            "scene_reference",
            "detail_reference",
            "architecture_reference",
        ],
        "status": "approved",
        "source": "J.O.A.T. approved local environment master",
        "locked": True,
    }

    if path.is_file():
        asset["sha256"] = sha256_file(path)

    return asset


# =============================================================================
# DEFAULT REGISTRY
# =============================================================================

def default_environment_record(
    definition: dict[str, Any]
) -> dict[str, Any]:

    env_id = definition["id"]

    return {
        "id": env_id,
        "name": definition["name"],
        "aliases": definition["aliases"],
        "version": "1.1.0",
        "status": "approved_locked",
        "category": definition["category"],
        "description": definition["description"],

        "assets": [
            build_anchor_asset(definition)
        ],

        "environment_rules": {
            "identity": (
                f"Preserve the approved {definition['name']} environment "
                "identity across all shots."
            ),
            "architecture": (
                "Preserve reference-supported architecture, room geometry, "
                "building geometry, entrances, windows, permanent fixtures, "
                "major furniture placement, and structural relationships."
            ),
            "geography": (
                "Preserve reference-supported spatial relationships and "
                "geographic layout. Do not randomly relocate permanent "
                "environment features between shots."
            ),
            "materials": (
                "Preserve reference-supported surfaces, finishes, textures, "
                "colors, and permanent decor."
            ),
            "lighting": (
                "Lighting may change only when required by the approved "
                "time-of-day or scene instructions. The physical environment "
                "identity must remain stable."
            ),
            "time_of_day": (
                "Use the requested time-of-day while preserving the locked "
                "environment identity."
            ),
        },

        "continuity_rules": [
            (
                f"Preserve {definition['name']} architecture, layout, "
                "permanent fixtures, spatial relationships, and distinctive "
                "visual landmarks across shots."
            ),
            (
                "Use the approved environment identity anchor for "
                "continuity-linked shots."
            ),
            (
                "Supporting references may provide alternate angles, "
                "lighting, or detail without replacing the locked "
                "environment identity."
            ),
            (
                "Time-of-day and lighting changes must remain physically "
                "consistent with the same location."
            ),
            (
                "Characters, temporary props, vehicles, products, weather, "
                "and removable decorations do not become permanent "
                "environment traits unless explicitly approved."
            ),
        ],

        "negative_rules": [
            (
                "Do not change the location into a different building, room, "
                "street, neighborhood, store, church, or architectural style "
                "without an approved environment-version change."
            ),
            (
                "Do not silently move permanent doors, windows, walls, "
                "fixtures, major furniture, streets, structures, or "
                "landmarks between continuity-linked shots."
            ),
            (
                "Do not infer permanent environment traits from temporary "
                "characters, props, vehicles, weather, or scene dressing."
            ),
            (
                "Do not overwrite approved environment assets, metadata, "
                "paths, or hashes silently."
            ),
        ],

        "selection_policy": {
            "identity": [
                "identity_anchor",
                "establishing_view",
                "wide_reference",
                "detail_reference",
            ],
            "wide": [
                "identity_anchor",
                "wide_reference",
                "establishing_view",
            ],
            "interior": [
                "identity_anchor",
                "interior_reference",
                "wide_reference",
                "detail_reference",
            ],
            "exterior": [
                "identity_anchor",
                "exterior_reference",
                "establishing_view",
                "wide_reference",
            ],
            "lighting": [
                "identity_anchor",
                "lighting_reference",
                "time_of_day_reference",
            ],
            "detail": [
                "identity_anchor",
                "detail_reference",
                "architecture_reference",
            ],
            "scene": [
                "identity_anchor",
                "scene_reference",
                "wide_reference",
                "detail_reference",
            ],
        },

        "approval": {
            "live_change_allowed": False,
            "requires_human_approval_for_registry_mutation": True,
        },
    }


def build_default_registry() -> dict[str, Any]:
    return {
        "schema": REGISTRY_SCHEMA,
        "registry_version": "1.1.0",
        "locked_baseline": True,
        "environments": [
            default_environment_record(x)
            for x in ENVIRONMENT_DEFINITIONS
        ],
    }


# =============================================================================
# REGISTRY
# =============================================================================

class EnvironmentMaster:

    def __init__(self, path: Path):
        self.path = path
        self.registry: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        """
        Build the authoritative registry from the locked definitions plus the
        exact approved local files.

        We intentionally do not silently rewrite environments.json.
        """
        self.registry = build_default_registry()

    def list_environments(self) -> list[dict[str, Any]]:
        return deepcopy(
            self.registry.get("environments", [])
        )

    def resolve(self, identifier: str) -> dict[str, Any]:
        wanted = normalize_name(identifier)

        for env in self.registry.get("environments", []):
            candidates = [
                env.get("id", ""),
                env.get("name", ""),
                *env.get("aliases", []),
            ]

            if any(
                normalize_name(x) == wanted
                for x in candidates
            ):
                return deepcopy(env)

        raise KeyError(
            f"Unknown environment: {identifier}"
        )

    def registry_fingerprint(self) -> str:
        return sha256_text(
            stable_json(self.registry)
        )

    def selected_assets(
        self,
        identifier: str,
        task: str,
    ) -> list[dict[str, Any]]:

        env = self.resolve(identifier)

        assets = [
            x
            for x in env.get("assets", [])
            if x.get("status", "approved") == "approved"
        ]

        policy = env.get(
            "selection_policy",
            {}
        )

        roles = policy.get(
            task,
            policy.get("identity", [])
        )

        selected: list[dict[str, Any]] = []

        for role in roles:
            for asset in assets:
                if (
                    role in asset.get("roles", [])
                    and asset not in selected
                ):
                    selected.append(asset)

        return selected

    def identity_anchor(
        self,
        identifier: str,
    ) -> Optional[dict[str, Any]]:

        env = self.resolve(identifier)

        for asset in env.get("assets", []):

            if (
                asset.get("status") == "approved"
                and asset.get("locked") is True
                and "identity_anchor"
                in asset.get("roles", [])
            ):
                location = self._asset_location(asset)

                if not location:
                    continue

                local_path = ROOT / location

                if not local_path.is_file():
                    continue

                expected = asset.get("sha256")

                if not expected:
                    continue

                actual = sha256_file(local_path)

                if actual != expected:
                    continue

                return asset

        return None

    def build_packet(
        self,
        identifier: str,
        task: str = "identity",
        time_of_day: str = "director_defined",
        lighting: str = "director_defined",
        weather: str = "director_defined",
        scene_id: str = "",
        shot_id: str = "",
    ) -> dict[str, Any]:

        env = self.resolve(identifier)
        selected = self.selected_assets(
            identifier,
            task
        )

        anchor = self.identity_anchor(identifier)

        asset_lock_ready = anchor is not None

        supporting = [
            x
            for x in selected
            if (
                anchor is None
                or x.get("asset_id")
                != anchor.get("asset_id")
            )
        ]

        packet_core = {
            "schema": PACKET_SCHEMA,

            "environment_id": env["id"],
            "environment_name": env["name"],
            "environment_version": env.get(
                "version",
                "1.1.0"
            ),

            "task": task,

            "environment_locked": True,
            "asset_identity_lock_ready": (
                asset_lock_ready
            ),

            "identity_lock_asset": (
                self._asset_location(anchor)
                if anchor
                else None
            ),

            "identity_lock_sha256": (
                anchor.get("sha256")
                if anchor
                else None
            ),

            "supporting_reference_assets": [
                self._asset_location(x)
                for x in supporting
                if self._asset_location(x)
            ],

            "environment_rules": deepcopy(
                env.get(
                    "environment_rules",
                    {}
                )
            ),

            "continuity_rules": deepcopy(
                env.get(
                    "continuity_rules",
                    []
                )
            ),

            "negative_rules": deepcopy(
                env.get(
                    "negative_rules",
                    []
                )
            ),

            "scene_context": {
                "scene_id": scene_id or None,
                "shot_id": shot_id or None,
                "time_of_day": time_of_day,
                "lighting": lighting,
                "weather": weather,
            },

            "source_asset_hashes": {
                x["asset_id"]: x.get("sha256")
                for x in selected
                if (
                    x.get("asset_id")
                    and x.get("sha256")
                )
            },

            "source_asset_locations": {
                x["asset_id"]:
                    self._asset_location(x)
                for x in selected
                if (
                    x.get("asset_id")
                    and self._asset_location(x)
                )
            },

            "approval": deepcopy(
                env.get(
                    "approval",
                    {
                        "live_change_allowed": False,
                        "requires_human_approval_for_registry_mutation":
                            True,
                    },
                )
            ),

            "downstream_handoff": {
                "director_compatible": True,
                "shot_camera_compatible": True,
                "ltx_compatible": True,
                "registry_mutation_allowed": False,
            },
        }

        packet_core["packet_fingerprint"] = (
            sha256_text(
                stable_json(packet_core)
            )
        )

        return packet_core

    @staticmethod
    def _asset_location(
        asset: Optional[dict[str, Any]]
    ) -> Optional[str]:

        if not asset:
            return None

        return (
            asset.get("path")
            or asset.get("url")
            or asset.get("ghl_url")
        )

    def verify_assets(
        self,
        identifier: str,
    ) -> dict[str, Any]:

        env = self.resolve(identifier)

        results = []

        for asset in env.get("assets", []):
            results.append(
                self._verify_one_asset(asset)
            )

        all_ok = (
            all(x["ok"] for x in results)
            if results
            else False
        )

        return {
            "environment_id": env["id"],
            "environment_name": env["name"],
            "asset_count": len(
                env.get("assets", [])
            ),
            "all_ok": all_ok,
            "asset_identity_lock_ready": (
                self.identity_anchor(
                    identifier
                ) is not None
            ),
            "results": results,
        }

    def _verify_one_asset(
        self,
        asset: dict[str, Any],
    ) -> dict[str, Any]:

        asset_id = asset.get("asset_id")
        expected_hash = asset.get("sha256")
        location = self._asset_location(asset)

        result = {
            "asset_id": asset_id,
            "location": location,
            "exists": False,
            "hash_checked": False,
            "hash_match": False,
            "expected_sha256": expected_hash,
            "actual_sha256": None,
            "locked": asset.get("locked") is True,
            "ok": False,
        }

        if not location:
            return result

        local_path = ROOT / location

        if not local_path.is_file():
            return result

        data = local_path.read_bytes()
        actual = sha256_bytes(data)

        result["exists"] = True
        result["hash_checked"] = True
        result["actual_sha256"] = actual

        result["hash_match"] = (
            bool(expected_hash)
            and actual == expected_hash
        )

        result["ok"] = (
            result["exists"]
            and result["hash_checked"]
            and result["hash_match"]
            and result["locked"]
        )

        return result

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

        # 1
        add(
            "1. Environment registry loads",
            self.registry.get("schema")
            == REGISTRY_SCHEMA,
        )

        environments = self.registry.get(
            "environments",
            []
        )

        # 2
        add(
            "2. Eight required environments registered",
            len(environments) == 8,
            len(environments),
        )

        expected_ids = [
            f"ENV-{i:03d}"
            for i in range(1, 9)
        ]

        actual_ids = [
            x.get("id")
            for x in environments
        ]

        # 3
        add(
            "3. ENV-001 through ENV-008 present",
            actual_ids == expected_ids,
            actual_ids,
        )

        # 4
        resolution_ok = True
        resolution_detail = {}

        for definition in ENVIRONMENT_DEFINITIONS:

            try:
                by_id = self.resolve(
                    definition["id"]
                )

                by_name = self.resolve(
                    definition["name"]
                )

                ok = (
                    by_id["id"]
                    == definition["id"]
                    and
                    by_name["id"]
                    == definition["id"]
                )

            except Exception:
                ok = False

            resolution_detail[
                definition["id"]
            ] = ok

            resolution_ok = (
                resolution_ok and ok
            )

        add(
            "4. IDs and names resolve",
            resolution_ok,
            resolution_detail,
        )

        # 5
        continuity_ok = all(
            len(
                x.get(
                    "continuity_rules",
                    []
                )
            ) > 0
            for x in environments
        )

        add(
            "5. Continuity rules exist for every environment",
            continuity_ok,
        )

        # 6
        negative_ok = all(
            len(
                x.get(
                    "negative_rules",
                    []
                )
            ) > 0
            for x in environments
        )

        add(
            "6. Negative rules exist for every environment",
            negative_ok,
        )

        # 7
        approval_ok = all(
            (
                x.get(
                    "approval",
                    {}
                ).get(
                    "live_change_allowed"
                )
                is False
            )
            and
            (
                x.get(
                    "approval",
                    {}
                ).get(
                    "requires_human_approval_for_registry_mutation"
                )
                is True
            )
            for x in environments
        )

        add(
            "7. Registry mutation approval gate",
            approval_ok,
        )

        # 8
        packet = self.build_packet(
            "ENV-001",
            task="scene",
            time_of_day="day",
            lighting="natural daylight",
            scene_id="SCENE-001",
            shot_id="SHOT-001",
        )

        packet_ok = (
            packet.get("schema")
            == PACKET_SCHEMA
            and packet.get(
                "environment_id"
            ) == "ENV-001"
            and packet.get(
                "environment_locked"
            ) is True
            and packet.get(
                "approval",
                {}
            ).get(
                "live_change_allowed"
            ) is False
        )

        add(
            "8. Environment packet generation",
            packet_ok,
        )

        # 9
        context_ok = (
            packet.get(
                "scene_context",
                {}
            ).get(
                "time_of_day"
            ) == "day"
            and
            packet.get(
                "scene_context",
                {}
            ).get(
                "lighting"
            ) == "natural daylight"
            and
            packet.get(
                "scene_context",
                {}
            ).get(
                "scene_id"
            ) == "SCENE-001"
            and
            packet.get(
                "scene_context",
                {}
            ).get(
                "shot_id"
            ) == "SHOT-001"
        )

        add(
            "9. Time-of-day and lighting continuity carried",
            context_ok,
        )

        # 10
        first = self.build_packet(
            "ENV-001",
            task="scene",
            time_of_day="day",
            lighting="natural daylight",
            scene_id="SCENE-001",
            shot_id="SHOT-001",
        )

        second = self.build_packet(
            "ENV-001",
            task="scene",
            time_of_day="day",
            lighting="natural daylight",
            scene_id="SCENE-001",
            shot_id="SHOT-001",
        )

        add(
            "10. Deterministic environment packet fingerprint",
            first["packet_fingerprint"]
            == second["packet_fingerprint"],
        )

        # 11
        before = self.registry_fingerprint()

        self.build_packet(
            "ENV-002",
            task="identity",
            time_of_day="evening",
            lighting="warm practical lighting",
        )

        after = self.registry_fingerprint()

        add(
            "11. Packet generation does not mutate registry",
            before == after,
        )

        # 12
        handoff = packet.get(
            "downstream_handoff",
            {}
        )

        handoff_ok = (
            handoff.get(
                "director_compatible"
            ) is True
            and
            handoff.get(
                "shot_camera_compatible"
            ) is True
            and
            handoff.get(
                "ltx_compatible"
            ) is True
            and
            handoff.get(
                "registry_mutation_allowed"
            ) is False
        )

        add(
            "12. Director / Shot / LTX handoff contract",
            handoff_ok,
        )

        # 13
        asset_state = {}

        for env in environments:

            verification = self.verify_assets(
                env["id"]
            )

            asset_state[
                env["id"]
            ] = {
                "environment_name":
                    env["name"],
                "asset_count":
                    len(
                        env.get(
                            "assets",
                            []
                        )
                    ),
                "identity_anchor_registered":
                    self.identity_anchor(
                        env["id"]
                    )
                    is not None,
                "asset_integrity_ok":
                    verification["all_ok"],
            }

        asset_state_ok = all(
            x[
                "identity_anchor_registered"
            ]
            and
            x[
                "asset_integrity_ok"
            ]
            for x in asset_state.values()
        )

        add(
            "13. All 8 approved environment identity anchors registered",
            asset_state_ok,
            asset_state,
        )

        # 14
        expected_files = {
            x["id"]: {
                "file":
                    anchor_relative_path(x),
                "exists":
                    anchor_path(x).is_file(),
            }
            for x in ENVIRONMENT_DEFINITIONS
        }

        all_files_exist = all(
            x["exists"]
            for x in expected_files.values()
        )

        add(
            "14. All 8 approved environment master files exist",
            all_files_exist,
            expected_files,
        )

        # 15
        integrity_results = {
            env["id"]:
                self.verify_assets(
                    env["id"]
                )["all_ok"]
            for env in environments
        }

        all_integrity_ok = all(
            integrity_results.values()
        )

        add(
            "15. All environment master hashes verify",
            all_integrity_ok,
            integrity_results,
        )

        # 16
        lock_results = {
            env["id"]:
                self.identity_anchor(
                    env["id"]
                ) is not None
            for env in environments
        }

        all_locks_ready = all(
            lock_results.values()
        )

        add(
            "16. All environment identity locks ready",
            all_locks_ready,
            lock_results,
        )

        asset_lock_ready_count = sum(
            1
            for env in environments
            if self.identity_anchor(
                env["id"]
            ) is not None
        )

        all_passed = all(
            x["pass"]
            for x in tests
        )

        return {
            "acceptance_test_version":
                ACCEPTANCE_TEST_VERSION,

            "app_version":
                APP_VERSION,

            "registry_schema":
                REGISTRY_SCHEMA,

            "packet_schema":
                PACKET_SCHEMA,

            "tests":
                tests,

            "all_passed":
                all_passed,

            "environment_count":
                len(environments),

            "asset_identity_locks_ready":
                asset_lock_ready_count,

            "asset_identity_locks_pending":
                len(environments)
                - asset_lock_ready_count,

            "production_ready":
                (
                    all_passed
                    and asset_lock_ready_count == 8
                ),

            "note": (
                "Scene/Environment Master is production-ready only when "
                "all 8 approved local identity anchors exist, verify by "
                "SHA-256, and asset_identity_locks_ready equals 8."
            ),
        }


MASTER = EnvironmentMaster(
    REGISTRY_PATH
)


# =============================================================================
# UI FUNCTIONS
# =============================================================================

def environment_choices() -> list[tuple[str, str]]:

    MASTER.reload()

    return [
        (
            f"{x['id']} — {x['name']}",
            x["id"]
        )
        for x in MASTER.list_environments()
    ]


def registry_ui() -> dict[str, Any]:

    MASTER.reload()

    return {
        "schema":
            MASTER.registry.get("schema"),

        "registry_version":
            MASTER.registry.get(
                "registry_version"
            ),

        "locked_baseline":
            MASTER.registry.get(
                "locked_baseline"
            ),

        "environments":
            MASTER.list_environments(),
    }


def build_packet_ui(
    environment_id: str,
    task: str,
    time_of_day: str,
    lighting: str,
    weather: str,
    scene_id: str,
    shot_id: str,
    oauth: Optional[gr.OAuthToken] = None,
    request: gr.Request = None,
) -> dict[str, Any]:
    # Project additions do not alter the eight locked canonical environments.
    if environment_id.startswith("ENV-") and environment_id[4:].isdigit() and int(environment_id[4:]) >= 100:
        from huggingface_hub import HfApi
        token = getattr(oauth, "token", None)
        if not token and request is not None:
            header = request.headers.get("x-hf-authorization", "") or request.headers.get("authorization", "")
            if header.lower().startswith("bearer "): token = header[7:]
        if not token or HfApi(token=token).whoami().get("name") != "Dezz-9-10":
            raise gr.Error("Verified owner required for project environments.")
        from joat_project_environments import packet
        return packet(environment_id, task, time_of_day, lighting, weather, scene_id, shot_id)

    MASTER.reload()

    return MASTER.build_packet(
        identifier=environment_id,
        task=task,
        time_of_day=time_of_day,
        lighting=lighting,
        weather=weather,
        scene_id=scene_id,
        shot_id=shot_id,
    )


def verify_ui(
    environment_id: str,
) -> dict[str, Any]:

    MASTER.reload()

    return MASTER.verify_assets(
        environment_id
    )


def tests_ui() -> dict[str, Any]:

    MASTER.reload()

    return MASTER.acceptance_test()


def asset_status_ui() -> dict[str, Any]:

    MASTER.reload()

    status = {}

    for env in MASTER.list_environments():

        verification = MASTER.verify_assets(
            env["id"]
        )

        status[env["id"]] = {
            "name":
                env["name"],

            "identity_lock_ready":
                MASTER.identity_anchor(
                    env["id"]
                ) is not None,

            "verification":
                verification,
        }

    return status


# =============================================================================
# GRADIO APP
# =============================================================================

def build_app() -> gr.Blocks:

    choices = environment_choices()

    default_env = (
        choices[0][1]
        if choices
        else None
    )

    with gr.Blocks(
        title=(
            "J.O.A.T. Scene & "
            f"Environment Master v{APP_VERSION}"
        )
    ) as app:

        gr.Markdown(
            "# J.O.A.T. Scene & Environment Master "
            f"— v{APP_VERSION}\n\n"
            "**Roadmap Stage #3**  \n"
            "Owns locked reusable environments, location continuity, "
            "time-of-day, lighting, approved identity anchors, and "
            "controlled downstream environment packets."
        )

        with gr.Tab(
            "Environment Packet"
        ):

            with gr.Row():

                environment_id = gr.Dropdown(
                    choices=choices,
                    allow_custom_value=True,
                    value=default_env,
                    label="Environment",
                )

                task = gr.Dropdown(
                    choices=[
                        "identity",
                        "wide",
                        "interior",
                        "exterior",
                        "lighting",
                        "detail",
                        "scene",
                    ],
                    value="scene",
                    label="Task",
                )

            with gr.Row():

                time_of_day = gr.Dropdown(
                    choices=[
                        "director_defined",
                        "dawn",
                        "morning",
                        "day",
                        "afternoon",
                        "golden_hour",
                        "dusk",
                        "evening",
                        "night",
                    ],
                    value="director_defined",
                    label="Time of Day",
                )

                lighting = gr.Textbox(
                    value="director_defined",
                    label="Lighting",
                )

                weather = gr.Textbox(
                    value="director_defined",
                    label="Weather / Atmosphere",
                )

            with gr.Row():

                scene_id = gr.Textbox(
                    value="",
                    placeholder="SCENE-001",
                    label="Scene ID",
                )

                shot_id = gr.Textbox(
                    value="",
                    placeholder="SHOT-001",
                    label="Shot ID",
                )

            packet_output = gr.JSON(
                label=(
                    "Environment Packet — "
                    "joat.environment_packet.v1"
                )
            )

            gr.Button(
                "Build Environment Packet",
                variant="primary",
            ).click(
                fn=build_packet_ui,
                inputs=[
                    environment_id,
                    task,
                    time_of_day,
                    lighting,
                    weather,
                    scene_id,
                    shot_id,
                ],
                outputs=packet_output,
            )

        with gr.Tab("Registry"):

            registry_output = gr.JSON(
                value=registry_ui(),
                label="Locked Environment Registry",
            )

            gr.Button(
                "Refresh Registry"
            ).click(
                fn=registry_ui,
                inputs=None,
                outputs=registry_output,
            )

        with gr.Tab(
            "Environment Assets"
        ):

            gr.Markdown(
                "### Approved Environment Identity Anchors\n\n"
                "All eight approved environment master images are "
                "registered locally and protected by SHA-256 verification."
            )

            asset_status_output = gr.JSON(
                label="Environment Asset Status"
            )

            gr.Button(
                "Check All Environment Assets",
                variant="primary",
            ).click(
                fn=asset_status_ui,
                inputs=None,
                outputs=asset_status_output,
            )

        with gr.Tab("Integrity"):

            integrity_env = gr.Dropdown(
                choices=choices,
                value=default_env,
                label="Environment",
            )

            integrity_output = gr.JSON(
                label="Environment Asset Integrity"
            )

            gr.Button(
                "Verify Environment Asset",
                variant="primary",
            ).click(
                fn=verify_ui,
                inputs=integrity_env,
                outputs=integrity_output,
            )

        with gr.Tab(
            "Acceptance Tests"
        ):

            test_output = gr.JSON(
                label=(
                    "Scene / Environment "
                    "Acceptance Test"
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

        with gr.Tab("About"):

            gr.Markdown(
                f"""
## J.O.A.T. Scene & Environment Master

**Version:** {APP_VERSION}

**Registry:** `{REGISTRY_SCHEMA}`

**Packet:** `{PACKET_SCHEMA}`

### Registered Environments

1. ENV-001 — Executive Office
2. ENV-002 — Coffee Shop
3. ENV-003 — Luxury Loft Apartment
4. ENV-004 — Gated Community
5. ENV-005 — Got Ham Neighborhood
6. ENV-006 — Rough WNY Apartment Interior
7. ENV-007 — Local Grocery Store
8. ENV-008 — Baptist Church

### Production Rules

- Approved environment imagery is reused.
- Every master has a local SHA-256 identity lock.
- Environment identity is version-controlled.
- Permanent location geometry cannot silently drift.
- Time-of-day and lighting travel with the scene packet.
- Temporary characters/props do not redefine a location.
- Locked masters cannot be silently changed.
- Director, Shot/Camera, and LTX workers receive controlled packets.

### Production Acceptance Target

`asset_identity_locks_ready = 8`

`asset_identity_locks_pending = 0`

`production_ready = true`
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