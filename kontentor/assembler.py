"""Step 4: Automatic Video Assembler with YouTube Shorts Safe-Zone Dynamic Subtitles."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List

from .subtitle_renderer import (
    export_srt,
    render_subtitle_banner_png,
    split_narration_into_phrases,
)


class VideoAssembler:
    """Assembles historical frames, mastered voiceovers, Ken Burns motion, and safe-zone subtitles."""

    def __init__(self, fps: int = 30) -> None:
        self.fps = fps

    def _build_zoompan_filter(
        self, motion: str, duration: float, width: int, height: int
    ) -> str:
        """Build smooth FFmpeg zoompan expression for all camera motions."""
        frames = max(1, int(round(duration * self.fps)))
        if motion == "zoom_out":
            z_expr = f"if(eq(on,1),1.20,max(1.0,zoom-0.20/{frames}))"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion == "pan_right":
            z_expr = "1.16"
            x_expr = f"(iw-iw/zoom)*(on/{frames})"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion == "pan_left":
            z_expr = "1.16"
            x_expr = f"(iw-iw/zoom)*(1-on/{frames})"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion == "tilt_up":
            z_expr = "1.16"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = f"(ih-ih/zoom)*(1-on/{frames})"
        else:  # default zoom_in
            z_expr = f"min(zoom+0.20/{frames},1.20)"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"

        return (
            f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
            f"crop={width * 2}:{height * 2},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
            f"d={frames}:s={width}x{height}:fps={self.fps}"
        )

    def render_scene_clip(
        self,
        scene: Dict[str, Any],
        image_path: Path,
        audio_path: Path,
        clip_dir: Path,
        width: int = 1080,
        height: int = 1920,
    ) -> Path:
        """Render a single scene with Ken Burns motion and YouTube Shorts Safe-Zone dynamic subtitles."""
        sid = int(scene["scene_id"])
        duration = float(scene["duration"])
        motion = scene.get("motion", "zoom_in")
        narration = scene.get("narration") or scene.get("subtitle", "")

        # YouTube Shorts Safe Zone (clear of right-side Like/Comment bar & bottom Profile/Title)
        if height > width:
            banner_w = 720
            banner_h = 148
            overlay_x = 135  # Leaves 225px clear on right side for YouTube Like/Comment buttons
            overlay_y = 1130  # 790px above bottom, completely clear of Channel Profile & Title
        else:
            banner_w = 1100
            banner_h = 148
            overlay_x = (width - banner_w) // 2
            overlay_y = height - banner_h - 90

        phrases = split_narration_into_phrases(narration, duration)
        banner_inputs: List[str] = []
        filter_parts: List[str] = []

        zp_filter = self._build_zoompan_filter(motion, duration, width, height)
        filter_parts.append(f"[0:v]{zp_filter},format=yuv420p[v0]")

        for p_idx, (p_text, t_start, t_end) in enumerate(phrases, start=1):
            p_png = clip_dir / f"sub_{sid:02d}_p{p_idx}.png"
            render_subtitle_banner_png(p_text, p_png, width=banner_w, height=banner_h)
            banner_inputs.extend(["-loop", "1", "-i", str(p_png)])
            prev_tag = f"v{p_idx - 1}"
            next_tag = f"v{p_idx}"
            filter_parts.append(
                f"[{prev_tag}][{p_idx}:v]overlay={overlay_x}:{overlay_y}:"
                f"enable='between(t,{t_start:.2f},{t_end:.2f})':shortest=1[{next_tag}]"
            )

        final_v_tag = f"[{f'v{len(phrases)}'}]"
        audio_input_idx = len(phrases) + 1
        out_clip = clip_dir / f"clip_{sid:02d}.mp4"

        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            *banner_inputs,
            "-i",
            str(audio_path),
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            final_v_tag,
            "-map",
            f"{audio_input_idx}:a",
            "-t",
            f"{duration:.3f}",
            "-r",
            str(self.fps),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(out_clip),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_clip

    def assemble_video(
        self,
        scenes: List[Dict[str, Any]],
        images_dir: Path,
        work_dir: Path,
        output_mp4: Path,
        format_type: str = "short",
    ) -> Dict[str, Any]:
        """Assemble all scenes into a final MP4 with safe-zone subtitles & ambient score."""
        width, height = (1080, 1920) if format_type == "short" else (1920, 1080)
        clips_dir = work_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        output_mp4.parent.mkdir(parents=True, exist_ok=True)

        available_images = sorted(
            [
                p
                for p in images_dir.iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            ]
        )
        if not available_images:
            raise FileNotFoundError(f"No images found in {images_dir}")

        rendered_clips: List[Path] = []
        for idx, scene in enumerate(scenes):
            img_name = scene.get("image_file")
            if img_name and (images_dir / img_name).exists():
                img_path = images_dir / img_name
            else:
                img_path = available_images[idx % len(available_images)]

            audio_path = Path(scene["audio_file"])
            clip_path = self.render_scene_clip(
                scene=scene,
                image_path=img_path,
                audio_path=audio_path,
                clip_dir=clips_dir,
                width=width,
                height=height,
            )
            rendered_clips.append(clip_path)

        srt_path = output_mp4.with_suffix(".srt")
        export_srt(scenes, srt_path)

        concat_list = work_dir / "concat_list.txt"
        concat_lines = [f"file '{c.resolve()}'" for c in rendered_clips]
        concat_list.write_text("\n".join(concat_lines), encoding="utf-8")

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-i",
                str(srt_path),
                "-c:v",
                "copy",
                "-c:a",
                "copy",
                "-c:s",
                "mov_text",
                "-metadata:s:s:0",
                "language=eng",
                "-movflags",
                "+faststart",
                str(output_mp4),
            ],
            check=True,
            capture_output=True,
        )

        total_duration = round(sum(float(s["duration"]) for s in scenes), 2)
        return {
            "video_path": str(output_mp4),
            "srt_path": str(srt_path),
            "scene_count": len(scenes),
            "total_duration_seconds": total_duration,
            "resolution": f"{width}x{height}",
        }
