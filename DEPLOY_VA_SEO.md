# Kontentor AI — Cloudflare, Google Cloud va Google Qidiruv (#1 SEO) Yo‘riqnomasi

Ushbu hujjatda `Kontentor` tizimini **Cloudflare** va **Google Cloud** ga joylash (deploy qilish) hamda **Google Search Console** orqali Google qidiruvda **1-o‘ringa chiqarish** qadamlari keltirilgan.

---

## 1. Ideal Bepul AI Uchlik (Ulangan Arxitektura)

1. **Miya, Ssenariy va Sifat Nazorati (Vision QC):**
   - **GPT-6 Luna** (`Experiential API`) + **Gemini 4 Hydrogen** (`gemini-4-hydrogen`).
   - Ssenariy va JSON promptlarni yozadi hamda `verify_image_with_hydrogen()` funksiyasi orqali chizilgan rasmlarda xatolik yo‘qligini (Vision orqali ko‘rib) tekshiradi!
2. **Rassom (0 dan Kadrlar Chizish):**
   - **Cloudflare Workers AI (`@cf/black-forest-labs/flux-1-schnell`)** — kuniga 10,000 bepul neyron (50–100 ta HD rasm mutlaqo bepul).
3. **Diktor va Subtitr + Montaj:**
   - **Python `edge-tts` (`en-US-AndrewNeural` / `en-US-BrianNeural` / `Mark`)** + **FFmpeg** (Zoom-in / Ken Burns + `.srt` subtitr).

---

## 2. Cloudflare’ga Deploy Qilish (`/web`)

`web/wrangler.toml` ichiga Cloudflare Account ID (`.env` dagi `CF_ACCOUNT_ID`) ulanadi.

```bash
cd web
npm install

# 1. D1 bazani yaratish va migratsiya qilish
npx wrangler d1 create kontentor-db
# Chiqqan database_id ni wrangler.toml ga qo'ying, so'ng:
npx wrangler d1 migrations apply kontentor-db --remote

# 2. R2 bucket yaratish
npx wrangler r2 bucket create kontentor-media

# 3. Maxfiy API kalitlarni Cloudflare'ga xavfsiz yuklash
npx wrangler secret put LUNA_API_KEY
npx wrangler secret put GEMINI_API_KEY

# 4. Cloudflare'ga deploy qilish
npx wrangler deploy
```

---

## 3. Python FFmpeg Render Konteynerini Google Cloud Run’ga Joylash (`/render-worker`)

Google Cloud Console ichidagi **Cloud Run** oyiga 2 million so‘rovgacha bepul (Free Tier) ishlaydi:

```bash
cd render-worker
gcloud run deploy kontentor-render-worker \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2
```
Deploy bo‘lgach, chiqqan `https://kontentor-render-worker-...run.app` manzilini `web/wrangler.toml` dagi `RENDER_WORKER_URL` ga yozib qo‘yasiz.

---

## 4. Google Search Console’da 1-o‘ringa Chiqarish (SEO)

Saytingiz va videolaringiz Google qidiruvda 1-o‘rinda chiqishi uchun barcha texnik SEO qismlar ([web_ui/index.html](file:///Users/sohibjonsulaymonov/kodlar/kontentor/web_ui/index.html), [server.py](file:///Users/sohibjonsulaymonov/kodlar/kontentor/server.py) va [web/src/index.ts](file:///Users/sohibjonsulaymonov/kodlar/kontentor/web/src/index.ts)) tayyorlab qo‘yildi:

1. **Schema.org JSON-LD (`SoftwareApplication` + `VideoObject`):** Google botlari saytingizga kirganda videolarni Google Video karuselida 1-o‘rinda chiqarishi uchun maxsus mikro-razmetka qo‘shildi.
2. **Avtomatik Sitemap va Robots:**
   - `https://sizning-domeningiz/sitemap.xml`
   - `https://sizning-domeningiz/robots.txt`
3. **Google Search Console’ga ulash (3 daqiqa):**
   - [Google Search Console](https://search.google.com/search-console) ga kiring va Cloudflare domeningizni qo‘shing.
   - Berilgan tasdiqlash kodini [web_ui/index.html](file:///Users/sohibjonsulaymonov/kodlar/kontentor/web_ui/index.html) ning 9-qatoridagi `GOOGLE_SEARCH_CONSOLE_VERIFICATION_CODE` o‘rniga qo‘ying.
   - Chap menyudan **Sitemaps** bo‘limiga kirib, `sitemap.xml` deb yuboring — Google saytingiz va videolaringizni darhol indeksatsiya qiladi!
