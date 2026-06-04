CREATE TABLE IF NOT EXISTS sheets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL CHECK (kind IN ('character', 'npc')),
    subtype      TEXT NOT NULL,
    name         TEXT NOT NULL,
    data         TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sheets_kind ON sheets(kind);
CREATE INDEX IF NOT EXISTS idx_sheets_name ON sheets(name);
