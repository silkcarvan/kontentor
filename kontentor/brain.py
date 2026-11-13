"""Step 1: Brain & Storyboard Director (GPT-6 Luna + Cloudflare AI + Google Gemini)."""

import datetime
import json
import re
import urllib.request
from typing import Any, Dict, List

from .config import load_credentials, load_style_memory, save_style_memory


class KontentorBrain:
    """Generates strict JSON storyboards (narration + image_prompt) and powers the AI chat."""

    def __init__(self) -> None:
        self.creds = load_credentials()
        self.memory = load_style_memory()

    def _build_system_prompt(self, format_type: str = "short") -> str:
        dna = self.memory.get("visual_style_dna", {})
        rules = "\n".join(f"- {r}" for r in self.memory.get("youtuber_persona_rules", []))
        lessons = "\n".join(
            f"- [{l.get('date')}] {l.get('insight')}"
            for l in self.memory.get("lessons_learned", [])
        )

        scene_count = (
            "6 to 8 scenes (each 3.5-5 seconds, total under 55 seconds for YouTube #Shorts)"
            if format_type == "short"
            else "20 to 35 scenes (16:9 long documentary format)"
        )

        return f"""You are Kontentor, an autonomous English-language History YouTuber specializing in Central Asian History, Rulers (Amir Temur, Babur, Tomyris), Scholars (Ulugh Beg, Al-Khwarizmi, Ibn Sina, Al-Biruni), Culture, and Silk Road Tourism.

TARGET FORMAT: {format_type.upper()} ({scene_count})
VISUAL STYLE: {dna.get('style_name', 'Golden Sepia Historical Graphic Novel')}

STORYTELLING RULES:
{rules}

LEARNED ANALYTICS INSIGHTS:
{lessons}

Return ONLY valid JSON with this exact schema:
{{
  "title": "Engaging English YouTube title (include #Shorts if short)",
  "description": "English SEO description with hashtags",
  "tags": ["Central Asia", "Samarkand", "History"],
  "thumbnail_prompt": "English FLUX prompt for thumbnail",
  "scenes": [
    {{
      "scene_id": 1,
      "motion": "zoom_in",
      "narration": "English narrator sentence (10-16 words)",
      "subtitle": "SHORT UPPERCASE CAPTION",
      "image_prompt": "Detailed English visual description for FLUX image generator in Golden Sepia Historical Graphic Novel style"
    }}
  ]
}}"""

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Safely extract JSON object from model response."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start : end + 1]
        return json.loads(cleaned)

    def _call_gpt6_luna(self, system_prompt: str, user_prompt: str) -> str:
        """Tier 1: Call GPT-6 Luna via Experiential Labs API."""
        api_key = self.creds["luna_api_key"]
        base_url = self.creds["luna_base_url"].rstrip("/")
        model = self.creds["luna_model"]

        url = f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "KontentorStudio/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]

    def _call_cloudflare_ai_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Tier 2: Call Cloudflare Workers AI LLM (@cf/moonshotai/kimi-k2.7-code or llama)."""
        account_id = self.creds.get("cf_account_id", "")
        token = self.creds.get("cf_api_token", "")
        model = self.creds.get("cf_llm_model", "@cf/moonshotai/kimi-k2.7-code")
        if not (account_id and token):
            raise ValueError("Cloudflare credentials missing")

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        res_obj = data.get("result", {})
        if isinstance(res_obj, dict):
            if "response" in res_obj:
                return res_obj["response"]
            if "choices" in res_obj:
                return res_obj["choices"][0]["message"]["content"]
        raise ValueError("Unexpected Cloudflare LLM response format")

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """Tier 3: Call Google Gemini API."""
        api_key = self.creds["gemini_api_key"]
        model = self.creds["gemini_model"]
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def generate_storyboard(
        self, topic: str, wiki_research: Dict[str, str], format_type: str = "short"
    ) -> Dict[str, Any]:
        """Step 1: Generate strict JSON storyboard with narration and image_prompt per scene."""
        system_prompt = self._build_system_prompt(format_type=format_type)
        user_prompt = (
            f"Create an original {format_type} documentary storyboard in JSON about:\n"
            f"TOPIC: {topic}\n"
            f"WIKIPEDIA HISTORICAL FACTS:\n{wiki_research.get('summary', '')}\n\n"
            "Ensure every scene has 'narration' (English) and 'image_prompt' (English)."
        )

        # 1. Try GPT-6 Luna
        if self.creds.get("luna_api_key"):
            try:
                raw = self._call_gpt6_luna(system_prompt, user_prompt)
                parsed = self._extract_json(raw)
                if parsed.get("scenes"):
                    parsed["model_used"] = "gpt-6-luna"
                    return parsed
            except Exception as exc:
                print(f"[Step 1] GPT-6 Luna fallback ({exc})...")

        # 2. Try Cloudflare Workers AI (kimi-k2.7-code)
        if self.creds.get("cf_account_id") and self.creds.get("cf_api_token"):
            try:
                raw = self._call_cloudflare_ai_llm(system_prompt, user_prompt)
                parsed = self._extract_json(raw)
                if parsed.get("scenes"):
                    parsed["model_used"] = self.creds.get("cf_llm_model")
                    return parsed
            except Exception as exc:
                print(f"[Step 1] Cloudflare AI LLM fallback ({exc})...")

        # 3. Try Google Gemini
        if self.creds.get("gemini_api_key"):
            try:
                raw = self._call_gemini(system_prompt, user_prompt)
                parsed = self._extract_json(raw)
                if parsed.get("scenes"):
                    parsed["model_used"] = self.creds.get("gemini_model")
                    return parsed
            except Exception as exc:
                print(f"[Step 1] Gemini fallback ({exc})...")

        return self._generate_fallback_storyboard(topic, wiki_research)

    def _generate_fallback_storyboard(
        self, topic: str, wiki_research: Dict[str, str]
    ) -> Dict[str, Any]:
        """Rich Central Asian history storyboard generator."""
        summary = wiki_research.get("summary", "")
        sentences = [
            s.strip() for s in summary.replace(". ", ".\n").splitlines() if s.strip()
        ]
        short_title = wiki_research.get("title", topic).split("—")[0].strip()

        motions = ["zoom_in", "zoom_out", "pan_right", "pan_left"]
        scenes: List[Dict[str, Any]] = [
            {
                "scene_id": 1,
                "motion": "zoom_in",
                "narration": f"How did {short_title} forever change the destiny of Central Asia and the world?",
                "subtitle": f"THE SECRET OF {short_title.upper()[:20]}",
                "image_prompt": (
                    f"An ancient parchment scroll with a glowing golden question mark in the foreground, "
                    f"while a dramatic historical vision of {short_title} in medieval Samarkand rises in golden smoke above."
                ),
            }
        ]
        for idx, sent in enumerate(sentences[:6], start=2):
            words = sent.split()
            sub = " ".join(words[:6]).upper()
            scenes.append(
                {
                    "scene_id": idx,
                    "motion": motions[(idx - 1) % len(motions)],
                    "narration": sent,
                    "subtitle": sub,
                    "image_prompt": (
                        f"Epic medieval Central Asian historical scene illustrating: {sent}, "
                        "ornate Silk Road architecture and authentic historical attire."
                    ),
                }
            )
        return {
            "title": f"{wiki_research.get('title', topic)} #Shorts",
            "description": f"{summary}\n\n#CentralAsia #History #SilkRoad #Samarkand #Shorts",
            "tags": ["Central Asia", "Silk Road", "History", "Samarkand", short_title],
            "thumbnail_prompt": f"Dramatic golden sepia graphic novel illustration of {short_title}",
            "model_used": "built_in_historian",
            "scenes": scenes,
        }

    def pick_next_autonomous_topic(self) -> str:
        queue = self.memory.get("autonomous_topic_queue", [])
        completed = set(self.memory.get("completed_topics", []))
        for t in queue:
            if t not in completed:
                return t
        return "Mirzo Ulugh Beg: The Sultan Who Mapped 1,018 Stars in Samarkand"

    def mark_topic_completed(self, topic: str) -> None:
        completed = self.memory.setdefault("completed_topics", [])
        if topic not in completed:
            completed.append(topic)
            save_style_memory(self.memory)

    def self_train_from_analytics(
        self, video_metrics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        today = datetime.date.today().isoformat()
        new_insights: List[Dict[str, str]] = []

        for metric in video_metrics:
            title = metric.get("title", "Unknown Video")
            ctr = float(metric.get("ctr_percent", 0.0))
            avg_retention = float(metric.get("avg_percentage_viewed", 0.0))
            drop_off_sec = int(metric.get("drop_off_second", 0))

            if avg_retention >= 75.0:
                new_insights.append(
                    {
                        "date": today,
                        "metric_source": title,
                        "insight": (
                            f"HIGH PERFORMER ({avg_retention}% retention, {ctr}% CTR): "
                            f"'{title}' succeeded with vivid visual metaphors in Scenes 1-2."
                        ),
                    }
                )
            elif drop_off_sec > 0 and avg_retention < 55.0:
                new_insights.append(
                    {
                        "date": today,
                        "metric_source": title,
                        "insight": (
                            f"RETENTION FIX (Drop-off at {drop_off_sec}s in '{title}'): "
                            f"Keep narration under 12 words around second {drop_off_sec}."
                        ),
                    }
                )

        self.memory.setdefault("lessons_learned", []).extend(new_insights)
        save_style_memory(self.memory)
        return {
            "updated_lessons_count": len(self.memory["lessons_learned"]),
            "new_insights": new_insights,
        }
