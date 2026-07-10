-- Schema definition for Mehndi Recommendation System SQLite Database

-- Catalog of designs
CREATE TABLE IF NOT EXISTS designs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    complexity TEXT NOT NULL,
    occasion TEXT NOT NULL,
    tags TEXT
);

-- Users session/auth
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL
);

-- User preferences and likes
CREATE TABLE IF NOT EXISTS preferences (
    user_id INTEGER NOT NULL,
    liked_design_ids TEXT, -- Comma-separated list of design IDs
    filter_history TEXT,   -- JSON string of past search filters
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Recommendation tracking and interaction logs
CREATE TABLE IF NOT EXISTS recommendation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    design_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    was_liked INTEGER DEFAULT 0, -- 0 for false, 1 for true
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(design_id) REFERENCES designs(id) ON DELETE CASCADE
);
