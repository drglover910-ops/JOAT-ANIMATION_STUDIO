"""J.O.A.T. MSR output isolation v1.0.7; no model, asset, or creative changes."""
PATCH_VERSION = "1.0.7"

class JOATGeneratedVideoLatent:
    RETURN_TYPES = ("LATENT",)
    FUNCTION = "isolate_generated_video"
    CATEGORY = "J.O.A.T./render integrity"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"latent": ("LATENT",),
                             "output_frames": ("INT", {"default":145, "min":9, "max":1001})}}

    def isolate_generated_video(self, latent, output_frames):
        # LTX temporal VAE: N pixel frames = 8*(N_latent-1)+1.
        # Core LTXVAddGuide/IC-LoRA append reference latents to the END.
        # Base generation length is explicitly set before guide injection.
        if isinstance(output_frames, bool) or not isinstance(output_frames, int):
            raise ValueError("MSR output frame count must be an integer")
        if output_frames < 9 or output_frames > 1001 or (output_frames-1)%8:
            raise ValueError("MSR output frame count must lie on the LTX 8n+1 grid")
        count = (output_frames-1)//8+1
        samples = latent["samples"]
        if len(samples.shape) != 5 or samples.shape[2] < count:
            raise ValueError("MSR generated video latent is missing or shorter than requested")
        out = dict(latent)
        out["samples"] = samples[:, :, :count]
        mask = latent.get("noise_mask")
        if mask is not None:
            if len(mask.shape) != 5 or (mask.shape[2] != 1 and mask.shape[2] < count):
                raise ValueError("MSR video noise mask does not match the generated latent")
            out["noise_mask"] = mask if mask.shape[2] == 1 else mask[:, :, :count]
        return (out,)


def register_msr_output_node(mappings):
    mappings["JOATGeneratedVideoLatent"] = JOATGeneratedVideoLatent
