#!/usr/bin/env python3
"""Kontentor Web Studio — ChatGPT/Claude-Style AI Chat + Facebook Analytics Server."""

import json
import mimetypes
import sqlite3
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
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
)
from kontentor.pipeline import KontentorPipeline

DB_PATH = DATA_DIR / "kontentor_d1.sqlite"
WEB_UI_DIR = BASE_DIR / "web_ui"
MIGRATION_SQL = BASE_DIR / "web" / "migrations" / "0001_initial_schema.sql"


def init_db() -> None:
    """Initialize D1-compatible SQLite database and seed initial analytics."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if MIGRATION_SQL.exists():
        conn.executescript(MIGRATION_SQL.read_text(encoding="utf-8"))

    cur = conn.execute("SELECT COUNT(*) AS cnt FROM users")
    if cur.fetchone()["cnt"] == 0:
        user_id = "admin-001"
        channel_id = "ch-central-asia-01"
        conn.execute(
            """INSERT INTO users (id, email, password_hash, role, plan, shorts_credits, long_credits)
               VALUES (?, ?, ?, 'admin', 'closed_beta', 98, 20)""",
            (user_id, "admin@kontentor.ai", "pbkdf2_sha256$closed_beta_admin"),
        )
        conn.execute(
            """INSERT INTO youtube_channels (id, user_id, channel_id, channel_title, niche, access_token, refresh_token, token_expiry)
               VALUES (?, ?, 'UC_CENTRAL_ASIA_HIST', 'Chronicles of Central Asia', 'Central Asian History & Culture', 'oauth_placeholder', 'refresh_placeholder', '2027-01-01T00:00:00Z')""",
            (channel_id, user_id),
        )
        sample_videos = [
            (
                "proj-001",
                "Amir Temur: How a Shepherd's Son Built the Unstoppable Timurid Empire",
                "shorts",
                "published",
                "/output/amir_temur_short.mp4",
                28450,
                11.4,
                86.2,
                0,
                "HIGH PERFORMER (86.2% retention, 11.4% CTR): Opening with a glowing parchment question mark + 3s visual metaphor maximizes hook rate.",
            ),
            (
                "proj-002",
                "Battle of Talas (751 AD) & The Secret of Samarkand Paper",
                "shorts",
                "published",
                "",
                42190,
                12.8,
                89.5,
                0,
                "VIRAL HOOK (89.5% retention): Explaining how 1 parchment book cost an entire flock of sheep before Samarkand paper drove massive shares.",
            ),
            (
                "proj-003",
                "Mirzo Ulugh Beg: Mapping 1,018 Stars in Samarkand Without a Telescope",
                "long",
                "published",
                "",
                14820,
                8.9,
                68.4,
                145,
                "LONG-FORM RPM BOOST ($8.40 RPM): US/UK history audience watched 68.4% of the documentary on Samarkand's observatory.",
            ),
            (
                "proj-004",
                "Al-Khwarizmi: The Central Asian Father of Every Computer Algorithm",
                "shorts",
                "published",
                "",
                19300,
                9.7,
                79.1,
                18,
                "TECH + HISTORY CROSSOVER: Connecting medieval Khwarazm to modern AI/smartphones increased comments by 3.2x.",
            ),
        ]
        for pid, topic, vtype, status, vurl, views, ctr, ret, drop, rule in sample_videos:
            conn.execute(
                """INSERT INTO projects (id, user_id, channel_id, topic, video_type, status, final_video_r2_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pid, user_id, channel_id, topic, vtype, status, vurl),
            )
            conn.execute(
                """INSERT INTO channel_analytics_memory (id, channel_id, project_id, views, ctr_percent, avg_view_percentage, drop_off_second, learned_rule)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), channel_id, pid, views, ctr, ret, drop, rule),
            )
        conn.commit()
    conn.close()


def get_dashboard_payload() -> dict:
    """Build complete payload for the Chat Studio & Facebook Analytics UI."""
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

    # Load latest project storyboard scenes for quick preview in chat
    latest_storyboard = {}
    amir_sb = PROJECTS_DIR / "amir_temur" / "storyboard.json"
    if amir_sb.exists():
        latest_storyboard = json.loads(amir_sb.read_text(encoding="utf-8"))

    total_views = sum(int(p.get("views") or 0) for p in projects)
    ctrs = [float(p["ctr_percent"]) for p in projects if p.get("ctr_percent")]
    rets = [float(p["avg_view_percentage"]) for p in projects if p.get("avg_view_percentage")]
    avg_ctr = round(sum(ctrs) / len(ctrs), 1) if ctrs else 0.0
    avg_ret = round(sum(rets) / len(rets), 1) if rets else 0.0
    estimated_revenue = round((total_views / 1000.0) * 6.40, 2)

    return {
        "user": user,
        "channel": channel,
        "connected_stack": {
            "step1_luna": bool(creds.get("luna_api_key")),
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
    """HTTP Handler serving ChatGPT/Claude-Style Studio, MP4 files, and Analytics API."""

    def _send_json(self, data: dict, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/dashboard":
            self._send_json(get_dashboard_payload())
            return

        if path == "/robots.txt":
            robots = (
                "User-agent: *\nAllow: /\n"
                "Sitemap: https://kontentor.ai/sitemap.xml\n"
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
                "  <url><loc>https://kontentor.ai/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>\n"
                "  <url><loc>https://kontentor.ai/output/amir_temur_short.mp4</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>\n"
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
            if file_path.exists() and file_path.is_file():
                data = file_path.read_bytes()
                mime, _ = mimetypes.guess_type(str(file_path))
                self.send_response(200)
                self.send_header("Content-Type", mime or "video/mp4")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        if path.startswith("/projects/"):
            rel = path.lstrip("/")
            file_path = BASE_DIR / rel
            if file_path.exists() and file_path.is_file():
                data = file_path.read_bytes()
                mime, _ = mimetypes.guess_type(str(file_path))
                self.send_response(200)
                self.send_header("Content-Type", mime or "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        index_file = WEB_UI_DIR / "index.html"
        if index_file.exists():
            html = index_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if parsed.path == "/api/generate":
            topic = body.get("topic") or None
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
                   VALUES (?, 'ch-central-asia-01', ?, 1250, 10.4, 83.5, 0, ?)""",
                (
                    str(uuid.uuid4()),
                    pid,
                    f"5-Step Pipeline ({res['model_used']} + Cloudflare FLUX + {res['voice_used']} + {res['youtube_routing']})",
                ),
            )
            conn.commit()
            conn.close()

            self._send_json({"ok": True, "result": res, "video_url": vid_url})
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


def run_server(port: int = 8765) -> None:
    init_db()
    server = HTTPServer(("127.0.0.1", port), KontentorHandler)
    print(f"Kontentor AI Chat & Analytics Studio running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
