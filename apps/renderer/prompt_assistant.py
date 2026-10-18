"""Shared remote prompt-writer selection; no model weights or credentials here."""
from __future__ import annotations

import os

FABLE = "qwen-fable"
# Filled with the duplicated Space when it is supplied; environment override is optional.
DEFAULT_FABLE_SPACE = "amisima/Qwen3.8-Fable"


def assistant_choices(qwen_space):
    return [("Qwen3.8 · Original", qwen_space),
            ("Qwen3.8 · Fable", FABLE)]


def is_fable(writer):
    value = str(writer or "").strip().lower()
    configured = os.environ.get("QWEN_FABLE_SPACE", DEFAULT_FABLE_SPACE).strip().lower()
    for prefix in ("https://huggingface.co/spaces/", "http://huggingface.co/spaces/"):
        if value.startswith(prefix):
            value = value[len(prefix):].strip("/")
        if configured.startswith(prefix):
            configured = configured[len(prefix):].strip("/")
    return value == FABLE or value.startswith(FABLE + ":") or "fable" in value or bool(configured and value == configured)


def supports_images(writer):
    # Both offered Qwen models accept images; never silently strip attachments.
    return True


def resolve_writer(writer):
    value = str(writer or "").strip()
    if value.lower() == FABLE:
        value = os.environ.get("QWEN_FABLE_SPACE", DEFAULT_FABLE_SPACE).strip()
        if not value:
            raise ValueError(
                "Qwen Fable is not connected yet. Set QWEN_FABLE_SPACE to the "
                "owner/name of your Fable vision Space. No AI request was sent."
            )
    elif value.lower().startswith(FABLE + ":"):
        value = value.split(":", 1)[1].strip()
    if not value:
        raise ValueError("Choose a writing Space before preparing a prompt. No AI request was sent.")
    if value.lower() == FABLE or value.lower().startswith(FABLE + ":"):
        raise ValueError("QWEN_FABLE_SPACE must be a Space address such as owner/name.")
    for prefix in ("https://huggingface.co/spaces/", "http://huggingface.co/spaces/"):
        if value.startswith(prefix):
            value = value[len(prefix):].strip("/")
            break
    return value


def prepare_request(writer, message, image=None):
    target = resolve_writer(writer)
    return target, message, image


def _reply_text(result):
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        if result.get("role") in ("user", "system", "tool"):
            return ""
        if (result.get("metadata") or {}).get("title"):
            return ""
        return _reply_text(result.get("content", result.get("text", "")))
    if isinstance(result, (tuple, list)):
        if result and all(isinstance(item, dict) and "role" in item for item in result):
            for item in reversed(result):
                if item.get("role") == "assistant":
                    text = _reply_text(item)
                    if text:
                        return text
            return ""
        if result and all(isinstance(item, (tuple, list)) and len(item) == 2 for item in result):
            return _reply_text(result[-1][1])
        if result and all(isinstance(item, dict) and item.get("type") == "text" for item in result):
            return "\n".join(_reply_text(item) for item in result).strip()
        for item in reversed(result):
            text = _reply_text(item)
            if text:
                return text
    return ""


def writer_result(result):
    """Reject incomplete JSON/prompt output, supporting existing Gradio chat APIs."""
    if isinstance(result, (tuple, list)) and len(result) == 1:
        return writer_result(result[0])
    if isinstance(result, dict) and result.get("protocol") == "h3-writer-v1":
        if result.get("finish_reason") != "stop":
            raise ValueError(
                "The writer returned an incomplete answer "
                f"({result.get('finish_reason', 'unknown')}; "
                f"{result.get('generated_tokens', '?')}/{result.get('max_new_tokens', '?')} tokens). "
                "No automatic retry was submitted."
            )
        text = str(result.get("text") or "").strip()
    else:
        def cut_off(value):
            if isinstance(value, dict):
                title = str((value.get("metadata") or {}).get("title", "")).lower()
                return "cut off" in title or "truncated" in title or cut_off(value.get("content"))
            return isinstance(value, (tuple, list)) and any(cut_off(item) for item in value)
        if cut_off(result):
            raise ValueError("The writer reported a truncated answer. No automatic retry was submitted.")
        text = _reply_text(result)
    if not text:
        raise ValueError("The writer returned no final answer. No automatic retry was submitted.")
    return text
