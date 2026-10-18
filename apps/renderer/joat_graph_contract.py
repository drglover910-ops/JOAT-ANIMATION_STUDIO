"""J.O.A.T. CPU-only MSR graph contract; file version 1.0.2.

Inspects the registered node schemas and injected API graph. It does not run
nodes, allocate a GPU, load models, inspect pixels, or approve generated media.
"""

import math

FILE_VERSION = "1.0.2"

_EXPECTED_OUTPUTS = {
    "LiconMSR": ("IMAGE",),
    "LTXAddVideoICLoRAGuide": ("CONDITIONING", "CONDITIONING", "LATENT"),
    "LTXVAddGuideMulti": ("CONDITIONING", "CONDITIONING", "LATENT"),
    "JOATGeneratedVideoLatent": ("LATENT",),
    "EmptyLTXVLatentVideo": ("LATENT",),
    "LTXVConcatAVLatent": ("LATENT",),
    "LTXVSeparateAVLatent": ("LATENT", "LATENT"),
    "VAEDecode": ("IMAGE",),
    "LTXVEmptyLatentAudio": ("LATENT",),
    "LTXVConditioning": ("CONDITIONING", "CONDITIONING"),
    "LoadImage": ("IMAGE", "MASK"),
    "LTXICLoRALoaderModelOnly": ("MODEL", "FLOAT"),
}


def _fail(message):
    raise RuntimeError("MSR graph preflight: " + message)


def _is_link(value):
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and isinstance(value[0], str) and type(value[1]) is int)


def _registered(mappings, class_type):
    cls = mappings.get(class_type)
    if cls is None:
        _fail("required node is not registered: " + class_type)
    try:
        schema = cls.INPUT_TYPES()
        outputs = tuple(cls.RETURN_TYPES)
    except Exception as exc:
        _fail("cannot inspect registered schema for " + class_type
              + " (" + type(exc).__name__ + ")")
    if not isinstance(schema, dict):
        _fail("invalid INPUT_TYPES schema for " + class_type)
    expected = _EXPECTED_OUTPUTS.get(class_type)
    if expected is not None and outputs[:len(expected)] != expected:
        _fail("incompatible output types for " + class_type)
    return cls, schema, outputs


def _input_specs(schema, values, class_type):
    required = dict(schema.get("required", {}))
    optional = dict(schema.get("optional", {}))
    for name, spec in list(required.items()) + list(optional.items()):
        if not isinstance(spec, (tuple, list)) or not spec:
            _fail("invalid input schema for " + class_type + "." + name)
        if spec[0] != "COMFY_DYNAMICCOMBO_V3":
            continue
        options = spec[1].get("options", []) if len(spec) > 1 and isinstance(spec[1], dict) else []
        chosen = next((option for option in options
                       if isinstance(option, dict) and option.get("key") == values.get(name)), None)
        if chosen is None:
            _fail("unsupported dynamic option for " + class_type + "." + name)
        inner = chosen.get("inputs", {})
        if not isinstance(inner, dict):
            _fail("invalid dynamic schema for " + class_type + "." + name)
        for inner_name, inner_spec in inner.get("required", {}).items():
            required[name + "." + inner_name] = inner_spec
        for inner_name, inner_spec in inner.get("optional", {}).items():
            optional[name + "." + inner_name] = inner_spec
    return required, {**required, **optional}


def _validate_literal(value, spec, label):
    kind = spec[0]
    metadata = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if isinstance(kind, str) and "," in kind:
        # V3 MultiType inputs serialize accepted types as e.g. "FLOAT,INT".
        # Validate each allowed literal type with the same numeric bounds.
        for member in kind.split(","):
            try:
                _validate_literal(value, (member.strip(), metadata), label)
                return
            except RuntimeError:
                pass
        _fail("literal does not match allowed input types for " + label)
    if isinstance(kind, (list, tuple)):
        if value not in kind:
            _fail("unsupported option for " + label)
    elif kind == "COMBO":
        # Comfy v3 exposes dropdowns as ("COMBO", {"options": [...]});
        # classic nodes expose the options directly in the first tuple slot.
        options = metadata.get("options")
        if not isinstance(options, (list, tuple)) or not options:
            _fail("dropdown options are unavailable for " + label)
        if value not in options:
            _fail("unsupported option for " + label)
    elif kind in ("INT", "FLOAT"):
        valid = type(value) is int if kind == "INT" else type(value) in (int, float)
        if not valid or not math.isfinite(value):
            _fail("invalid numeric input for " + label)
        if "min" in metadata and value < metadata["min"]:
            _fail("numeric input is below schema minimum for " + label)
        if "max" in metadata and value > metadata["max"]:
            _fail("numeric input is above schema maximum for " + label)
    elif kind == "BOOLEAN" and type(value) is not bool:
        _fail("invalid boolean input for " + label)
    elif kind == "STRING" and not isinstance(value, str):
        _fail("invalid string input for " + label)
    elif kind not in ("COMFY_DYNAMICCOMBO_V3", "INT", "FLOAT", "BOOLEAN", "STRING", "*"):
        _fail("required connection is missing for " + label)


