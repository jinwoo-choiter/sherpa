# pr-data-ingestion Specification

## Purpose
TBD - created by archiving change bootstrap-sherpa-mvp. Update Purpose after archive.
## Requirements
### Requirement: Daily polling of GitHub PRs and review comments

The system SHALL poll the configured team GitHub repository on a daily batch schedule and persist new pull requests and their review comments to a local SQLite database. Webhook-based real-time processing is explicitly out of scope for the MVP.

#### Scenario: New PR opened since last poll

- **WHEN** the polling job runs and detects a pull request opened or updated since the last successful poll watermark
- **THEN** the system inserts a row in `pull_requests` with `id`, `repo`, `number`, `opened_at`, `merged_at` (nullable), `status`, and `author_hash`, and ingests all associated review comments into `review_comments`

#### Scenario: Polling job fails partway through

- **WHEN** the polling job aborts after partially writing rows
- **THEN** the polling watermark is NOT advanced, and the next run re-fetches the unfinished window so no PRs are silently dropped

### Requirement: Author identifiers are anonymized at write time

The system SHALL store author identifiers only as `author_hash = hash(salt + github_login)` and SHALL NOT persist raw GitHub logins anywhere in the database. The salt SHALL be readable only by the operator and SHALL NOT be checked into the system code repository.

#### Scenario: Ingest writes a comment author

- **WHEN** the ingester records a `review_comments` row
- **THEN** the `author_hash` column contains the salted hash and no row in any table contains the raw GitHub login

#### Scenario: Salt is missing at startup

- **WHEN** the ingester starts without a configured salt
- **THEN** the process exits with a non-zero status and a clear error, rather than ingesting un-salted data

### Requirement: Comment outcome detection via git blame heuristic

The system SHALL classify every ingested review comment with a `resolution_type` in `comment_outcomes` using post-comment commits as evidence. The four resolution types and their heuristics are normative:

- `addressed` — the commented line(s) are changed by a commit authored after the comment, per git blame.
- `discussed` — five or more follow-up comments AND code on the line range was changed.
- `dismissed` — follow-up comments contain a rebuttal pattern AND no code change AND the PR was merged.
- `ignored` — no follow-up activity AND the PR was merged.

The heuristic does not need to be perfect; it is used as a learning-corpus filter, not a ground-truth classifier.

#### Scenario: Senior comment leads to a fix

- **WHEN** a senior reviewer leaves a comment on lines L1–L2 of file F, and a later commit on the same PR modifies any line in L1–L2
- **THEN** the system writes `comment_outcomes` with `resolution_type = 'addressed'`, `resulted_in_change = TRUE`, and `linked_diff_id` referencing the post-comment diff

#### Scenario: PR merges with no follow-up

- **WHEN** a comment receives no replies and no commit modifies the commented lines, and the PR is merged
- **THEN** the system writes `comment_outcomes` with `resolution_type = 'ignored'` and `resulted_in_change = FALSE`

### Requirement: SQLite schema for ingestion

The system SHALL maintain a single SQLite file with the five tables `pull_requests`, `review_comments`, `code_diffs`, `comment_outcomes`, and `learning_labels` as specified in the project document §4. Pre-allocated columns intended for future use MAY be NULL but MUST exist from the first migration.

#### Scenario: Fresh database initialization

- **WHEN** the system runs against an empty SQLite file
- **THEN** all five tables are created with the documented columns and primary/foreign-key constraints, including columns currently allowed to be NULL (e.g. `review_comments.category`)

#### Scenario: Direct SQL outside the db module

- **WHEN** any module other than `db/` constructs raw SQL strings against the schema
- **THEN** review of that change is rejected; all schema access goes through `db/` helpers

### Requirement: Component CLIs for operational debugging

Each ingestion-related component (ingester, outcome detector) SHALL expose a standalone CLI entry point that can be invoked without the rest of the system running, to support operational debugging.

#### Scenario: Operator re-runs outcome detection for one PR

- **WHEN** the operator invokes the outcome-detector CLI with a PR id
- **THEN** the CLI re-evaluates `comment_outcomes` for that PR's comments and reports what changed, without requiring the polling job to be running

