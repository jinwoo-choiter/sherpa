# Sherpa

Self-hosted, local-LLM code review assistant. Posts a single integrated `[pre-flight]` comment per PR. **Never approves.**

Spec authority: see `openspec/changes/bootstrap-sherpa-mvp/` (proposal, design, specs, tasks). The principles in §2 of the project document — pre-flight ≠ approval, ingest-time anonymization, "good cases only" learning corpus — are normative; this README is operator playbook.

## Layout

```
src/sherpa/
  config.py        # salt loading, env, role mapping
  anon.py          # author_hash(salt, login) — never persists raw login
  db/              # schema.sql + repo.py — single SQL surface
  ingester/        # GitHub poll → SQLite (anonymized)
  outcomes/        # comment_outcomes heuristic (4 resolution_types)
  rag/             # senior+addressed seed index + retriever
  inference/       # Ollama wrapper + prompt assembly + postprocess + audit
  bot/             # idempotent [pre-flight] comment poster
.github/workflows/
  sherpa-preflight.yml  # self-hosted runner only; refuses hosted runners
tests/             # no-approve lock-in, anon fail-fast, postprocess invariants
```

Each component is a standalone CLI (`python -m sherpa.<component> ...`). DB access is confined to `sherpa.db`; other modules MUST NOT write SQL.

## Day 0 — operator setup (one-time, NOT automated)

1. Create a dedicated GitHub bot account (`sherpa-bot` or team-namespaced equivalent). Issue a PAT or GitHub App token. **Never use a personal account.**
2. Register a self-hosted GitHub Actions runner on the workstation with label `sherpa-local`.
3. Create separate repos for: system code (this repo), data (SQLite), RAG index, convention spec (`SKILL.md`).
4. Generate the salt file: `head -c 32 /dev/urandom | base64 > ~/sherpa-salt && chmod 0400 ~/sherpa-salt`.
5. Install Python 3.11+, `uv` (or `pip-tools`), `ruff`, `mypy`. Install Ollama and pull the LLM/embedding models.
6. Create JSON files listing GitHub logins for `seniors` and `bots`:
   ```json
   ["alice", "bob"]
   ```

### Required environment variables

| Var | Purpose |
|---|---|
| `SHERPA_GH_TOKEN` | bot account token |
| `SHERPA_SALT_PATH` | path to salt file (0400 in operator $HOME) |
| `SHERPA_DB_PATH` | SQLite file path (in the data repo, not this one) |
| `SHERPA_RAG_DIR` | RAG index dir (in the index repo) |
| `SHERPA_AUDIT_DIR` | local dir for inference audit JSON |
| `SHERPA_STATE_PATH` | poll watermark JSON |
| `SHERPA_SENIORS_PATH` | JSON array of senior logins |
| `SHERPA_BOTS_PATH` | JSON array of bot logins (must include the running bot) |
| `SHERPA_SKILL_MD` | convention spec path (defaults to a built-in fallback) |
| `OLLAMA_BASE_URL` | default `http://127.0.0.1:11434` (loopback enforced) |
| `SHERPA_LLM_MODEL` | default `qwen2.5-coder:32b-instruct-q4_K_M` |
| `SHERPA_EMBED_MODEL` | default `nomic-embed-text` (revisit after measurement) |

## Day-to-day operation

```bash
# 1. Initialize schema (once)
python -m sherpa.db init

# 2. Daily poll (cron-driven)
python -m sherpa.ingester poll <owner>/<repo>

# 3. Recompute outcomes after a poll
python -m sherpa.outcomes recompute            # all PRs
python -m sherpa.outcomes recompute --pr <id>  # single PR

# 4. (Re)build the RAG seed index after outcomes are fresh
python -m sherpa.rag build

# 5. Dry-run inference for a PR — never posts
python -m sherpa.inference run --pr <node-id>

# 6. Manual fallback post if the Action runner is down
python -m sherpa.bot post --pr owner/repo#123 --body-file body.txt
```

