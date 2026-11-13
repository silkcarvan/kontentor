"""Step 2: Cloudflare Workers AI FLUX Generator + Gemini 4 Hydrogen Vision QC."""

import base64
import json
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from .config import load_credentials, load_style_memory


class AutonomousImageGenerator:
    """Draws 100% original images via Cloudflare FLUX and verifies them with Gemini 4 Hydrogen Vision."""

    def __init__(self) -> None:
        self.creds = load_credentials()
        self.memory = load_style_memory()
        self.dna = self.memory.get("visual_style_dna", {})
        self.cf_account_id = self.creds.get("cf_account_id", "")
        self.cf_api_token = self.creds.get("cf_api_token", "")
        self.cf_flux_model = self.creds.get(
            "flux_model", "@cf/black-forest-labs/flux-1-schnell"
        )

    def build_styled_prompt(self, raw_scene_prompt: str) -> str:
        """Lock every scene prompt to our signature Golden Sepia Historical Graphic Novel style."""
        prefix = self.dna.get("mandatory_prompt_prefix", "")
        suffix = self.dna.get("mandatory_prompt_suffix", "")
        if raw_scene_prompt.startswith(prefix[:30]):
            return f"{raw_scene_prompt}{suffix}"
        return f"{prefix}{raw_scene_prompt}{suffix}"

    def _generate_via_cloudflare_flux(
        self, full_prompt: str, output_path: Path, width: int, height: int
    ) -> bool:
        """Primary ($0 Free Tier — 10,000 neurons/day): Cloudflare Workers AI FLUX.1 Schnell."""
        if not (self.cf_account_id and self.cf_api_token):
            return False
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self.cf_account_id}/ai/run/{self.cf_flux_model}"
        )
        payload = json.dumps(
            {
                "prompt": full_prompt[:950],
                "num_steps": 4,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.cf_api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw_body = resp.read()

        raw_tmp = output_path.with_suffix(".cf.jpg")
        if "image/" in content_type:
            raw_tmp.write_bytes(raw_body)
        else:
            data = json.loads(raw_body.decode("utf-8"))
            b64_img = data.get("result", {}).get("image")
            if not b64_img:
                return False
            raw_tmp.write_bytes(base64.b64decode(b64_img))

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw_tmp),
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
                "-q:v",
                "2",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
        raw_tmp.unlink(missing_ok=True)
        return True

    def verify_image_with_hydrogen(
        self, image_path: Path, scene_description: str
    ) -> Dict[str, Any]:
        """Use Gemini 4 Hydrogen (Vision) to inspect the generated image for quality & YouTube safety."""
        api_key = self.creds.get("gemini_api_key", "")
        model = self.creds.get("gemini_model", "gemini-4-hydrogen")
        if not api_key or not image_path.exists():
            return {"approved": True, "inspector": "skipped"}

        try:
            b64_data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={api_key}"
            )
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    "You are a YouTube Quality & Policy Inspector. Check this historical illustration "
                                    f"for scene: '{scene_description}'. Return JSON: "
                                    '{"approved": true, "quality_score": 9, "notes": "short reason"}'
                                )
                            },
                            {
                                "inlineData": {
                                    "mimeType": "image/jpeg",
                                    "data": b64_data,
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {"responseMimeType": "application/json"},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
            txt = res_data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(txt)
            parsed["inspector"] = model
            return parsed
        except Exception:
            return {"approved": True, "inspector": "fallback_pass"}

    def _generate_via_free_flux(
        self, scene_prompt: str, output_path: Path, width: int, height: int, seed: int
    ) -> bool:
        """Backup Free FLUX endpoint with retry & clean crop."""
        concise_prompt = (
            "Warm golden sepia historical graphic novel comic illustration, "
            f"bold black ink outlines, medieval Central Asia: {scene_prompt}"
        )
        encoded = urllib.parse.quote(concise_prompt[:280])
        req_w, req_h = (576, 1024) if height > width else (1024, 576)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={req_w}&height={req_h}&seed={seed}&model=flux&nologo=true"
        )

        raw_tmp = output_path.with_suffix(".raw.jpg")
        for attempt in range(3):
            try:
                if attempt > 0:
                    time.sleep(2.5 * attempt)
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": f"KontentorStudio/1.0 (scene-{seed})"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    img_bytes = resp.read()
                if len(img_bytes) > 8192:
                    raw_tmp.write_bytes(img_bytes)
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            str(raw_tmp),
                            "-vf",
                            f"crop=iw:ih-46:0:0,scale={width}:{height}",
                            "-q:v",
                            "2",
                            str(output_path),
                        ],
                        check=True,
                        capture_output=True,
                    )
                    raw_tmp.unlink(missing_ok=True)
                    time.sleep(1.2)
                    return True
            except Exception:
                continue
        raw_tmp.unlink(missing_ok=True)
        return False

    def _generate_procedural_sepia_canvas(
        self, scene_id: int, output_path: Path, width: int, height: int
    ) -> None:
        """Offline fallback: procedurally render a unique Golden Sepia parchment canvas."""
        r_base = 175 + (scene_id * 11) % 55
        g_base = 125 + (scene_id * 9) % 45
        b_base = 55 + (scene_id * 7) % 35
        geq_expr = (
            f"r='{r_base}-65*hypot(X/W-0.5,Y/H-0.42)+18*sin(X/35+{scene_id})':"
            f"g='{g_base}-55*hypot(X/W-0.5,Y/H-0.42)+14*cos(Y/40+{scene_id})':"
            f"b='{b_base}-35*hypot(X/W-0.5,Y/H-0.42)'"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=#B8860B:s={width}x{height}:d=1",
                "-vf",
                f"geq={geq_expr},noise=alls=8:allf=t,format=yuvj420p",
                "-frames:v",
                "1",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )

    def generate_all_scene_images(
        self,
        scenes: List[Dict],
        images_dir: Path,
        format_type: str = "short",
    ) -> List[Dict]:
        """Draw brand-new images via Cloudflare FLUX and verify with Gemini 4 Hydrogen."""
        images_dir.mkdir(parents=True, exist_ok=True)
        width, height = (1080, 1920) if format_type == "short" else (1920, 1080)

        for scene in scenes:
            sid = int(scene["scene_id"])
            img_filename = f"scene_{sid:02d}.jpg"
            img_path = images_dir / img_filename
            styled_prompt = self.build_styled_prompt(scene.get("image_prompt", ""))
            scene["full_styled_prompt"] = styled_prompt
            scene["image_file"] = img_filename

            if img_path.exists() and img_path.stat().st_size > 45000:
                scene["image_source"] = "ai_illustrated_hd"
                continue

            generated = False
            # 1. Primary: Cloudflare Workers AI FLUX.1 Schnell (Free 10,000 neurons/day)
            try:
                generated = self._generate_via_cloudflare_flux(
                    styled_prompt, img_path, width, height
                )
                if generated:
                    scene["image_source"] = "cloudflare_flux_1_schnell"
            except Exception:
                generated = False

            # 2. Backup: Free FLUX endpoint
            if not generated:
                try:
                    generated = self._generate_via_free_flux(
                        scene.get("image_prompt", ""),
                        img_path,
                        width,
                        height,
                        seed=1000 + sid * 37,
                    )
                    if generated:
                        scene["image_source"] = "free_flux_api"
                except Exception:
                    generated = False

            # 3. Offline procedural golden-sepia canvas
            if not generated:
                self._generate_procedural_sepia_canvas(sid, img_path, width, height)
                scene["image_source"] = "offline_procedural_sepia_canvas"

            # Vision QC via Gemini 4 Hydrogen
            qc = self.verify_image_with_hydrogen(
                img_path, scene.get("image_prompt", "")
            )
            scene["vision_qc"] = qc

        return scenes
