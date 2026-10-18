"""Shared lora library, stored in a Hugging Face storage bucket.

The list lives in `hf://buckets/<owner>/<bucket>/library.json` and holds two
sections, "normal" and "nsfw". Each entry keeps a name, the link, its trigger
words and a strength. A bucket is mutable object storage rather than a git
repo, so the file is simply overwritten on every change and survives a restart
of the Space.

Writing needs an `HF_TOKEN` with write access. When the bucket is mounted into
the Space as a volume, set `LORA_LIBRARY_DIR` to the mount path and the file is
read and written directly, with no token involved.

Used from app.py with a single line inside `with gr.Blocks(...) as demo:`

    lora_library.library_tab(lora_box=user_loras_text, prompt_box=prompt)

or, for a build with fixed lora slots,

    lora_library.library_tab(lora_slots=lora_refs, scale_slots=lora_scales,
                             prompt_box=prompt)
"""

from __future__ import annotations

import json
import os
import re
import time

import gradio as gr
import requests

BUCKET = os.environ.get("LORA_LIBRARY_BUCKET", "amisima/Krea-2-LoRAs")
LIBRARY_FILE = os.environ.get("LORA_LIBRARY_FILE", "library.json")
LOCAL_DIR = os.environ.get("LORA_LIBRARY_DIR", "").strip()
# Fallback for a Space whose huggingface_hub is too old to speak to buckets.
DATASET_REPO = os.environ.get("LORA_LIBRARY_REPO", BUCKET)
# Anyone holding this key may remove any entry. Set it in the Space secrets.
ADMIN_KEY = os.environ.get("LORA_LIBRARY_ADMIN_KEY", "").strip()

_OWNER_JS = """
() => {
  try {
    var k = window.localStorage.getItem('lora_library_owner_v1');
    if (!k) {
      k = 'u' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
      window.localStorage.setItem('lora_library_owner_v1', k);
    }
    return k;
  } catch (e) { return ''; }
}
"""

_CIVITAI_DOWNLOAD_RE = re.compile(r"/api/download/models/(\d+)")
_CIVITAI_PAGE_RE = re.compile(r"civitai\.(?:com|red)/models/(\d+)")
_CIVITAI_HOST_RE = re.compile(r"https?://(?:www\.)?(civitai\.(?:com|red))")

# version id -> model page url. Filled in as entries are looked at so a library
# of 50 loras does not hit the API 50 times on every refresh.
_CIVITAI_PAGE_CACHE: dict[str, str] = {}


