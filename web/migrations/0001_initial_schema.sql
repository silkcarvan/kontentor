-- ============================================================================
-- KONTENTOR AI YOUTUBE AUTOMATION SAAS — CLOUDFLARE D1 INITIAL MIGRATION
-- ============================================================================
PRAGMA foreign_keys = ON;

-- 1. USERS TABLE (Closed Beta Admin-Only Provisioning + Future SaaS Credits)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    plan TEXT NOT NULL DEFAULT 'closed_beta' CHECK (plan IN ('closed_beta', 'starter', 'pro')),
    shorts_credits INTEGER NOT NULL DEFAULT 100 CHECK (shorts_credits >= 0),
    long_credits INTEGER NOT NULL DEFAULT 20 CHECK (long_credits >= 0),
    plan_expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 2. YOUTUBE CHANNELS TABLE (OAuth2 Tokens & Channel Binding per User)
CREATE TABLE IF NOT EXISTS youtube_channels (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel_id TEXT,
    channel_title TEXT NOT NULL,
    niche TEXT DEFAULT 'Central Asian History & Culture',
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expiry TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_youtube_channels_user_id ON youtube_channels(user_id);

-- 3. PROJECTS TABLE (4-Stage Video Pipeline Tracking + R2 & YouTube Links)
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel_id TEXT,
    topic TEXT NOT NULL,
    video_type TEXT NOT NULL CHECK (video_type IN ('shorts', 'long')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'generating_assets', 'rendering', 'uploading', 'published', 'failed')
    ),
    script_json TEXT,
    final_video_r2_url TEXT,
    youtube_video_id TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES youtube_channels(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_user_status ON projects(user_id, status);

-- 4. SELF-LEARNING & ANALYTICS TABLE (Channel Memory & Retention Optimization)
CREATE TABLE IF NOT EXISTS channel_analytics_memory (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    project_id TEXT,
    views INTEGER DEFAULT 0,
    ctr_percent REAL DEFAULT 0.0,
    avg_view_percentage REAL DEFAULT 0.0,
    drop_off_second INTEGER DEFAULT 0,
    learned_rule TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (channel_id) REFERENCES youtube_channels(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);
