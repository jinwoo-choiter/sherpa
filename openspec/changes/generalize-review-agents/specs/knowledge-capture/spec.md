## ADDED Requirements

### Requirement: Tacit-knowledge store kept separate from the spec layer

The system SHALL maintain a team tacit-knowledge store that is distinct from the spec/form layer (`SKILL.md` and OpenSpec docs). The store captures recurring senior judgment — the team-specific concerns a frontier agent cannot infer from code alone (e.g. real-time / synchronization hazards, local conventions). The store is curated as an asset in its own right and is designed to later inform spec/convention proposals, but spec evolution itself is out of scope for this capability.

#### Scenario: Knowledge concern that the spec does not encode

- **WHEN** a team-specific concern recurs in senior reviews but is not expressible as a form/tone rule
- **THEN** it is recorded in the tacit-knowledge store, not in `SKILL.md`, and remains available for injection into future reviews

#### Scenario: Store consulted independently of any single review

- **WHEN** an operator inspects accumulated team knowledge
- **THEN** the store is readable as a standalone asset, independent of any one PR or review run

### Requirement: Candidate distillation from review outcomes (good-cases-only)

The system SHALL distill candidate tacit-knowledge entries from `comment_outcomes`, restricted to the good-cases-only corpus: senior-authored comments whose `resolution_type = 'addressed'` on a merged PR. The heuristic is a filter for surfacing candidates, not a source of truth.

#### Scenario: Addressed senior comments feed distillation

- **WHEN** distillation runs over the outcomes corpus
- **THEN** only senior-authored, `addressed`, merged-PR comments are eligible as candidate sources, and each candidate records the source comment ids it was derived from

#### Scenario: Outcomes corpus is empty

- **WHEN** distillation runs before any qualifying outcomes exist
- **THEN** no candidates are produced and the run completes without error

### Requirement: Human curation gate before an entry becomes active

A distilled candidate SHALL NOT be injected into reviews until a human confirms it. Only human-confirmed entries are "active"; candidates and rejected entries SHALL NOT influence review context. This preserves the principle that automated heuristics select candidates but never silently become team knowledge.

#### Scenario: Candidate awaits confirmation

- **WHEN** a candidate has been distilled but not yet confirmed by a human
- **THEN** it is excluded from the context injected into any review run

#### Scenario: Human rejects a candidate

- **WHEN** a curator rejects a distilled candidate
- **THEN** the entry is marked rejected and is never injected, and is not re-proposed as a fresh candidate from the same source comments

### Requirement: Injection of relevant active knowledge into review context

For each review run the system SHALL inject the active tacit-knowledge entries most relevant to the current PR's diff into the agent's review context, as the team-specific judgment layer that complements the spec/form layer.

#### Scenario: PR resembles a known knowledge entry

- **WHEN** a review starts for a PR whose diff is similar to an active tacit-knowledge entry
- **THEN** that entry is injected into the agent's context, and its identity is recorded in the run's audit record so the operator can see which knowledge influenced the review

#### Scenario: No active knowledge yet

- **WHEN** a review runs while the store has no active entries
- **THEN** the review proceeds using only the spec/form layer and the run records that no knowledge entries were injected

### Requirement: Author anonymization preserved in the knowledge store

The tacit-knowledge store SHALL NOT persist raw GitHub logins. Entries reference their provenance by source comment id and/or `author_hash`, consistent with ingest-time anonymization.

#### Scenario: Entry references its source

- **WHEN** a tacit-knowledge entry is created from senior comments
- **THEN** its provenance is recorded as comment ids and/or `author_hash`, and no plaintext author login is stored anywhere in the entry