def civitai_page_url(url: str, resolve: bool = True) -> str:
    """Model page for a civitai link.

    A download link (`/api/download/models/<versionId>`) says nothing about
    which model it belongs to, so the version has to be resolved through the
    API to get `modelId`. With `resolve=False` only links that are already a
    model page, or that were resolved earlier, come back — so redrawing a big
    library never blocks on the network. Returns "" when unknown.
    """
    url = (url or "").strip().strip('"').strip("'")
    if not url:
        return ""

    host_match = _CIVITAI_HOST_RE.match(url)
    if not host_match:
        return ""
    host = host_match.group(1)

    # Already a model page.
    if _CIVITAI_PAGE_RE.search(url):
        return url

    match = _CIVITAI_DOWNLOAD_RE.search(url)
    if not match:
        return ""
    version_id = match.group(1)
    if version_id in _CIVITAI_PAGE_CACHE:
        return _CIVITAI_PAGE_CACHE[version_id]
    if not resolve:
        return ""

    headers = {"User-Agent": "Mozilla/5.0"}
    token = os.environ.get("CIVITAI_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for api_host in (host, "civitai.com", "civitai.red"):
        try:
            response = requests.get(
                f"https://{api_host}/api/v1/model-versions/{version_id}",
                headers=headers, timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:  # noqa: BLE001
            continue
        model_id = data.get("modelId") or (data.get("model") or {}).get("id")
        if not model_id:
            continue
        page = f"https://{host}/models/{model_id}?modelVersionId={version_id}"
        _CIVITAI_PAGE_CACHE[version_id] = page
        return page

    _CIVITAI_PAGE_CACHE[version_id] = ""
    return ""


def _entry_page_url(item: dict, resolve: bool = False) -> str:
    """Model page for a library entry, preferring the one saved with it."""
    saved = (item.get("page") or "").strip()
    if saved:
        return saved
    return civitai_page_url(item.get("url") or "", resolve=resolve)


def _links_markdown(entries: list[dict], heading: str, resolve: bool = False) -> str:
    """A numbered list of 🔗 links matching the tick boxes above it."""
    rows, missing = [], 0
    for index, item in enumerate(entries, start=1):
        page = _entry_page_url(item, resolve=resolve)
        name = str(item.get("name") or "").strip() or f"lora {index}"
        if page:
            rows.append(f"{index}. [🔗 {name}]({page})")
        else:
            rows.append(f"{index}. {name}")
            missing += 1
    if not rows:
        return ""
    text = f"**{heading} — open the model page on civitai**  \n" + "  \n".join(rows)
    if missing:
        text += (
            f"  \n<sub>{missing} without a model page yet — press "
            "**🔗 fetch model links**.</sub>"
        )
    return text
_HF_URL_RE = re.compile(r"^https?://(?:www\.)?huggingface\.co/(?:datasets/)?([^/\s]+)/([^/\s?#]+)")


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------

def _token() -> str:
    return (os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN") or "").strip()


def _bucket_path() -> str:
    return f"buckets/{BUCKET.strip('/')}/{LIBRARY_FILE}"


_mount_cache: dict[str, str] = {}


def _runtime_volume_paths() -> list[str]:
    """Ask the Hub where this Space has its volumes mounted.

    A bucket attached in the Space settings lands at whatever mount path was
    typed in there, so guessing is hopeless. The plain REST endpoint is used
    rather than the Python client, because the client on an older Space does
    not know about volumes at all.
    """
    space_id = os.environ.get("SPACE_ID") or os.environ.get("SPACE_REPO_ID") or ""
    if not space_id:
        return []
    headers = {"User-Agent": "Mozilla/5.0"}
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(
            f"https://huggingface.co/api/spaces/{space_id}/runtime",
            headers=headers, timeout=20,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as error:  # noqa: BLE001
        print(f"[lora-library] could not read the Space runtime: "
              f"{type(error).__name__}: {error}", flush=True)
        return []

    wanted = BUCKET.strip("/").lower()
    preferred, others = [], []

    def walk(node):
        if isinstance(node, dict):
            mount = node.get("mountPath") or node.get("mount_path")
            if isinstance(mount, str) and mount.startswith("/"):
                source = str(node.get("source") or node.get("repoId") or "").strip("/").lower()
                (preferred if source.endswith(wanted) else others).append(mount)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return preferred + others


def _mount_table_paths() -> list[str]:
    """Mount points that look like an attached volume rather than the OS."""
    system = ("/proc", "/sys", "/dev", "/run", "/etc", "/usr", "/lib", "/bin",
              "/sbin", "/boot", "/var/lib", "/var/run")
    found = []
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) < 3:
                    continue
                point, fstype = parts[1], parts[2]
                if point == "/" or any(point.startswith(prefix) for prefix in system):
                    continue
                if fstype in ("nfs", "nfs4", "fuse", "virtiofs", "9p") or fstype.startswith("fuse"):
                    found.insert(0, point)
                elif point.count("/") == 1:
                    found.append(point)
    except Exception:  # noqa: BLE001
        return []
    return found


def _volume_mount_path() -> str:
    if "path" in _mount_cache:
        return str(_mount_cache["path"])
    _mount_cache["path"] = ""
    for path in _runtime_volume_paths() + _mount_table_paths():
        if path and os.path.isdir(path) and os.access(path, os.W_OK):
            _mount_cache["path"] = path
            print(f"[lora-library] using the volume mounted at {path}", flush=True)
            break
    return str(_mount_cache["path"])


def _mounted_file() -> str:
    """The library file on a locally mounted bucket, or "" when there is none."""
    bucket_name = BUCKET.strip("/").split("/")[-1]
    candidates = [LOCAL_DIR] if LOCAL_DIR else []
    candidates.append(_volume_mount_path())
    candidates += [
        f"/bucket/{bucket_name}", "/bucket",
        f"/buckets/{bucket_name}", "/buckets",
        f"/mnt/bucket/{bucket_name}", "/mnt/bucket",
        f"/data/{bucket_name}", "/data",
        f"/mnt/data/{bucket_name}", "/mnt/data",
        f"/storage/{bucket_name}", "/storage",
    ]
    for directory in candidates:
        if directory and os.path.isdir(directory) and os.access(directory, os.W_OK):
            return os.path.join(directory, LIBRARY_FILE)
    return ""


def _hub_has_buckets() -> bool:
    """Buckets need huggingface_hub 1.5 or newer; older Spaces have to fall back."""
    try:
        from huggingface_hub import HfFileSystem  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    try:
        from importlib.metadata import version as _version

        parts = _version("huggingface_hub").split(".")
        return (int(parts[0]), int(parts[1])) >= (1, 5)
    except Exception:  # noqa: BLE001
        return True


def _filesystem():
    from huggingface_hub import HfFileSystem

    token = _token()
    return HfFileSystem(token=token) if token else HfFileSystem()


def _empty() -> dict:
    return {"normal": [], "nsfw": []}


def _clean(data) -> dict:
    out = _empty()
    if not isinstance(data, dict):
        return out
    for section in ("normal", "nsfw"):
        for item in data.get(section) or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            try:
                strength = float(item.get("strength", 1.0))
            except (TypeError, ValueError):
                strength = 1.0
            try:
                low_strength = float(item.get("low_strength", strength))
            except (TypeError, ValueError):
                low_strength = strength
            out[section].append({
                "name": str(item.get("name") or "").strip() or url.split("/")[-1][:60],
                "url": url,
                "page": str(item.get("page") or "").strip(),
                "trigger": str(item.get("trigger") or "").strip(),
                "strength": strength,
                "high": str(item.get("high") or "").strip(),
                "low": str(item.get("low") or "").strip(),
                "low_strength": low_strength,
                "added": str(item.get("added") or ""),
                "owner": str(item.get("owner") or ""),
            })
    return out


def _may_delete(item: dict, owner: str) -> bool:
    owner = (owner or "").strip()
    if not owner:
        return False
    if ADMIN_KEY and owner == ADMIN_KEY:
        return True
    return bool(item.get("owner")) and item.get("owner") == owner


# Every backend is tried in turn, and whichever one answers is remembered so the
# reader and the writer never end up looking in two different places.
_active = {"backend": "", "detail": ""}


def _read_mounted():
    mounted = _mounted_file()
    if not mounted:
        return None
    if not os.path.exists(mounted):
        return _empty()
    with open(mounted, "r", encoding="utf-8") as handle:
        return _clean(json.load(handle))


def _write_mounted(payload: str) -> None:
    mounted = _mounted_file()
    if not mounted:
        raise RuntimeError("no mounted bucket")
    with open(mounted, "w", encoding="utf-8") as handle:
        handle.write(payload)


def _read_bucket():
    if not _hub_has_buckets():
        raise RuntimeError("huggingface_hub is too old for buckets (needs 1.5+)")
    filesystem = _filesystem()
    path = _bucket_path()
    if not filesystem.exists(path):
        return _empty()
    with filesystem.open(path, "r") as handle:
        return _clean(json.loads(handle.read()))


def _write_bucket(payload: str) -> None:
    if not _hub_has_buckets():
        raise RuntimeError("huggingface_hub is too old for buckets (needs 1.5+)")
    if not _token():
        raise RuntimeError("no HF_TOKEN")
    filesystem = _filesystem()
    with filesystem.open(_bucket_path(), "w") as handle:
        handle.write(payload)


def _read_dataset():
    url = (f"https://huggingface.co/datasets/{DATASET_REPO}/resolve/main/"
           f"{LIBRARY_FILE}?cb={int(time.time())}")
    headers = {"User-Agent": "Mozilla/5.0"}
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(url, headers=headers, timeout=25)
    if response.status_code == 404:
        return _empty()
    response.raise_for_status()
    return _clean(response.json())


def _write_dataset(payload: str) -> None:
    if not _token():
        raise RuntimeError("no HF_TOKEN")
    import io

    from huggingface_hub import HfApi

    api = HfApi(token=_token())
    api.create_repo(repo_id=DATASET_REPO, repo_type="dataset", exist_ok=True, private=True)
    api.upload_file(
        path_or_fileobj=io.BytesIO(payload.encode("utf-8")),
        path_in_repo=LIBRARY_FILE,
        repo_id=DATASET_REPO,
        repo_type="dataset",
        commit_message="update lora library",
    )


def _mounted_name() -> str:
    mounted = _mounted_file()
    return f"mounted bucket ({os.path.dirname(mounted)})" if mounted else "mounted bucket"


# ---------------------------------------------------------------------------
# buckets from a Space whose huggingface_hub is pinned below 1.5
# ---------------------------------------------------------------------------
# Some builds pin an old huggingface_hub on purpose (diffusers / ComfyUI
# compatibility) and upgrading it in place would break the Space. A modern copy
# is installed into a directory of its own and driven from a subprocess, so the
# running app never imports it.

_ISOLATED_DIR = os.environ.get("LORA_LIBRARY_HUB_DIR", "/tmp/lora_library_hub")
_isolated_state: dict[str, object] = {}


def _isolated_ready() -> bool:
    if "ok" in _isolated_state:
        return bool(_isolated_state["ok"])
    _isolated_state["ok"] = False
    if os.path.isdir(os.path.join(_ISOLATED_DIR, "huggingface_hub")):
        _isolated_state["ok"] = True
        return True
    print("[lora-library] installing a private huggingface_hub for bucket access…", flush=True)
    import subprocess
    import sys

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--quiet",
             "--target", _ISOLATED_DIR, "huggingface_hub>=1.5"],
            check=True, timeout=600,
        )
        _isolated_state["ok"] = os.path.isdir(os.path.join(_ISOLATED_DIR, "huggingface_hub"))
    except Exception as error:  # noqa: BLE001
        print(f"[lora-library] private huggingface_hub install failed: "
              f"{type(error).__name__}: {error}", flush=True)
    return bool(_isolated_state["ok"])


def _isolated_run(mode: str, payload_path: str = "") -> str:
    import subprocess
    import sys

    if not _isolated_ready():
        raise RuntimeError("could not install a huggingface_hub new enough for buckets")
    script = (
        "import sys, json, os\n"
        f"sys.path.insert(0, {_ISOLATED_DIR!r})\n"
        "from huggingface_hub import HfFileSystem\n"
        "token = os.environ.get('HF_TOKEN') or os.environ.get('HUGGINGFACE_HUB_TOKEN') or None\n"
        "fs = HfFileSystem(token=token)\n"
        f"path = {_bucket_path()!r}\n"
        f"mode = {mode!r}\n"
        f"payload_path = {payload_path!r}\n"
        "if mode == 'read':\n"
        "    if fs.exists(path):\n"
        "        with fs.open(path, 'r') as handle:\n"
        "            sys.stdout.write(handle.read())\n"
        "    else:\n"
        "        sys.stdout.write('{}')\n"
        "else:\n"
        "    with open(payload_path, 'r', encoding='utf-8') as handle:\n"
        "        body = handle.read()\n"
        "    with fs.open(path, 'w') as handle:\n"
        "        handle.write(body)\n"
        "    sys.stdout.write('ok')\n"
    )
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=180, env=environment,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "").strip().splitlines()[-1:] or "subprocess failed")
    return result.stdout


