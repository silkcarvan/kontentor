#!/usr/bin/env python3
"""Kontentor Web Studio — Clean 0-State Local AI Chat, Video Generator & Analytics Server."""

import argparse
import json
import mimetypes
import re
import shutil
import sqlite3
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from kontentor.brain import KontentorBrain
from kontentor.config import (
    BASE_DIR,
    DATA_DIR,
    OUTPUT_DIR,
    PROJECTS_DIR,
    load_credentials,
    load_style_memory,
    save_style_memory,
)
from kontentor.pipeline import KontentorPipeline

DB_PATH = DATA_DIR / "kontentor_d1.sqlite"
WEB_UI_DIR = BASE_DIR / "web_ui"
MIGRATION_SQL = BASE_DIR / "web" / "migrations" / "0001_initial_schema.sql"


def init_db(reset: bool = False) -> None:
    """Initialize D1-compatible SQLite database in a clean 0-state."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    if reset and DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if MIGRATION_SQL.exists():
        conn.executescript(MIGRATION_SQL.read_text(encoding="utf-8"))

    if reset:
        conn.execute("DELETE FROM channel_analytics_memory")
        conn.execute("DELETE FROM projects")
        conn.execute("DELETE FROM youtube_channels")
        conn.execute("DELETE FROM users")
        conn.commit()

    cur = conn.execute("SELECT COUNT(*) AS cnt FROM users")
    if cur.fetchone()["cnt"] == 0:
        user_id = "admin-001"
        channel_id = "ch-central-asia-01"
        conn.execute(
            """INSERT INTO users (id, email, password_hash, role, plan, shorts_credits, long_credits)
               VALUES (?, ?, ?, 'admin', 'pro', 100, 50)""",
            (user_id, "admin@kontentor.ai", "pbkdf2_sha256$local_admin"),
        )
        conn.execute(
            """INSERT INTO youtube_channels (id, user_id, channel_id, channel_title, niche, access_token, refresh_token, token_expiry)
               VALUES (?, ?, 'UC_CENTRAL_ASIA_HIST', 'Chronicles of Central Asia', 'Central Asian History & Culture', 'oauth_placeholder', 'refresh_placeholder', '2027-01-01T00:00:00Z')""",
            (channel_id, user_id),
        )
        conn.commit()
    conn.close()


def reset_all_to_zero() -> None:
    """Reset database, generated outputs, and project folders to a fresh 0 state."""
    init_db(reset=True)
    for mp4 in OUTPUT_DIR.glob("*.mp4"):
        try:
            mp4.unlink()
        except OSError:
            pass
    for srt in OUTPUT_DIR.glob("*.srt"):
        try:
            srt.unlink()
        except OSError:
            pass
    for pdir in PROJECTS_DIR.iterdir():
        if pdir.is_dir():
            shutil.rmtree(pdir, ignore_errors=True)

    memory = load_style_memory()
    memory["completed_topics"] = []
    memory["lessons_learned"] = []
    save_style_memory(memory)


def get_dashboard_payload() -> dict:
    """Build complete payload for the Chat Studio & Analytics UI."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    user = dict(conn.execute("SELECT * FROM users LIMIT 1").fetchone())
    channel = dict(conn.execute("SELECT * FROM youtube_channels LIMIT 1").fetchone())
    projects = [
        dict(r)
        for r in conn.execute(
            """SELECT p.*, a.views, a.ctr_percent, a.avg_view_percentage, a.drop_off_second, a.learned_rule
               FROM projects p
               LEFT JOIN channel_analytics_memory a ON a.project_id = p.id
               ORDER BY p.created_at DESC"""
        ).fetchall()
    ]
    conn.close()

    creds = load_credentials()
    memory = load_style_memory()
    output_videos = [
        f"/output/{p.name}"
        for p in sorted(
            OUTPUT_DIR.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True
        )
    ]

    latest_storyboard = {}
    if projects:
        for pdir in sorted(
            PROJECTS_DIR.glob("*/storyboard.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        ):
            try:
                latest_storyboard = json.loads(pdir.read_text(encoding="utf-8"))
                break
            except Exception:
                pass

    total_views = sum(int(p.get("views") or 0) for p in projects)
    ctrs = [float(p["ctr_percent"]) for p in projects if p.get("ctr_percent") is not None]
    rets = [
        float(p["avg_view_percentage"])
        for p in projects
        if p.get("avg_view_percentage") is not None
    ]
    avg_ctr = round(sum(ctrs) / len(ctrs), 1) if ctrs else 0.0
    avg_ret = round(sum(rets) / len(rets), 1) if rets else 0.0
    estimated_revenue = round((total_views / 1000.0) * 6.40, 2)

    return {
        "user": user,
        "channel": channel,
        "connected_stack": {
            "step1_luna": bool(creds.get("luna_api_key") or creds.get("gemini_api_key")),
            "step2_cloudflare_flux": bool(
                creds.get("cf_account_id") and creds.get("cf_api_token")
            ),
            "step3_edge_tts": True,
            "step4_ffmpeg": True,
            "step5_youtube_router": True,
            "gemini_backup": bool(creds.get("gemini_api_key")),
        },
        "kpis": {
            "total_views": total_views,
            "avg_ctr_percent": avg_ctr,
            "avg_retention_percent": avg_ret,
            "estimated_revenue_usd": estimated_revenue,
            "published_videos": len(projects),
            "shorts_credits": user["shorts_credits"],
            "long_credits": user["long_credits"],
        },
        "projects": projects,
        "output_videos": output_videos,
        "latest_storyboard": latest_storyboard,
        "style_memory": memory,
    }


class KontentorHandler(BaseHTTPRequestHandler):
    """Multi-threaded HTTP Handler supporting Byte-Range MP4 streaming & AI Generation."""

    def _send_json(self, data: dict, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _serve_file(self, file_path: Path, default_mime: str) -> None:
        if not file_path.exists() or not file_path.is_file():
            self._send_json({"error": "File not found"}, 404)
            return

        mime, _ = mimetypes.guess_type(str(file_path))
        content_type = mime or default_mime
        file_size = file_path.stat().st_size
        range_header = self.headers.get("Range")

        if range_header:
            m = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if m:
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else file_size - 1
                end = min(end, file_size - 1)
                if start <= end:
                    length = end - start + 1
                    with file_path.open("rb") as f:
                        f.seek(start)
                        chunk = f.read(length)
                    self.send_response(206)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header(
                        "Content-Range", f"bytes {start}-{end}/{file_size}"
                    )
                    self.send_header("Content-Length", str(len(chunk)))
                    self.end_headers()
                    self.wfile.write(chunk)
                    return

        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/dashboard":
            self._send_json(get_dashboard_payload())
            return

        if path == "/robots.txt":
            robots = (
                "User-agent: *\nAllow: /\n"
                "Sitemap: http://127.0.0.1:8090/sitemap.xml\n"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(robots)))
            self.end_headers()
            self.wfile.write(robots)
            return

        if path == "/sitemap.xml":
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                "  <url><loc>http://127.0.0.1:8090/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>\n"
                "</urlset>\n"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(xml)))
            self.end_headers()
            self.wfile.write(xml)
            return

        if path.startswith("/output/"):
            file_path = OUTPUT_DIR / Path(path).name
            self._serve_file(file_path, "video/mp4")
            return

        if path.startswith("/projects/"):
            rel = path.lstrip("/")
            file_path = BASE_DIR / rel
            self._serve_file(file_path, "image/jpeg")
            return

        index_file = WEB_UI_DIR / "index.html"
        if index_file.exists():
            html = index_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if parsed.path == "/api/reset":
            reset_all_to_zero()
            self._send_json({"ok": True, "message": "Tizim 0 holatiga tozalandi!"})
            return

        if parsed.path == "/api/generate":
            try:
                topic = (body.get("topic") or "").strip() or None
                fmt = body.get("format", "short")
                voice = body.get("voice", "en-US-AndrewNeural")
                vtype_db = "shorts" if fmt == "short" else "long"
                credit_col = "shorts_credits" if fmt == "short" else "long_credits"

                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                user = conn.execute("SELECT * FROM users LIMIT 1").fetchone()
                if user[credit_col] <= 0:
                    conn.close()
                    self._send_json({"error": f"Insufficient {vtype_db} credits!"}, 402)
                    return

                conn.execute(
                    f"UPDATE users SET {credit_col} = {credit_col} - 1 WHERE id = ?",
                    (user["id"],),
                )
                conn.commit()

                pipeline = KontentorPipeline(voice_name=voice)
                res = pipeline.run_autonomous_youtuber(topic=topic, format_type=fmt)
                vid_name = Path(res["video"]["video_path"]).name
                vid_url = f"/output/{vid_name}"
                pid = f"proj-{uuid.uuid4().hex[:6]}"

                conn.execute(
                    """INSERT INTO projects (id, user_id, channel_id, topic, video_type, status, final_video_r2_url)
                       VALUES (?, ?, 'ch-central-asia-01', ?, ?, 'published', ?)""",
                    (pid, user["id"], res["topic"], vtype_db, vid_url),
                )
                conn.execute(
                    """INSERT INTO channel_analytics_memory (id, channel_id, project_id, views, ctr_percent, avg_view_percentage, drop_off_second, learned_rule)
                       VALUES (?, 'ch-central-asia-01', ?, 0, 0.0, 0.0, 0, ?)""",
                    (
                        str(uuid.uuid4()),
                        pid,
                        f"0 dan yaratildi: {res['model_used']} + Cloudflare FLUX + {res['voice_used']} ({res['video']['total_duration_seconds']}s)",
                    ),
                )
                conn.commit()
                conn.close()

                self._send_json({"ok": True, "result": res, "video_url": vid_url})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
            return

        if parsed.path == "/api/train":
            brain = KontentorBrain()
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT p.topic AS title, a.views, a.ctr_percent, a.avg_view_percentage AS avg_percentage_viewed, a.drop_off_second
                   FROM channel_analytics_memory a
                   JOIN projects p ON p.id = a.project_id"""
            ).fetchall()
            conn.close()
            metrics = [dict(r) for r in rows]
            train_res = brain.self_train_from_analytics(metrics)
            self._send_json({"ok": True, "training": train_res})
            return

        self._send_json({"error": "Unknown endpoint"}, 404)


def run_server(port: int = 8090, reset_on_start: bool = False) -> None:
    init_db(reset=reset_on_start)
    server = ThreadingHTTPServer(("127.0.0.1", port), KontentorHandler)
    print(f"Kontentor AI Chat & Analytics Studio running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--reset", action="store_true", help="Reset DB to 0 state on startup")
    args = parser.parse_args()
    run_server(port=args.port, reset_on_start=args.reset)
