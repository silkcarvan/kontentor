"""Step 5: YouTube Data API v3 Auto-Uploader (Shorts 9:16 vs Long 16:9 Routing)."""

import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


class YouTubeAutoUploader:
    """Automatically formats and uploads Shorts (9:16 <60s) and Long (16:9) videos."""

    def prepare_upload_metadata(
        self,
        title: str,
        description: str,
        tags: List[str],
        format_type: str,
        duration_seconds: float,
    ) -> Dict[str, Any]:
        """Automatically distinguish Shorts vs Long-form for YouTube Data API v3."""
        is_shorts = format_type == "short" and duration_seconds <= 60.0
        clean_title = title.strip()

        if is_shorts:
            if "#shorts" not in clean_title.lower():
                clean_title = f"{clean_title[:88]} #Shorts"
            if "#shorts" not in description.lower():
                description = f"{description.strip()}\n\n#Shorts #CentralAsia #History"
            if "Shorts" not in tags:
                tags = list(tags) + ["Shorts", "YouTubeShorts"]
            placement = "YouTube Shorts Feed (9:16 Vertical, <=60s)"
        else:
            clean_title = clean_title.replace("#Shorts", "").replace("#shorts", "").strip()
            placement = "YouTube Main Documentary Feed (16:9 Widescreen)"

        return {
            "youtube_placement": placement,
            "is_shorts": is_shorts,
            "api_body": {
                "snippet": {
                    "title": clean_title[:100],
                    "description": description,
                    "tags": tags[:15],
                    "categoryId": "27",  # 27 = Education / History
                    "defaultLanguage": "en",
                    "defaultAudioLanguage": "en",
                },
                "status": {
                    "privacyStatus": os.environ.get("YOUTUBE_PRIVACY", "public"),
                    "selfDeclaredMadeForKids": False,
                },
            },
        }

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        format_type: str = "short",
        duration_seconds: float = 40.0,
        access_token: str = "",
    ) -> Dict[str, Any]:
        """Upload MP4 to YouTube Data API v3 if OAuth access_token is configured."""
        meta = self.prepare_upload_metadata(
            title=title,
            description=description,
            tags=tags,
            format_type=format_type,
            duration_seconds=duration_seconds,
        )
        token = access_token or os.environ.get("YOUTUBE_ACCESS_TOKEN", "")
        if not token:
            meta["upload_status"] = "ready_for_oauth_upload"
            return meta

        init_url = (
            "https://www.googleapis.com/upload/youtube/v3/videos"
            "?uploadType=resumable&part=snippet,status"
        )
        body_bytes = json.dumps(meta["api_body"]).encode("utf-8")
        video_bytes = video_path.read_bytes()

        req = urllib.request.Request(
            init_url,
            data=body_bytes,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(len(video_bytes)),
                "X-Upload-Content-Type": "video/mp4",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            upload_url = resp.headers.get("Location")

        put_req = urllib.request.Request(
            upload_url,
            data=video_bytes,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "video/mp4",
                "Content-Length": str(len(video_bytes)),
            },
            method="PUT",
        )
        with urllib.request.urlopen(put_req, timeout=180) as put_resp:
            yt_resp = json.loads(put_resp.read().decode("utf-8"))

        meta["upload_status"] = "published"
        meta["youtube_video_id"] = yt_resp.get("id")
        return meta
