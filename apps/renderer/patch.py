import re, pathlib, shutil

p = pathlib.Path("app.py")
src = p.read_text(encoding="utf-8")
shutil.copy2(p, "app.py.bak")
n = 0

# --- FIX 1: _make_prefix_subclass връща речник вместо клас ---
bad = "        _prefix_cls_cache[base_cls] = _RefPrefixedTimestep\n        return _prefix_cls_cache"
good = "        _prefix_cls_cache[base_cls] = _RefPrefixedTimestep\n        return _RefPrefixedTimestep"
if bad in src:
    src = src.replace(bad, good, 1)
    n += 1
    print("fix1 ok")
else:
    print("fix1 SKIP (вече е оправено или не съвпада)")

# --- FIX 2: UI компоненти за character face ---
anchor = 'image = gr.Image(label="🖼️ reference image", type="filepath", height=280)'
ui = anchor + '''
                identity_image = gr.Image(
                    label="🔒 character face (същото лице във всички клипове)",
                    type="filepath",
                    height=200,
                )
                identity_prompt_lock = gr.Checkbox(
                    value=True,
                    label="добавяй identity lock към промпта автоматично",
                )
                gr.Markdown(
                    "чист портрет анфас. **Continue the scene не го пипа** — "
                    "сменя се само reference image. празно = старо поведение.",
                    elem_classes="consent-note",
                )'''
if "identity_image = gr.Image(" not in src and anchor in src:
    src = src.replace(anchor, ui, 1)
    n += 1
    print("fix2 ok")
else:
    print("fix2 SKIP")

# --- FIX 3: добави ги в _GENERATE_INPUTS ---
tail = "            profile_name,\n            skip_refine,\n            user_loras_text,\n    ]"
tail_new = ("            profile_name,\n            skip_refine,\n            user_loras_text,\n"
            "            identity_image,\n            identity_prompt_lock,\n    ]")
if "identity_image,\n            identity_prompt_lock," not in src and tail in src:
    src = src.replace(tail, tail_new, 1)
    n += 1
    print("fix3 ok")
else:
    print("fix3 SKIP")

p.write_text(src, encoding="utf-8")
print(f"\nготово: {n}/3 промени. бекъп: app.py.bak")