def _read_isolated():
    return _clean(json.loads(_isolated_run("read") or "{}"))


def _write_isolated(payload: str) -> None:
    import tempfile

    if not _token():
        raise RuntimeError("no HF_TOKEN")
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    handle.write(payload)
    handle.close()
    try:
        _isolated_run("write", handle.name)
    finally:
        os.unlink(handle.name)


_BACKENDS = [
    ("mounted bucket", _read_mounted, _write_mounted),
    (f"bucket {BUCKET}", _read_bucket, _write_bucket),
    (f"bucket {BUCKET} (private hub)", _read_isolated, _write_isolated),
    (f"dataset {DATASET_REPO}", _read_dataset, _write_dataset),
]


def load_library() -> dict:
    """Read from the backend that last worked, or find one that does."""
    ordered = _BACKENDS
    if _active["backend"]:
        ordered = ([b for b in _BACKENDS if b[0] == _active["backend"]]
                   + [b for b in _BACKENDS if b[0] != _active["backend"]])
    first_error = ""
    for name, reader, _writer in ordered:
        try:
            data = reader()
        except Exception as error:  # noqa: BLE001
            first_error = first_error or f"{name}: {type(error).__name__}: {error}"
            print(f"[lora-library] read from {name} failed: {error}", flush=True)
            continue
        if data is None:
            continue
        if data["normal"] or data["nsfw"] or not _active["backend"]:
            _active["backend"], _active["detail"] = name, ""
        return data
    _active["detail"] = first_error
    return _empty()


