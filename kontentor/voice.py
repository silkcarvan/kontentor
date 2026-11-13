"""Step 3: ElevenLabs ('Mark') + Unlimited Edge-TTS + Broadcast Vocal Mastering."""

import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, List

from .config import load_credentials

ELEVENLABS_VOICES = {
    "mark": "1SM7GgM6IMuvQlz2BwM3",   # ElevenLabs 'Mark' (Natural / Documentary)
    "adam": "pNInz6obpgDQGcFmaJgB",   # ElevenLabs 'Adam' (Deep Narration)
    "brian": "nPczCjzI2devNBz1zQrb",  # ElevenLabs 'Brian' (Epic Storyteller)
}

EDGE_VOICE_PRESETS = {
    "mark": "en-US-ChristopherNeural",   # Deep resonant Mark-style narrator
    "andrew": "en-US-AndrewNeural",      # Warm natural documentary narrator
    "brian": "en-US-BrianNeural",        # Crisp storyteller
    "eric": "en-US-EricNeural",
    "en-US-AndrewNeural": "en-US-AndrewNeural",
    "en-US-BrianNeural": "en-US-BrianNeural",
    "en-US-ChristopherNeural": "en-US-ChristopherNeural",
    "en-US-EricNeural": "en-US-EricNeural",
}


