import json
import subprocess
import sys
from pathlib import Path

import gradio as gr
from character_master import CharacterAssetMaster


APP_VERSION = "1.2.0"
ACCEPTANCE_TEST_VERSION = "1.1.1"

ROOT = Path(__file__).resolve().parent
METADATA_SCRIPT = ROOT / "generate_character_metadata.py"
GENERATED_METADATA_PATH = ROOT / "generated_character_metadata.json"

master = CharacterAssetMaster()


def chars():
    master.reload()
    return master.list_characters()


def packet(cid, task):
    master.reload()
    return master.build_ltx_packet(cid, task)


def verify(cid):
    master.reload()
    return master.verify_assets(cid)


def test():
    master.reload()
    return master.acceptance_test()


def generate_character_metadata():
    if not METADATA_SCRIPT.exists():
        return {
            "success": False,
            "app_version": APP_VERSION,
            "error": "generate_character_metadata.py not found",
        }

    try:
        result = subprocess.run(
            [sys.executable, str(METADATA_SCRIPT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "app_version": APP_VERSION,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        if not GENERATED_METADATA_PATH.exists():
            return {
                "success": False,
                "app_version": APP_VERSION,
                "error": (
                    "Metadata generator completed but "
                    "generated_character_metadata.json "
                    "was not created."
                ),
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        metadata = json.loads(
            GENERATED_METADATA_PATH.read_text(
                encoding="utf-8"
            )
        )

        return {
            "success": True,
            "app_version": APP_VERSION,
            "metadata": metadata,
        }

    except Exception as exc:
        return {
            "success": False,
            "app_version": APP_VERSION,
            "error": repr(exc),
        }


character_ids = [
    x["id"] for x in master.list_characters()
]

default_character = (
    character_ids[0]
    if character_ids
    else None
)


with gr.Blocks(
    title=f"J.O.A.T. Character & Asset Master v{APP_VERSION}"
) as demo:

    gr.Markdown(
        f"# J.O.A.T. Character & Asset Master — v{APP_VERSION}\n"
        "**Locked baseline worker.** Owns character "
        "identity/reference assets and hands controlled "
        "packets to Director / Studio Operations. "
        "It does not modify the LTX core."
    )

    with gr.Tab("Character Packet"):
        cid = gr.Dropdown(
            choices=character_ids,
            value=default_character,
            label="Character",
        )

        task = gr.Dropdown(
            choices=[
                "identity",
                "full_body",
                "profile",
                "back",
                "wardrobe",
                "interaction",
                "pose",
                "scene",
            ],
            value="identity",
            label="Task",
        )

        out = gr.JSON(
            label="LTX-ready character packet"
        )

        gr.Button(
            "Build Packet",
            variant="primary",
        ).click(
            packet,
            inputs=[cid, task],
            outputs=out,
        )

    with gr.Tab("Registry"):
        reg = gr.JSON(
            value=chars(),
            label="Approved characters",
        )

        gr.Button(
            "Refresh Registry"
        ).click(
            chars,
            inputs=None,
            outputs=reg,
        )

    with gr.Tab("Integrity"):
        vo = gr.JSON(
            label="Asset integrity results"
        )

        gr.Button(
            "Verify Selected Character Assets",
            variant="primary",
        ).click(
            verify,
            inputs=cid,
            outputs=vo,
        )

    with gr.Tab("Metadata Generator"):
        gr.Markdown(
            "### CHAR-003 through CHAR-007\n"
            "Reads the committed character images and "
            "calculates their filenames, repository paths, "
            "SHA-256 hashes, widths and heights.\n\n"
            "**This does not modify `characters.json`.**"
        )

        metadata_output = gr.JSON(
            label="Generated Character Metadata"
        )

        gr.Button(
            "Generate Character Metadata",
            variant="primary",
        ).click(
            generate_character_metadata,
            inputs=None,
            outputs=metadata_output,
        )

    with gr.Tab("Acceptance Test"):
        to = gr.JSON(
            label="Acceptance test results"
        )

        gr.Button(
            f"Run v{ACCEPTANCE_TEST_VERSION} Acceptance Test",
            variant="primary",
        ).click(
            test,
            inputs=None,
            outputs=to,
        )


if __name__ == "__main__":
    demo.launch()