def save_library(library: dict) -> str:
    """Write, then read back to prove it landed. Returns "" or a message."""
    payload = json.dumps(_clean(library), ensure_ascii=False, indent=1)
    wanted = {item["url"] for item in _clean(library)["normal"] + _clean(library)["nsfw"]}

    problems = []
    for name, reader, writer in _BACKENDS:
        try:
            writer(payload)
        except Exception as error:  # noqa: BLE001
            problems.append(f"{name}: {type(error).__name__}: {error}")
            continue
        try:
            written = reader() or _empty()
        except Exception as error:  # noqa: BLE001
            problems.append(f"{name}: written, but could not be read back ({error})")
            continue
        got = {item["url"] for item in written["normal"] + written["nsfw"]}
        if wanted - got:
            problems.append(f"{name}: written, but it did not come back")
            continue
        _active["backend"], _active["detail"] = name, ""
        return ""

    detail = "; ".join(problems) or "no storage backend is available"
    _active["detail"] = detail
    return (f"**nothing was saved.** {detail}\n\n"
            f"Easiest fix: attach the `{BUCKET}` bucket to this Space under "
            "*Settings → Storage Buckets* (any mount path will do) — then no token is needed "
            "at all. Otherwise add an `HF_TOKEN` with write access under "
            "*Settings → Variables and secrets*.")


def storage_note() -> str:
    if _active["backend"] and not _active["detail"]:
        name = _mounted_name() if _active["backend"] == "mounted bucket" else _active["backend"]
        return f"storage: {name}"
    if _active["detail"]:
        return f"storage: not working yet — {_active['detail']}"
    return "storage: not contacted yet"


# ---------------------------------------------------------------------------
# reading a link
# ---------------------------------------------------------------------------