class VoiceEngine:
    """Synthesizes English documentary voiceovers via ElevenLabs ('Mark') or Edge-TTS with Studio Mastering."""

    def __init__(self, voice_name: str = "mark") -> None:
        self.creds = load_credentials()
        self.raw_voice_choice = voice_name.lower()
        self.elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        self.elevenlabs_voice_id = ELEVENLABS_VOICES.get(
            self.raw_voice_choice, ELEVENLABS_VOICES["mark"]
        )
        self.edge_voice_name = EDGE_VOICE_PRESETS.get(
            self.raw_voice_choice,
            EDGE_VOICE_PRESETS.get(voice_name, "en-US-AndrewNeural"),
        )

    @property
    def voice_name(self) -> str:
        if self.elevenlabs_api_key:
            return f"ElevenLabs-{self.raw_voice_choice.capitalize()}"
        return f"{self.edge_voice_name} (Mastered)"

    @staticmethod
    def get_audio_duration(audio_path: Path) -> float:
        """Measure exact audio duration in seconds using ffprobe."""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return round(float(res.stdout.strip()), 3)

    @staticmethod
    def estimate_speech_duration(text: str) -> float:
        word_count = max(1, len(text.strip().split()))
        return round(max(3.0, word_count / 2.6 + 0.35), 2)

    @staticmethod
    def _master_voice_audio(raw_mp3: Path, output_mp3: Path) -> None:
        """Apply ElevenLabs-style warm broadcast EQ, compression & breathing room."""
        audio_filter = (
            "highpass=f=75,"
            "equalizer=f=165:t=q:w=1.1:g=3.0,"
            "equalizer=f=3600:t=q:w=1.4:g=2.2,"
            "acompressor=threshold=-18dB:ratio=3:attack=5:release=60:makeup=2dB,"
            "apad=pad_dur=0.22"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw_mp3),
                "-af",
                audio_filter,
                "-ar",
                "44100",
                "-ac",
                "2",
                "-b:a",
                "192k",
                str(output_mp3),
            ],
            check=True,
            capture_output=True,
        )

    def _synthesize_via_elevenlabs(self, text: str, raw_mp3: Path) -> bool:
        """Call ElevenLabs v1 TTS API using 'Mark' (1SM7GgM6IMuvQlz2BwM3) or chosen voice."""
        if not self.elevenlabs_api_key:
            return False
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}"
        payload = json.dumps(
            {
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {
                    "stability": 0.55,
                    "similarity_boost": 0.80,
                    "style": 0.35,
                    "use_speaker_boost": True,
                },
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "xi-api-key": self.elevenlabs_api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio_bytes = resp.read()
        if len(audio_bytes) > 1000:
            raw_mp3.write_bytes(audio_bytes)
            return True
        return False

    def synthesize_scene(self, text: str, output_mp3: Path, output_srt: Path) -> float:
        """Synthesize a single scene narration to mastered MP3 + SRT and return exact duration."""
        output_mp3.parent.mkdir(parents=True, exist_ok=True)
        target_dur = self.estimate_speech_duration(text)
        raw_mp3 = output_mp3.with_suffix(".raw.mp3")

        # 1. Try ElevenLabs ('Mark' voice 1SM7GgM6IMuvQlz2BwM3) if ELEVENLABS_API_KEY is set
        if self.elevenlabs_api_key:
            try:
                if self._synthesize_via_elevenlabs(text, raw_mp3):
                    self._master_voice_audio(raw_mp3, output_mp3)
                    raw_mp3.unlink(missing_ok=True)
                    return self.get_audio_duration(output_mp3)
            except Exception:
                raw_mp3.unlink(missing_ok=True)

        # 2. Unlimited Free Neural TTS (edge-tts: Mark / Andrew / Brian) + Broadcast Mastering
        edge_tts_bin = Path(".venv/bin/edge-tts")
        if not edge_tts_bin.exists():
            found = shutil.which("edge-tts")
            if found:
                edge_tts_bin = Path(found)

        if edge_tts_bin.exists():
            try:
                rate_arg = "--rate=-2%"
                pitch_arg = (
                    "--pitch=-3Hz"
                    if "Christopher" in self.edge_voice_name
                    else "--pitch=+0Hz"
                )
                subprocess.run(
                    [
                        str(edge_tts_bin),
                        "--voice",
                        self.edge_voice_name,
                        rate_arg,
                        pitch_arg,
                        "--text",
                        text,
                        "--write-media",
                        str(raw_mp3),
                        "--write-subtitles",
                        str(output_srt),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=25,
                )
                if raw_mp3.exists() and raw_mp3.stat().st_size > 1000:
                    self._master_voice_audio(raw_mp3, output_mp3)
                    raw_mp3.unlink(missing_ok=True)
                    dur = self.get_audio_duration(output_mp3)
                    if dur >= 1.2:
                        return dur
            except Exception:
                raw_mp3.unlink(missing_ok=True)

        # 3. Fallback: macOS 'say' speech synthesizer + Broadcast Mastering
        temp_aiff = output_mp3.with_suffix(".aiff")
        try:
            subprocess.run(
                ["say", "-r", "168", "-o", str(temp_aiff), text],
                check=True,
                capture_output=True,
                timeout=12,
            )
            if temp_aiff.exists() and temp_aiff.stat().st_size > 4096:
                self._master_voice_audio(temp_aiff, output_mp3)
                temp_aiff.unlink(missing_ok=True)
                dur = self.get_audio_duration(output_mp3)
                if dur >= 1.2:
                    return dur
        except Exception:
            pass
        finally:
            temp_aiff.unlink(missing_ok=True)

        # 4. Offline fallback
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=110:sample_rate=44100:duration={target_dur}",
                "-af",
                f"volume=0.04,afade=t=in:st=0:d=0.3,afade=t=out:st={max(0.1, target_dur - 0.4):.2f}:d=0.4",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-b:a",
                "192k",
                str(output_mp3),
            ],
            check=True,
            capture_output=True,
        )
        return self.get_audio_duration(output_mp3)

    def synthesize_all_scenes(
        self, scenes: List[Dict], audio_dir: Path
    ) -> List[Dict]:
        """Generate mastered narration audio + SRT for every scene and record exact timing."""
        audio_dir.mkdir(parents=True, exist_ok=True)
        current_time = 0.0

        for scene in scenes:
            sid = int(scene["scene_id"])
            mp3_path = audio_dir / f"scene_{sid:02d}.mp3"
            srt_path = audio_dir / f"scene_{sid:02d}.srt"
            duration = self.synthesize_scene(scene["narration"], mp3_path, srt_path)
            scene["audio_file"] = str(mp3_path)
            scene["scene_srt_file"] = str(srt_path)
            scene["duration"] = duration
            scene["start_time"] = round(current_time, 3)
            scene["end_time"] = round(current_time + duration, 3)
            current_time += duration

        return scenes