Recommended cron (operator workstation):

```
# 02:00 KST daily poll then outcome recompute
0 17 * * * SHERPA_SALT_PATH=... ... python -m sherpa.ingester poll owner/repo && python -m sherpa.outcomes recompute
```

## Metrics queries (project doc §7.1) and kill thresholds (§7.2)

These are deliberate, run-on-demand SQL — automated reporting is out of MVP scope. Kill thresholds are annotated inline; revisit quarterly.

```sql
-- §7.1 PR cycle time (hours), team average + percentiles. No individual stats.
SELECT
  AVG(cycle_time_hours)                                          AS avg_hours,
  -- Kill if trend regresses while AI is enabled. No fixed threshold; track.
  MIN(cycle_time_hours)                                          AS min_hours,
  MAX(cycle_time_hours)                                          AS max_hours,
  COUNT(*)                                                       AS merged_prs
FROM pull_requests
WHERE status = 'merged'
  AND merged_at >= datetime('now', '-30 days');

-- §7.1 TTFR — open → first human (non-bot) review comment, hours.
SELECT
  AVG((julianday(rc.first_comment_at) - julianday(p.opened_at)) * 24.0) AS avg_ttfr_hours
FROM pull_requests p
JOIN (
  SELECT pr_id, MIN(created_at) AS first_comment_at
  FROM review_comments
  WHERE role <> 'bot'
  GROUP BY pr_id
) rc ON rc.pr_id = p.id
WHERE p.opened_at >= datetime('now', '-30 days');

-- §7.1 AI comment acceptance rate — among bot comments, fraction whose lines
-- were modified in a later commit. Kill threshold: < 25% sustained over 3 months.
SELECT
  ROUND(100.0 * SUM(CASE WHEN co.resulted_in_change THEN 1 ELSE 0 END) / COUNT(*), 1)
    AS ai_acceptance_pct
FROM review_comments rc
JOIN comment_outcomes co ON co.comment_id = rc.id
JOIN pull_requests p ON p.id = rc.pr_id
WHERE rc.role = 'bot'
  AND p.opened_at >= datetime('now', '-90 days');

-- §7.1 Complementarity — substantive human comments on PRs that the bot
-- already reviewed. Kill threshold: == 0 (signal that humans are over-trusting AI).
SELECT COUNT(*) AS human_substantive_after_bot
FROM review_comments human_rc
WHERE human_rc.role <> 'bot'
  AND human_rc.created_at > (
    SELECT MIN(b.created_at) FROM review_comments b
    WHERE b.pr_id = human_rc.pr_id AND b.role = 'bot'
  )
  AND LENGTH(human_rc.body) >= 80   -- coarse "substantive" filter
  AND human_rc.created_at >= datetime('now', '-30 days');
```

If any kill threshold is breached, disable `.github/workflows/sherpa-preflight.yml` and open a redesign change in `openspec/`.

## Operator checklist (review monthly)

- [ ] Salt file permissions still `0400`, owner only
- [ ] Bot account token expiry > 30 days; rotate before expiry
- [ ] Self-hosted runner status = `Idle`/`Active` (not `Offline`)
- [ ] `~/.sherpa/state.json` watermark advancing daily
- [ ] `audit/` directory rotated (keep ≥ 90 days for review reproducibility)
- [ ] Run §7.1 queries; verify kill thresholds are not breached

## Tests

```bash
pip install -e '.[dev]'
pytest
```

Notable invariants under test:
- `tests/test_no_approve.py` — bot package contains no Reviews-API surface (source grep) AND a transport double confirms only `/issues/.../comments` is hit.
- `tests/test_anon.py` — `Config.load()` fails fast when salt is missing, empty, or path unset.
- `tests/test_postprocess.py` — `[pre-flight]` prefix is enforced and approve-style language is stripped.
