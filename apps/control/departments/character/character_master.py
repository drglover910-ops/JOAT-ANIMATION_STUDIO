from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "characters.json"


class CharacterAssetMaster:
    def __init__(self, registry_path: Path = REGISTRY_PATH):
        self.registry_path = Path(registry_path)
        self.reload()

    def reload(self):
        self.data = json.loads(
            self.registry_path.read_text(encoding="utf-8")
        )
        return self.data

    def list_characters(self):
        return [
            {
                "id": c["id"],
                "name": c["name"],
                "version": c["version"],
                "status": c["status"],
            }
            for c in self.data["characters"]
        ]

    def get_character(self, character_id: str):
        for c in self.data["characters"]:
            if (
                c["id"] == character_id
                or character_id.lower()
                in [a.lower() for a in c.get("aliases", [])]
            ):
                return c

        raise KeyError(f"Unknown character: {character_id}")

    def verify_assets(self, character_id: str):
        c = self.get_character(character_id)
        results = []

        for a in c["assets"]:
            p = ROOT / a["path"]
            ok = p.exists()

            actual = (
                hashlib.sha256(p.read_bytes()).hexdigest()
                if ok
                else None
            )

            results.append(
                {
                    "asset_id": a["asset_id"],
                    "exists": ok,
                    "hash_match": (
                        actual == a["sha256"]
                        if ok
                        else False
                    ),
                    "actual_sha256": actual,
                }
            )

        return {
            "character_id": c["id"],
            "all_ok": all(
                r["exists"] and r["hash_match"]
                for r in results
            ),
            "results": results,
        }

    def select_assets(
        self,
        character_id: str,
        task: str = "identity",
        max_assets: int = 3,
    ):
        c = self.get_character(character_id)

        priorities = c["selection_policy"].get(
            task,
            c["selection_policy"]["identity"],
        )

        ranked = []

        for role in priorities:
            ranked += [
                a
                for a in c["assets"]
                if role in a["roles"] and a not in ranked
            ]

        return ranked[:max_assets]

    def build_ltx_packet(
        self,
        character_id: str,
        task: str = "identity",
    ):
        c = self.get_character(character_id)

        chosen = self.select_assets(
            character_id,
            task,
            3,
        )

        anchor = next(
            (
                a
                for a in chosen
                if "identity_anchor" in a["roles"]
            ),
            chosen[0],
        )

        return {
            "schema": "joat.character_packet.v1",
            "character_id": c["id"],
            "character_name": c["name"],
            "character_version": c["version"],
            "identity_locked": True,
            "identity_lock_asset": anchor["path"],
            "supporting_reference_assets": [
                a["path"]
                for a in chosen
                if a is not anchor
            ],
            "appearance_rules": c["appearance_rules"],
            "continuity_rules": c["continuity_rules"],
            "negative_rules": c["negative_rules"],
            "source_asset_hashes": {
                a["asset_id"]: a["sha256"]
                for a in chosen
            },
            "approval": {
                "live_change_allowed": False,
                "requires_human_approval_for_registry_mutation": True,
            },
        }

    def acceptance_test(self):
        """
        J.O.A.T. Character Asset Master
        Acceptance Test v1.1.1

        Tests every character registered in characters.json.
        """

        tests = []

        def check(name, fn):
            try:
                v = fn()

                tests.append(
                    {
                        "test": name,
                        "pass": bool(v),
                        "detail": v,
                    }
                )

            except Exception as e:
                tests.append(
                    {
                        "test": name,
                        "pass": False,
                        "detail": repr(e),
                    }
                )

        # GLOBAL REGISTRY GATE

        check(
            "registry loads",
            lambda: bool(
                self.data.get("characters")
            ),
        )

        # TEST EVERY REGISTERED CHARACTER

        for c in self.data.get("characters", []):
            cid = c["id"]
            name = c["name"]

            expected_assets = c.get(
                "asset_count",
                len(c.get("assets", [])),
            )

            # Character resolves

            check(
                f"{cid} resolves",
                lambda cid=cid, name=name:
                    self.get_character(cid)["name"]
                    == name,
            )

            # Every alias resolves

            for alias in c.get("aliases", []):
                check(
                    f'{cid} alias "{alias}" resolves',
                    lambda alias=alias, cid=cid:
                        self.get_character(alias)["id"]
                        == cid,
                )

            # Correct asset count

            check(
                f"{cid} has {expected_assets} registered assets",
                lambda cid=cid,
                expected_assets=expected_assets:
                    len(
                        self.get_character(cid)["assets"]
                    )
                    == expected_assets,
            )

            # Every file exists and SHA-256 matches

            check(
                f"{cid} all files + hashes verify",
                lambda cid=cid:
                    self.verify_assets(cid)["all_ok"],
            )

            # Identity anchor selected

            check(
                f"{cid} identity anchor selected",
                lambda cid=cid:
                    "identity_anchor"
                    in self.select_assets(
                        cid,
                        "identity",
                        1,
                    )[0]["roles"],
            )

            # LTX packet identity lock

            check(
                f"{cid} LTX packet locks identity",
                lambda cid=cid:
                    self.build_ltx_packet(cid)
                    ["identity_locked"]
                    is True,
            )

            # Registry mutation requires approval

            check(
                f"{cid} registry mutation approval gate",
                lambda cid=cid:
                    self.build_ltx_packet(cid)
                    ["approval"]
                    [
                        "requires_human_approval_for_registry_mutation"
                    ]
                    is True,
            )

        # FINAL ACCEPTANCE RESULT

        return {
            "acceptance_test_version": "1.1.1",

            "passed": all(
                t["pass"]
                for t in tests
            ),

            "characters_tested": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "version": c["version"],
                    "asset_count": c.get(
                        "asset_count",
                        len(
                            c.get(
                                "assets",
                                [],
                            )
                        ),
                    ),
                }
                for c in self.data.get(
                    "characters",
                    [],
                )
            ],

            "tests": tests,
        }