def lookup_link(url: str):
    """(name, trigger words) for a civitai / huggingface link."""
    url = (url or "").strip().strip('"').strip("'")
    if not url:
        return "", ""

    match = _CIVITAI_DOWNLOAD_RE.search(url)
    if match:
        headers = {"User-Agent": "Mozilla/5.0"}
        civitai_token = os.environ.get("CIVITAI_TOKEN", "").strip()
        if civitai_token:
            headers["Authorization"] = f"Bearer {civitai_token}"
        for host in ("civitai.red", "civitai.com"):
            try:
                response = requests.get(
                    f"https://{host}/api/v1/model-versions/{match.group(1)}",
                    headers=headers, timeout=20,
                )
                response.raise_for_status()
                data = response.json()
            except Exception:  # noqa: BLE001
                continue
            model_name = (data.get("model") or {}).get("name") or ""
            version_name = data.get("name") or ""
            label = f"{model_name} · {version_name}".strip(" ·")
            model_id = data.get("modelId") or (data.get("model") or {}).get("id")
            if model_id:
                page_host = "civitai.red" if "civitai.red" in url else "civitai.com"
                _CIVITAI_PAGE_CACHE[match.group(1)] = (
                    f"https://{page_host}/models/{model_id}?modelVersionId={match.group(1)}"
                )
            words = [w for w in (data.get("trainedWords") or []) if w]
            return label, ", ".join(words[:8])
        return "", ""

    hf_match = _HF_URL_RE.match(url)
    if hf_match:
        return f"{hf_match.group(1)}/{hf_match.group(2)}", ""

    return url.split("?")[0].split("/")[-1], ""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _labels(entries: list[dict], owner: str = "") -> list[str]:
    labels = []
    for index, item in enumerate(entries, start=1):
        mark = "🟢" if _may_delete(item, owner) else "🔒"
        label = f"{mark} {index}. {item['name']}  ·  strength {item['strength']:g}"
        if item.get("trigger"):
            label += f"  ·  trigger: {item['trigger']}"
        labels.append(label[:220])
    return labels


def _picked(entries: list[dict], labels: list[str], chosen) -> list[dict]:
    index_by_label = {label: i for i, label in enumerate(labels)}
    out = []
    for label in chosen or []:
        index = index_by_label.get(label)
        if index is not None and index < len(entries):
            out.append(entries[index])
    return out


def _autofind(predicate):
    try:
        from gradio.context import Context

        root = getattr(Context, "root_block", None)
        if root is None:
            return None
        for component in root.blocks.values():
            if isinstance(component, gr.Textbox):
                label = str(getattr(component, "label", "") or "")
                if predicate(label.lower()):
                    return component
    except Exception:  # noqa: BLE001
        return None
    return None


def _is_lora_box(label: str) -> bool:
    return "lora" in label and "search" not in label and "civitai" not in label


def _is_prompt_box(label: str) -> bool:
    if "prompt" not in label:
        return False
    return not any(word in label for word in
                   ("negative", "segment", "relay", "scene", "enhance", "search"))


