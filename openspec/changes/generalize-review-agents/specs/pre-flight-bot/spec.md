## REMOVED Requirements

### Requirement: Local-runner topology for inference

**Reason**: This requirement existed solely to preserve the IP-protection constraint behind local-only inference, which has been removed (sanctioned external CLI agents are now approved). Mandating a self-hosted runner is no longer required for that purpose.

**Migration**: Execution location (self-hosted runner vs. cloud/hosted runner) becomes an operational/design decision rather than a hard spec mandate. Safety is preserved by the human approval gate, the deterministic whitelist gate, sandboxed read-only agent execution, and trajectory audit — not by network topology.

## MODIFIED Requirements

### Requirement: AI never produces an approval action

The agent (model) SHALL NOT, under any circumstance, produce or authorize a GitHub review with state `APPROVED` (or any equivalent merge-unblocking action); no field of the agent's `ReviewResult` is ever treated as an approval. Approval authority lives exclusively in a deterministic gate outside the agent (see ADDED: *Deterministic whitelist binding-approve gate*). The bot SHALL submit an approving review only when that gate authorizes it; in all other cases it posts comments only.

#### Scenario: Inference output suggests approval

- **WHEN** the upstream `ReviewResult` contains approval-style content
- **THEN** the bot does not approve on that basis; approval happens only if the deterministic gate independently authorizes it

#### Scenario: Code path lets the model reach the approval API

- **WHEN** any code path would allow the agent's output to trigger the GitHub `submitReview`/`APPROVE` action
- **THEN** that change is rejected during review as a violation of the "model never approves; only the gate approves" contract

### Requirement: Single integrated comment per PR with `[pre-flight]` prefix

For each PR run the bot SHALL route the `ReviewResult` into one of three outcomes and post idempotently:

- **approve-eligible**: the deterministic gate authorized a binding approval — the bot submits the approving review (and may post a short note); no change-request comments are needed.
- **changes indicated**: the bot posts inline comments anchored to the specific files/lines that need attention.
- **human judgment needed**: the bot posts a reviewer-oriented summary plus "focus here" inline comments to orient a human reviewer.

Bot-authored comment bodies SHALL carry the `[pre-flight]` marker so they remain filterable by author and unmistakable as AI output. Inline per-line comments are now in scope (the anchoring risk that excluded them is mitigated by agentic file access).

#### Scenario: First run on a new PR needing changes

- **WHEN** the trigger fires for a newly opened PR whose `ReviewResult` indicates changes
- **THEN** the bot posts inline comments on the relevant lines, each marked `[pre-flight]`, and does not approve

#### Scenario: Run re-fires on the same PR

- **WHEN** the trigger fires again for a PR the bot already reviewed
- **THEN** the bot updates or skips rather than duplicating, and does not flood the PR with repeated comments

#### Scenario: Human-judgment PR

- **WHEN** the `ReviewResult` indicates the PR needs human judgment
- **THEN** the bot posts a reviewer summary plus focus-routing inline comments, and does not approve

### Requirement: GitHub Action trigger only

The system SHALL trigger a review through a PR hook (event-driven) on PR open/sync/reopen events from the configured repo. The trigger SHALL NOT fire reviews on unrelated events. The separate learning-corpus ingestion (polling) remains an independent track, not a review trigger.

#### Scenario: New PR opens

- **WHEN** a developer opens or updates a PR in the configured repo
- **THEN** the PR hook runs a review and the bot routes the result per the triage outcomes

#### Scenario: Non-PR event fires

- **WHEN** an event other than a PR open/sync/reopen arrives (e.g. issue comment, push to default branch)
- **THEN** no review is triggered

## ADDED Requirements

### Requirement: Deterministic whitelist binding-approve gate

The system SHALL include a deterministic gate, implemented in code outside the agent, that authorizes a binding approval only when **every** changed file in the PR matches an operator-owned whitelist of mechanically-safe categories. The gate SHALL be fail-closed: any non-matching file, mixed PR, or ambiguity routes the PR to human review with no approval. The whitelist definition SHALL be owned by the operator and live outside any PR's reach, so a PR cannot modify the rules that would approve it. The initial whitelist SHALL be conservative (e.g. docs/markdown-only, regenerable generated files, formatting-only changes); categories with weakening or supply-chain risk (e.g. test-weakening changes, dependency lockfile bumps) SHALL be excluded until explicitly added with their own safeguards.

#### Scenario: PR fully within the whitelist

- **WHEN** every changed file matches a whitelisted safe category
- **THEN** the gate authorizes a binding approval and the bot submits the approving review

#### Scenario: Mixed or out-of-whitelist PR

- **WHEN** a PR contains any file outside the whitelist, or the classification is ambiguous
- **THEN** the gate does not approve and the PR is routed to human review (fail-closed)

#### Scenario: PR attempts to modify the whitelist itself

- **WHEN** a PR changes the whitelist definition or any operator-owned gate configuration
- **THEN** that PR is not eligible for self-approval; the gate treats it as out-of-whitelist and routes it to human review

#### Scenario: Agent recommends approval under prompt injection

- **WHEN** the agent's `ReviewResult` recommends approving a PR that changes code outside the whitelist
- **THEN** the gate still refuses approval, because the binding decision depends on deterministic file classification, not on the agent's output

### Requirement: Post-merge safety controls for auto-approval

Because a binding auto-approval can merge a PR with no human in the loop, the system SHALL track every auto-approved PR for a post-merge safety metric (auto-approved-then-reverted/hot-fixed rate) and SHALL provide an operator kill-switch that disables auto-approval without disabling the review/comment path.

#### Scenario: Revert-rate threshold breached

- **WHEN** the auto-approved-then-reverted rate rises beyond the operator's threshold
- **THEN** the operator can disable auto-approval via the kill-switch while reviews and comments continue to run

#### Scenario: Auto-approved PR is later reverted

- **WHEN** a PR that was auto-approved is subsequently reverted or hot-fixed
- **THEN** that event is recorded against the auto-approval safety metric for the whitelist's effectiveness review
