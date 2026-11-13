"""FastAPI + FFmpeg + Edge-TTS Render Container for Kontentor SaaS."""

from typing import List, Literal, Optional
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Kontentor FFmpeg Render Worker", version="1.0.0")


class SceneInput(BaseModel):
    scene_id: int
    narration: str
    subtitle: Optional[str] = None
    image_r2_url: str
    motion: Literal["zoom_in", "zoom_out", "pan_left", "pan_right"] = "zoom_in"


class RenderJobRequest(BaseModel):
    project_id: str
    video_type: Literal["shorts", "long"] = "shorts"
    voice: str = "en-US-AndrewNeural"
    title: str
    description: str
    tags: List[str] = []
    scenes: List[SceneInput]
    background_music_track: Optional[str] = "epic_silk_road.mp3"
    youtube_access_token: Optional[str] = None


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "kontentor-render-worker",
        "tts_default_voice": "en-US-AndrewNeural",
        "ffmpeg_ready": True,
    }


@app.post("/render")
async def start_render(job: RenderJobRequest) -> dict:
    """Receive render job from Cloudflare Worker (Step 3 & 4 of Pipeline)."""
    return {
        "accepted": True,
        "project_id": job.project_id,
        "video_type": job.video_type,
        "scenes_count": len(job.scenes),
        "voice": job.voice,
    }
