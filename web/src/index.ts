/**
 * Kontentor SaaS — Cloudflare Worker Backend
 * Ideal Free Stack: GPT-6 Luna + Gemini 4 Hydrogen (Brain & Vision QC) + Cloudflare FLUX.1 Schnell + Edge-TTS
 * Includes Google Search Console SEO (/sitemap.xml, /robots.txt, Schema.org JSON-LD)
 */

export interface Env {
  DB: D1Database;
  MEDIA_BUCKET: R2Bucket;
  AI: any;
  LUNA_API_KEY: string;
  LUNA_BASE_URL: string;
  LUNA_MODEL: string;
  GEMINI_API_KEY: string;
  GEMINI_MODEL: string;
  FLUX_MODEL: string;
  MODERATION_MODEL: string;
  RENDER_WORKER_URL: string;
  RENDER_WORKER_SECRET: string;
  PUBLIC_SIGNUP_ENABLED: string;
}

const GOLDEN_SEPIA_STYLE_PREFIX =
  "Warm golden-amber and sepia-toned historical graphic novel illustration, bold hand-drawn black ink line art with rich warm watercolor shading, glowing golden dust particles, medieval Central Asian Silk Road atmosphere, NO text in image -- ";

async function generateScriptWithHydrogenOrLuna(
  topic: string,
  videoType: "shorts" | "long",
  env: Env
): Promise<any> {
  const sysPrompt =
    "You are an autonomous English History YouTuber specializing in Central Asia. Return strict JSON with title, description, tags, and scenes: [{scene_id, narration, subtitle, image_prompt, motion}].";
  const userPrompt = `Create a ${videoType} documentary script from scratch about: ${topic}`;

  // 1. Try GPT-6 Luna first
  if (env.LUNA_API_KEY) {
    try {
      const lunaRes = await fetch(`${env.LUNA_BASE_URL}/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${env.LUNA_API_KEY}`,
        },
        body: JSON.stringify({
          model: env.LUNA_MODEL || "gpt-6-luna",
          response_format: { type: "json_object" },
          messages: [
            { role: "system", content: sysPrompt },
            { role: "user", content: userPrompt },
          ],
        }),
      });
      if (lunaRes.ok) {
        const data = (await lunaRes.json()) as any;
        return JSON.parse(data.choices[0].message.content);
      }
    } catch (_) {}
  }

  // 2. Ideal Free Pair Fallback: Google AI Studio (gemini-4-hydrogen)
  const gemModel = env.GEMINI_MODEL || "gemini-4-hydrogen";
  const gemUrl = `https://generativelanguage.googleapis.com/v1beta/models/${gemModel}:generateContent?key=${env.GEMINI_API_KEY}`;
  const gemRes = await fetch(gemUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: sysPrompt }] },
      contents: [{ parts: [{ text: userPrompt }] }],
      generationConfig: { responseMimeType: "application/json" },
    }),
  });
  const gemData = (await gemRes.json()) as any;
  return JSON.parse(gemData.candidates[0].content.parts[0].text);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Google Search Console SEO: /robots.txt
    if (url.pathname === "/robots.txt" && request.method === "GET") {
      return new Response(
        `User-agent: *\nAllow: /\nSitemap: ${url.origin}/sitemap.xml\n`,
        { headers: { "Content-Type": "text/plain; charset=utf-8" } }
      );
    }

    // Google Search Console SEO: /sitemap.xml
    if (url.pathname === "/sitemap.xml" && request.method === "GET") {
      const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>${url.origin}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>`;
      return new Response(xml, {
        headers: { "Content-Type": "application/xml; charset=utf-8" },
      });
    }

    // 1. Facebook Business Suite Style Analytics Endpoint
    if (url.pathname === "/api/dashboard" && request.method === "GET") {
      const user = await env.DB.prepare("SELECT * FROM users LIMIT 1").first();
      const channel = await env.DB.prepare("SELECT * FROM youtube_channels LIMIT 1").first();
      const projects = await env.DB.prepare(
        `SELECT p.*, a.views, a.ctr_percent, a.avg_view_percentage, a.drop_off_second, a.learned_rule
         FROM projects p
         LEFT JOIN channel_analytics_memory a ON a.project_id = p.id
         ORDER BY p.created_at DESC`
      ).all();

      return Response.json({
        user,
        channel,
        projects: projects.results,
      });
    }

    // 2. Hydrogen/Luna Script + Cloudflare Workers AI FLUX.1 Schnell Images -> R2 -> Render Worker
    if (url.pathname === "/api/projects/generate" && request.method === "POST") {
      const body = (await request.json()) as {
        user_id: string;
        channel_id?: string;
        topic: string;
        video_type: "shorts" | "long";
      };

      const creditCol = body.video_type === "shorts" ? "shorts_credits" : "long_credits";
      const user = await env.DB.prepare(
        `SELECT id, ${creditCol} AS credits FROM users WHERE id = ?1`
      )
        .bind(body.user_id)
        .first<{ id: string; credits: number }>();

      if (!user || user.credits <= 0) {
        return Response.json({ error: "Insufficient credits" }, { status: 402 });
      }

      await env.DB.prepare(
        `UPDATE users SET ${creditCol} = ${creditCol} - 1 WHERE id = ?1`
      )
        .bind(body.user_id)
        .run();

      const projectId = crypto.randomUUID();
      await env.DB.prepare(
        `INSERT INTO projects (id, user_id, channel_id, topic, video_type, status)
         VALUES (?1, ?2, ?3, ?4, ?5, 'generating_assets')`
      )
        .bind(projectId, body.user_id, body.channel_id ?? null, body.topic, body.video_type)
        .run();

      // Step 1: Generate JSON Script (GPT-6 Luna or Gemini 4 Hydrogen)
      const storyboard = await generateScriptWithHydrogenOrLuna(
        body.topic,
        body.video_type,
        env
      );

      // Step 2: Draw every scene image from scratch via Cloudflare Workers AI (FLUX.1 Schnell)
      for (const scene of storyboard.scenes) {
        const fullPrompt = `${GOLDEN_SEPIA_STYLE_PREFIX}${scene.image_prompt}`;
        const aiImage = await env.AI.run(env.FLUX_MODEL, {
          prompt: fullPrompt,
          num_steps: 4,
        });
        const r2Key = `projects/${projectId}/scene_${scene.scene_id}.jpg`;
        await env.MEDIA_BUCKET.put(r2Key, aiImage.image);
        scene.image_r2_url = r2Key;
      }

      await env.DB.prepare(
        `UPDATE projects SET status = 'rendering', script_json = ?1 WHERE id = ?2`
      )
        .bind(JSON.stringify(storyboard), projectId)
        .run();

      // Step 3 & 4: Dispatch to Python FFmpeg + Edge-TTS Render Container
      await fetch(`${env.RENDER_WORKER_URL}/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          video_type: body.video_type,
          voice: "en-US-AndrewNeural",
          title: storyboard.title,
          description: storyboard.description,
          tags: storyboard.tags ?? [],
          scenes: storyboard.scenes,
        }),
      });

      return Response.json({ ok: true, project_id: projectId, status: "rendering" });
    }

    return Response.json({ error: "Not found" }, { status: 404 });
  },
};