def _with_triggers(prompt_text: str, triggers: list[str]) -> str:
    text = prompt_text or ""
    missing = [t for t in triggers if t and t.lower() not in text.lower()]
    if not missing:
        return text
    return f"{text.rstrip().rstrip(',')}, {', '.join(missing)}".strip(" ,")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def library_tab(lora_box=None, prompt_box=None, lora_slots=None, scale_slots=None,
                pair_slots=None, label: str = "📚 lora library"):
    """Draw the library tab. Hand it either a multi-line lora textbox
    (`lora_box`), a list of fixed slots (`lora_slots` + `scale_slots`), or a
    list of high/low pairs (`pair_slots`), each one a tuple of
    (repo, high, high_strength, low, low_strength)."""
    pairs = [tuple(p) for p in (pair_slots or [])]
    slots = [] if pairs else list(lora_slots or [])
    scales = [] if pairs else list(scale_slots or [])
    if not pairs and not slots and lora_box is None:
        lora_box = _autofind(_is_lora_box)
    if prompt_box is None:
        prompt_box = _autofind(_is_prompt_box)

    has_pairs = bool(pairs)
    has_slots = (not has_pairs) and bool(slots)
    has_box = (not has_pairs) and (not has_slots) and lora_box is not None
    has_prompt = prompt_box is not None

    library = load_library()

    with gr.Tab(label):
        gr.Markdown(
            f"a shared list, kept in the `{BUCKET}` bucket, so it survives a restart. "
            "tick what you want and it goes straight into the lora "
            + ("slots" if (has_slots or has_pairs) else "box") + ", trigger words and all.  \n"
            "🟢 = added by you, so you can remove it. 🔒 = somebody else's, and "
            "only they can remove it."
        )

        state = gr.State(library)
        normal_labels = gr.State(_labels(library["normal"]))
        nsfw_labels = gr.State(_labels(library["nsfw"]))

        with gr.Accordion("📋 ordinary", open=False):
            normal_pick = gr.CheckboxGroup(
                choices=_labels(library["normal"]), value=[],
                label="ordinary", show_label=False, interactive=True,
            )
            with gr.Accordion("🔗 the links", open=False):
                normal_links = gr.Markdown(_links_markdown(library["normal"], "ordinary"))

        with gr.Accordion("🔞 nsfw", open=False):
            nsfw_pick = gr.CheckboxGroup(
                choices=_labels(library["nsfw"]), value=[],
                label="nsfw", show_label=False, interactive=True,
            )
            with gr.Accordion("🔗 the links", open=False):
                nsfw_links = gr.Markdown(_links_markdown(library["nsfw"], "nsfw"))

        with gr.Row():
            add_button = gr.Button(
                "➕ add the ticked ones to the lora "
                + ("slots" if (has_slots or has_pairs) else "box"),
                variant="primary",
            )
            refresh_button = gr.Button("🔄 refresh")
            links_button = gr.Button("🔗 fetch model links")

        use_triggers = gr.Checkbox(
            value=True, label="append the trigger words to the prompt",
        )
        status = gr.Markdown("")
        storage_line = gr.Markdown(storage_note())

        with gr.Accordion("➕ add a lora to the library", open=False):
            new_url = gr.Textbox(label="link (civitai / huggingface / direct .safetensors)", lines=1)
            lookup_button = gr.Button("🔎 read the name and triggers off the link")
            new_name = gr.Textbox(label="name", lines=1)
            new_trigger = gr.Textbox(label="trigger words", lines=1)
            if has_pairs:
                with gr.Row():
                    new_high = gr.Textbox(label="high file (optional)", lines=1)
                    new_low = gr.Textbox(label="low file (optional)", lines=1)
                with gr.Row():
                    new_strength = gr.Number(value=1.0, label="high strength", precision=2)
                    new_low_strength = gr.Number(value=1.0, label="low strength", precision=2)
                new_nsfw = gr.Checkbox(value=False, label="nsfw")
            else:
                new_high = gr.Textbox(value="", visible=False)
                new_low = gr.Textbox(value="", visible=False)
                with gr.Row():
                    new_strength = gr.Number(value=1.0, label="strength", precision=2)
                    new_nsfw = gr.Checkbox(value=False, label="nsfw")
                new_low_strength = gr.Number(value=1.0, visible=False)
            save_button = gr.Button("💾 save to the library", variant="primary")

        with gr.Accordion("🗑 remove", open=False):
            gr.Markdown(
                "you can only remove the entries **you** added — those are the 🟢 ones. "
                "🔒 belongs to somebody else and is left alone."
            )
            delete_button = gr.Button("remove the ticked ones that are mine")

        with gr.Accordion("🔑 my key", open=False):
            owner_box = gr.Textbox(
                value="", label="this browser's key", lines=1,
                info="made automatically and kept in this browser. copy it into "
                     "another browser to keep ownership of what you added.",
            )

        # ------------------------------------------------------------ events

        def _pack(data, message, owner=""):
            normal = _labels(data["normal"], owner)
            nsfw = _labels(data["nsfw"], owner)
            return (
                data, normal, nsfw,
                gr.update(choices=normal, value=[]),
                gr.update(choices=nsfw, value=[]),
                message,
                storage_note(),
                _links_markdown(data["normal"], "ordinary"),
                _links_markdown(data["nsfw"], "nsfw"),
            )

        def _refresh(owner=""):
            data = load_library()
            return _pack(data, f"loaded: {len(data['normal'])} ordinary, "
                               f"{len(data['nsfw'])} nsfw", owner)

        refresh_targets = [state, normal_labels, nsfw_labels, normal_pick, nsfw_pick,
                           status, storage_line, normal_links, nsfw_links]
        refresh_button.click(_refresh, [owner_box], refresh_targets)
        owner_box.change(_refresh, [owner_box], refresh_targets)

        def _fetch_links(owner=""):
            """Resolve every download link to its model page and write the
            result back, so it is looked up once and then kept."""
            data = load_library()
            resolved = 0
            for section in ("normal", "nsfw"):
                for item in data[section]:
                    if (item.get("page") or "").strip():
                        continue
                    page = civitai_page_url(item.get("url") or "", resolve=True)
                    if page:
                        item["page"] = page
                        resolved += 1
            message = f"model links found: {resolved}" if resolved else "nothing new to look up."
            if resolved:
                error = save_library(data)
                if error:
                    message = f"{message} (not saved — {error})"
                else:
                    data = load_library()
            return _pack(data, message, owner)

        links_button.click(_fetch_links, [owner_box], refresh_targets)

        lookup_button.click(lambda url: lookup_link(url), new_url, [new_name, new_trigger])

        def _save(data, url, name, trigger, strength, nsfw, high="", low="",
                  low_strength=None, owner=""):
            url = (url or "").strip().strip('"').strip("'")
            owner = (owner or "").strip()
            # Start from what storage actually holds, so two people adding a lora
            # at the same time do not overwrite each other.
            data = load_library()
            if not url:
                return _pack(data, "paste a link first.", owner)
            for existing in data["normal"] + data["nsfw"]:
                if existing["url"] == url:
                    return _pack(data, f"already on the list: {existing['name']}", owner)
            if not (name or "").strip():
                name = lookup_link(url)[0] or url.split("?")[0].split("/")[-1]
            try:
                strength = float(strength)
            except (TypeError, ValueError):
                strength = 1.0
            try:
                low_strength = float(low_strength)
            except (TypeError, ValueError):
                low_strength = strength
            data["nsfw" if nsfw else "normal"].append({
                "name": name.strip(),
                "url": url,
                "page": civitai_page_url(url),
                "trigger": (trigger or "").strip(),
                "strength": strength,
                "high": (high or "").strip(),
                "low": (low or "").strip(),
                "low_strength": low_strength,
                "added": time.strftime("%Y-%m-%d"),
                "owner": owner,
            })
            error = save_library(data)
            # Show what came back out of storage, not what went in.
            return _pack(load_library() if not error else data,
                         error or f"added and saved: {name.strip()}", owner)

        save_button.click(
            _save,
            [state, new_url, new_name, new_trigger, new_strength, new_nsfw,
             new_high, new_low, new_low_strength, owner_box],
            refresh_targets,
        )

        def _delete(data, normal, nsfw, normal_chosen, nsfw_chosen, owner=""):
            data = _clean(data)
            owner = (owner or "").strip()
            chosen = (_picked(data["normal"], normal, normal_chosen)
                      + _picked(data["nsfw"], nsfw, nsfw_chosen))
            if not chosen:
                return _pack(data, "nothing is ticked.", owner)
            if not owner:
                return _pack(data, "no key for this browser, so nothing can be "
                                   "removed. open **🔑 my key** and paste yours in.", owner)

            fresh = load_library()
            by_url = {}
            for section in ("normal", "nsfw"):
                for item in fresh[section]:
                    by_url[item["url"]] = item

            doomed, refused = set(), []
            for item in chosen:
                current = by_url.get(item["url"], item)
                if _may_delete(current, owner):
                    doomed.add(item["url"])
                else:
                    refused.append(current.get("name") or item["url"])

            if not doomed:
                return _pack(fresh, "none of those are yours, so nothing was "
                                    f"removed: {', '.join(refused)}", owner)

            for section in ("normal", "nsfw"):
                fresh[section] = [i for i in fresh[section] if i["url"] not in doomed]
            error = save_library(fresh)
            message = error or f"removed: {len(doomed)}"
            if not error and refused:
                message += f"  \nleft alone (not yours): {', '.join(refused)}"
            return _pack(load_library() if not error else data, message, owner)

        delete_button.click(
            _delete,
            [state, normal_labels, nsfw_labels, normal_pick, nsfw_pick, owner_box],
            refresh_targets,
        )

        # ------------------------------------------- adding to high/low pairs

        if has_pairs:
            flat_pairs = [component for row in pairs for component in row]
            add_inputs = [state, normal_labels, nsfw_labels, normal_pick, nsfw_pick, use_triggers]
            add_outputs = [status]
            if has_prompt:
                add_inputs.append(prompt_box)
                add_outputs.append(prompt_box)
            add_outputs = add_outputs + flat_pairs

            def _add_pairs(data, normal, nsfw, normal_chosen, nsfw_chosen, triggers_on,
                           prompt_text=""):
                data = _clean(data)
                chosen = (_picked(data["normal"], normal, normal_chosen)
                          + _picked(data["nsfw"], nsfw, nsfw_chosen))
                blank = [gr.update() for _ in flat_pairs]
                if not chosen:
                    return tuple(["nothing is ticked."]
                                 + ([gr.update()] if has_prompt else []) + blank)

                used = chosen[:len(pairs)]
                spare = chosen[len(pairs):]

                updates = []
                for index in range(len(pairs)):
                    if index >= len(used):
                        updates += [gr.update() for _ in pairs[index]]
                        continue
                    item = used[index]
                    high_file = item.get("high") or ""
                    low_file = item.get("low") or ""
                    row = [gr.update(value=item["url"])]
                    row.append(gr.update(choices=["(None)", high_file], value=high_file)
                               if high_file else gr.update())
                    row.append(gr.update(value=item["strength"]))
                    row.append(gr.update(choices=["(None)", low_file], value=low_file)
                               if low_file else gr.update())
                    row.append(gr.update(value=item.get("low_strength", item["strength"])))
                    # A slot may have fewer than five components; keep them lined up.
                    updates += row[:len(pairs[index])]
                    updates += [gr.update() for _ in range(len(pairs[index]) - len(row))]

                message = f"**in the slots:** {', '.join(i['name'] for i in used)}"
                if any(not (i.get("high") or i.get("low")) for i in used):
                    message += ("  \nno file names were saved for some of them — press "
                                "**📥 Load files** in the slot to fill the High/Low boxes.")
                if spare:
                    message += (f"  \nno room for: {', '.join(i['name'] for i in spare)} "
                                f"(there are {len(pairs)} slots)")
                trigger_words = [i["trigger"] for i in used if i.get("trigger")]

                out = [message]
                if has_prompt:
                    out.append(gr.update(value=_with_triggers(prompt_text, trigger_words))
                               if triggers_on and trigger_words else gr.update())
                elif trigger_words:
                    out[0] += f"  \n**trigger words for the prompt:** {', '.join(trigger_words)}"
                return tuple(out + updates)

            add_button.click(_add_pairs, add_inputs, add_outputs)

        # ------------------------------------------- adding to the lora slots

        elif has_slots:
            add_inputs = [state, normal_labels, nsfw_labels, normal_pick, nsfw_pick, use_triggers]
            add_outputs = [status]
            if has_prompt:
                add_inputs.append(prompt_box)
                add_outputs.append(prompt_box)
            add_outputs = add_outputs + slots + scales

            def _add_slots(data, normal, nsfw, normal_chosen, nsfw_chosen, triggers_on,
                           prompt_text=""):
                data = _clean(data)
                chosen = (_picked(data["normal"], normal, normal_chosen)
                          + _picked(data["nsfw"], nsfw, nsfw_chosen))
                blank = [gr.update() for _ in slots] + [gr.update() for _ in scales]
                if not chosen:
                    return tuple(["nothing is ticked."]
                                 + ([gr.update()] if has_prompt else []) + blank)

                used = chosen[:len(slots)]
                spare = chosen[len(slots):]
                ref_updates = [
                    gr.update(value=used[i]["url"]) if i < len(used) else gr.update()
                    for i in range(len(slots))
                ]
                scale_updates = [
                    gr.update(value=used[i]["strength"]) if i < len(used) else gr.update()
                    for i in range(len(scales))
                ]

                message = f"**in the slots:** {', '.join(i['name'] for i in used)}"
                if spare:
                    message += (f"  \nno room for: {', '.join(i['name'] for i in spare)} "
                                f"(there are {len(slots)} slots)")
                trigger_words = [i["trigger"] for i in used if i.get("trigger")]

                out = [message]
                if has_prompt:
                    out.append(gr.update(value=_with_triggers(prompt_text, trigger_words))
                               if triggers_on and trigger_words else gr.update())
                elif trigger_words:
                    out[0] += f"  \n**trigger words for the prompt:** {', '.join(trigger_words)}"
                return tuple(out + ref_updates + scale_updates)

            add_button.click(_add_slots, add_inputs, add_outputs)

        # --------------------------------------------- adding to the lora box

        else:
            add_inputs = [state, normal_labels, nsfw_labels, normal_pick, nsfw_pick, use_triggers]
            add_outputs = [status]
            if has_box:
                add_inputs.append(lora_box)
                add_outputs.append(lora_box)
            if has_prompt:
                add_inputs.append(prompt_box)
                add_outputs.append(prompt_box)

            def _add_box(data, normal, nsfw, normal_chosen, nsfw_chosen, triggers_on, *boxes):
                data = _clean(data)
                chosen = (_picked(data["normal"], normal, normal_chosen)
                          + _picked(data["nsfw"], nsfw, nsfw_chosen))

                position = 0
                lora_text = boxes[position] if has_box else ""
                if has_box:
                    position += 1
                prompt_text = boxes[position] if has_prompt else ""

                if not chosen:
                    out = ["nothing is ticked."]
                    out += [gr.update()] * (int(has_box) + int(has_prompt))
                    return tuple(out) if len(out) > 1 else out[0]

                text = (lora_text or "").rstrip()
                added, skipped, trigger_words = [], [], []
                for item in chosen:
                    if item["url"] in text:
                        skipped.append(item["name"])
                    else:
                        text = f"{text}\n{item['url']} | {item['strength']:g}".strip()
                        added.append(item["name"])
                    if item.get("trigger"):
                        trigger_words.append(item["trigger"])

                message = ""
                if added:
                    message += f"**added:** {', '.join(added)}"
                if skipped:
                    message += f"  \nalready in the box: {', '.join(skipped)}"
                if trigger_words and not has_prompt:
                    message += f"  \n**trigger words for the prompt:** {', '.join(trigger_words)}"
                if not has_box:
                    lines = "\n".join(f"{i['url']} | {i['strength']:g}" for i in chosen)
                    message = f"copy these lines into the lora box:\n\n```\n{lines}\n```\n\n{message}"

                out = [message]
                if has_box:
                    out.append(gr.update(value=text))
                if has_prompt:
                    out.append(gr.update(value=_with_triggers(prompt_text, trigger_words))
                               if triggers_on and trigger_words else gr.update())
                return tuple(out) if len(out) > 1 else out[0]

            add_button.click(_add_box, add_inputs, add_outputs)

        try:
            from gradio.context import Context

            root = getattr(Context, "root_block", None)
            if root is not None:
                event = None
                for keyword in ("js", "_js"):
                    try:
                        event = root.load(None, None, [owner_box], **{keyword: _OWNER_JS})
                        break
                    except TypeError:
                        continue
                if event is not None and hasattr(event, "then"):
                    event.then(_refresh, [owner_box], refresh_targets)
                else:
                    root.load(_refresh, [owner_box], refresh_targets)
        except Exception:  # noqa: BLE001
            try:
                root.load(_refresh, [owner_box], refresh_targets)
            except Exception:  # noqa: BLE001
                pass

    return state
