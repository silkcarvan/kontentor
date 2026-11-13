"""5-Step Autonomous YouTuber Pipeline for Kontentor."""

import json
import re
from typing import Any, Dict, Optional

from .assembler import VideoAssembler
from .brain import KontentorBrain
from .config import OUTPUT_DIR, PROJECTS_DIR
from .image_generator import AutonomousImageGenerator
from .researcher import WikipediaResearcher
from .voice import VoiceEngine
from .youtube_uploader import YouTubeAutoUploader


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:40] or "project"


class KontentorPipeline:
    """Executes the 5-Step Pipeline:
    1. Script & JSON (GPT-6 Luna / Cloudflare AI / Gemini)
    2. Images from Scratch (Cloudflare Workers AI FLUX 9:16 or 16:9)
    3. Unlimited English Voice & .srt (edge-tts: Andrew / Brian / Mark)
    4. Code Montage (FFmpeg Zoom-in + Subtitles)
    5. Auto Shorts vs Long YouTube Data API v3 Routing
    """

    def __init__(self, voice_name: str = "en-US-AndrewNeural") -> None:
        self.researcher = WikipediaResearcher()
        self.brain = KontentorBrain()
        self.image_gen = AutonomousImageGenerator()
        self.voice = VoiceEngine(voice_name=voice_name)
        self.assembler = VideoAssembler()
        self.uploader = YouTubeAutoUploader()

    def run_autonomous_youtuber(
        self,
        topic: Optional[str] = None,
        format_type: str = "short",
    ) -> Dict[str, Any]:
        """Run all 5 steps autonomously from 0."""
        chosen_topic = topic or self.brain.pick_next_autonomous_topic()
        slug = _slugify(chosen_topic)
        project_dir = PROJECTS_DIR / slug
        project_dir.mkdir(parents=True, exist_ok=True)
        audio_dir = project_dir / "audio"
        images_dir = project_dir / "images"

        print(f"Step 1a. [Wikipedia] Fetching historical facts for: '{chosen_topic}'...")
        wiki_data = self.researcher.search_and_fetch(chosen_topic)
        (project_dir / "research.json").write_text(
            json.dumps(wiki_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        print(f"Step 1b. [GPT-6 Luna] Generating strict JSON script ({format_type})...")
        storyboard = self.brain.generate_storyboard(
            topic=chosen_topic, wiki_research=wiki_data, format_type=format_type
        )

        print(
            f"Step 2. [Cloudflare Workers AI FLUX] Drawing {len(storyboard['scenes'])} frames from scratch..."
        )
        scenes = self.image_gen.generate_all_scene_images(
            scenes=storyboard["scenes"],
            images_dir=images_dir,
            format_type=format_type,
        )

        print(
            f"Step 3. [edge-tts ({self.voice.voice_name})] Synthesizing English audio + .srt..."
        )
        scenes = self.voice.synthesize_all_scenes(scenes, audio_dir)
        storyboard["scenes"] = scenes

        storyboard_path = project_dir / "storyboard.json"
        storyboard_path.write_text(
            json.dumps(storyboard, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        print("Step 4. [FFmpeg] Applying Zoom-in / Ken Burns motion & burning subtitles...")
        output_mp4 = OUTPUT_DIR / f"{slug}_{format_type}.mp4"
        video_info = self.assembler.assemble_video(
            scenes=scenes,
            images_dir=images_dir,
            work_dir=project_dir / "build",
            output_mp4=output_mp4,
            format_type=format_type,
        )

        print("Step 5. [YouTube Data API v3] Preparing Shorts (9:16) vs Long (16:9) upload...")
        yt_upload_info = self.uploader.upload_video(
            video_path=output_mp4,
            title=storyboard.get("title", chosen_topic),
            description=storyboard.get("description", ""),
            tags=storyboard.get("tags", []),
            format_type=format_type,
            duration_seconds=video_info["total_duration_seconds"],
        )

        yt_meta_path = project_dir / "youtube_seo.json"
        yt_meta_path.write_text(
            json.dumps(yt_upload_info, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        self.brain.mark_topic_completed(chosen_topic)
        print(f"DONE! Video Ready: {output_mp4}")

        return {
            "topic": chosen_topic,
            "model_used": storyboard.get("model_used", "gpt-6-luna"),
            "voice_used": self.voice.voice_name,
            "project_dir": str(project_dir),
            "storyboard_path": str(storyboard_path),
            "youtube_seo_path": str(yt_meta_path),
            "youtube_routing": yt_upload_info.get("youtube_placement"),
            "scenes": scenes,
            "video": video_info,
        }