def validate_msr_graph(workflow, mappings, width, height, frames, *, check_image_choices=True):
    """Validate the actual MSR graph against installed CPU node schemas.

    Classic INPUT_TYPES and Comfy v3's compatible INPUT_TYPES are supported;
    v3 DynamicCombo selected inputs are expanded into their API dotted names.
    Return only dimensions, counts, registered types, and version information.
    """
    if not isinstance(workflow, dict) or not isinstance(mappings, dict):
        _fail("workflow and node mappings must be dictionaries")
    if any(type(value) is not int for value in (width, height, frames)):
        _fail("dimensions and frame count must be integers")
    if width < 64 or height < 64 or width % 32 or height % 32:
        _fail("dimensions must lie on the LTX spatial grid")
    if frames < 9 or frames > 1001 or (frames - 1) % 8:
        _fail("frame count must lie on the LTX temporal grid")

    expected_nodes = {
        "534": "EmptyLTXVLatentVideo", "548": "LTXVConcatAVLatent",
        "596": "LTXVSeparateAVLatent", "740": "VAEDecode",
        "597": "VHS_VideoCombine", "msr_pseudo": "LiconMSR",
        "msr_guide": "LTXAddVideoICLoRAGuide",
        "msr_guide_multi": "LTXVAddGuideMulti",
        "msr_crop": "JOATGeneratedVideoLatent",
    }
    for node_id, class_type in expected_nodes.items():
        node = workflow.get(node_id, {})
        if node.get("class_type") != class_type:
            _fail("missing or incompatible graph node: " + node_id)
    selected = set(expected_nodes)
    selected.update(node_id for node_id, node in workflow.items()
                    if node_id.startswith("msr_") or node.get("class_type") in
                    ("LTXVEmptyLatentAudio", "LTXVConditioning"))
    checked_types = set()
    output_cache = {}
    for node_id in sorted(selected):
        node = workflow[node_id]
        class_type = node.get("class_type", "")
        cls, schema, outputs = _registered(mappings, class_type)
        output_cache[class_type] = outputs
        checked_types.add(class_type)
        values = node.get("inputs", {})
        if not isinstance(values, dict):
            _fail("invalid graph inputs for " + class_type)
        required, specs = _input_specs(schema, values, class_type)
        for name in required:
            if name not in values:
                _fail("required input is missing: " + class_type + "." + name)
        for name, value in values.items():
            if name not in specs:
                # Comfy ignores auxiliary API keys such as LoadImage.upload.
                continue
            spec = specs[name]
            label = class_type + "." + name
            if _is_link(value):
                source_id, slot = value
                source = workflow.get(source_id)
                if source is None or slot < 0:
                    _fail("connection source is missing for " + label)
                source_type = source.get("class_type", "")
                if source_type not in output_cache:
                    output_cache[source_type] = _registered(mappings, source_type)[2]
                source_outputs = output_cache[source_type]
                if slot >= len(source_outputs):
                    _fail("connection output slot is invalid for " + label)
                kind = spec[0]
                if isinstance(kind, str):
                    accepted = {part.strip() for part in kind.split(",")}
                    actual = {part.strip() for part in str(source_outputs[slot]).split(",")}
                    if "*" not in accepted | actual and not accepted.intersection(actual):
                        _fail("connection type is incompatible for " + label)
            else:
                if class_type == "LoadImage" and name == "image" and not check_image_choices:
                    if not isinstance(value, str) or not value:
                        _fail("invalid image placeholder for " + label)
                elif class_type == "LiconMSR" and name == "frame_count" and type(value) is int and isinstance(spec[0], (list, tuple)):
                    # Licon's dropdown lists text, but VALIDATE_INPUTS and
                    # create_video both call int(frame_count). Preserve the
                    # renderer's integer and check its exact listed equivalent.
                    _validate_literal(str(value), spec, label)
                else:
                    _validate_literal(value, spec, label)
        if class_type == "JOATGeneratedVideoLatent":
            if cls.__name__ != "JOATGeneratedVideoLatent" or getattr(cls, "FUNCTION", None) != "isolate_generated_video":
                _fail("generated-output node registration differs from the installed helper")

    def expect(node_id, name, value):
        if workflow[node_id].get("inputs", {}).get(name) != value:
            _fail("unexpected production wiring or literal: " + node_id + "." + name)

    expect("534", "width", width)
    expect("534", "height", height)
    expect("534", "length", frames)
    expect("msr_pseudo", "width", width)
    expect("msr_pseudo", "height", height)
    expect("msr_guide_multi", "positive", ["msr_guide", 0])
    expect("msr_guide_multi", "negative", ["msr_guide", 1])
    expect("msr_guide_multi", "latent", ["msr_guide", 2])
    expect("548", "video_latent", ["msr_guide_multi", 2])
    expect("msr_crop", "latent", ["596", 0])
    expect("msr_crop", "output_frames", frames)
    expect("740", "samples", ["msr_crop", 0])
    expect("597", "frame_rate", 24)

    guide_count_text = workflow["msr_guide_multi"]["inputs"].get("num_guides")
    if not isinstance(guide_count_text, str) or not guide_count_text.isdigit():
        _fail("invalid per-image guide count")
    guide_count = int(guide_count_text)
    if not 1 <= guide_count <= 20:
        _fail("per-image guide count is outside the supported range")
    multi_inputs = workflow["msr_guide_multi"]["inputs"]
    expected_dynamic_names = {"num_guides." + name + str(index)
                              for index in range(1, guide_count + 1)
                              for name in ("image_", "frame_idx_", "strength_")}
    if {name for name in multi_inputs if name.startswith("num_guides.")} != expected_dynamic_names:
        _fail("selected DynamicCombo guide inputs differ from the declared count")
    for index in range(1, guide_count + 1):
        for name in ("image_", "frame_idx_", "strength_"):
            if "num_guides." + name + str(index) not in multi_inputs:
                _fail("selected DynamicCombo guide inputs are incomplete")
    conditioning_consumed = set()
    for node_id, node in workflow.items():
        for name, value in node.get("inputs", {}).items():
            if node_id != "msr_guide_multi" and value in (["msr_guide", 0], ["msr_guide", 1]):
                _fail("conditioning skips per-image guide metadata: " + node_id + "." + name)
            if value == ["msr_guide_multi", 0]:
                conditioning_consumed.add(0)
            elif value == ["msr_guide_multi", 1]:
                conditioning_consumed.add(1)
        if node.get("class_type") == "LTXVEmptyLatentAudio":
            expect(node_id, "frames_number", frames)
            expect(node_id, "frame_rate", 24)
        elif node.get("class_type") == "LTXVConditioning":
            expect(node_id, "frame_rate", 24)
    if conditioning_consumed != {0, 1}:
        _fail("per-image guide conditioning does not reach the sampling graph")

    # Detect cycles in dependencies of the production output, without executing.
    active, visited = set(), set()
    def visit(node_id):
        if node_id in active:
            _fail("production output contains a dependency cycle")
        if node_id in visited:
            return
        node = workflow.get(node_id)
        if node is None:
            _fail("production output has a missing dependency")
        active.add(node_id)
        for value in node.get("inputs", {}).values():
            if _is_link(value):
                visit(value[0])
        active.remove(node_id)
        visited.add(node_id)
    visit("597")
    reachable_conditioning = set()
    for node_id in visited:
        for value in workflow[node_id].get("inputs", {}).values():
            if value == ["msr_guide_multi", 0]:
                reachable_conditioning.add(0)
            elif value == ["msr_guide_multi", 1]:
                reachable_conditioning.add(1)
    if reachable_conditioning != {0, 1}:
        _fail("per-image guide conditioning does not reach the production output")
    return {"schema": "joat.msr_graph_preflight.v1", "file_version": FILE_VERSION,
            "status": "passed", "gpu_called": False, "width": width,
            "height": height, "output_frames": frames,
            "generated_latent_frames": (frames - 1) // 8 + 1,
            "per_image_guide_count": guide_count,
            "checked_node_count": len(selected), "checked_node_types": sorted(checked_types),
            "conditioning_metadata_chain_verified": True,
            "image_file_choices_checked": bool(check_image_choices),
            "scope": "registered schemas and graph only; generated media remains unverified"}
