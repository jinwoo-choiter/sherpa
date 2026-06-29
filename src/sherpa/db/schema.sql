-- Sherpa SQLite schema. Spec §4 / pr-data-ingestion.
-- Five tables. Pre-allocated columns are NULL-allowed but MUST exist from migration 0.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pull_requests (
    id                TEXT PRIMARY KEY,            -- GitHub PR node id
    repo              TEXT NOT NULL,
    number            INTEGER NOT NULL,
    opened_at         TIMESTAMP NOT NULL,
    merged_at         TIMESTAMP,
    status            TEXT NOT NULL CHECK (status IN ('open', 'merged', 'closed')),
    author_hash       TEXT NOT NULL,
    cycle_time_hours  REAL                          -- derived; nullable
);

CREATE INDEX IF NOT EXISTS idx_pull_requests_repo_number
    ON pull_requests(repo, number);

CREATE TABLE IF NOT EXISTS review_comments (
    id          TEXT PRIMARY KEY,                   -- GitHub comment id
    pr_id       TEXT NOT NULL REFERENCES pull_requests(id),
    author_hash TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('senior', 'peer', 'bot')),
    file_path   TEXT,                               -- NULL = PR-level comment
    line_range  TEXT,                               -- 'start-end'
    body        TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL,
    category    TEXT                                -- nullable; future heuristic / LLM tag
);

CREATE INDEX IF NOT EXISTS idx_review_comments_pr ON review_comments(pr_id);
CREATE INDEX IF NOT EXISTS idx_review_comments_role ON review_comments(role);

CREATE TABLE IF NOT EXISTS code_diffs (
    id         TEXT PRIMARY KEY,
    pr_id      TEXT NOT NULL REFERENCES pull_requests(id),
    commit_sha TEXT NOT NULL,
    file_path  TEXT NOT NULL,
    line_range TEXT NOT NULL,
    diff_text  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_code_diffs_pr ON code_diffs(pr_id);
CREATE INDEX IF NOT EXISTS idx_code_diffs_pr_file ON code_diffs(pr_id, file_path);

CREATE TABLE IF NOT EXISTS comment_outcomes (
    comment_id         TEXT PRIMARY KEY REFERENCES review_comments(id),
    resulted_in_change BOOLEAN NOT NULL,
    linked_diff_id     TEXT REFERENCES code_diffs(id),
    resolution_type    TEXT NOT NULL
        CHECK (resolution_type IN ('addressed', 'discussed', 'dismissed', 'ignored'))
);

CREATE TABLE IF NOT EXISTS learning_labels (
    comment_id      TEXT PRIMARY KEY REFERENCES review_comments(id),
    label           TEXT NOT NULL
        CHECK (label IN ('accept', 'reject:nit', 'reject:outdated', 'reject:individual-style')),
    labeled_by_hash TEXT NOT NULL,
    labeled_at      TIMESTAMP NOT NULL,
    weekly_pr_url   TEXT
);

-- Tacit-knowledge store (capability knowledge-capture). Separate from the spec
-- layer; provenance is comment ids only — never a plaintext login (D5/D10).
CREATE TABLE IF NOT EXISTS knowledge_entries (
    id                 TEXT PRIMARY KEY,            -- stable hash of source comment ids
    status             TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'active', 'rejected')),
    body               TEXT NOT NULL,
    source_comment_ids TEXT NOT NULL,               -- JSON array of comment ids (provenance)
    diff_excerpt       TEXT NOT NULL DEFAULT '',
    created_at         TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge_entries(status);
