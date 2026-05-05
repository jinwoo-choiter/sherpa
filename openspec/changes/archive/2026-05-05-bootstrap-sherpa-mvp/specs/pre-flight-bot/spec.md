## ADDED Requirements

### Requirement: Posting is performed by a dedicated bot identity

The system SHALL post pre-flight comments using a dedicated GitHub identity (`@sherpa-bot` or a team-namespaced equivalent), authenticated with a bot PAT or a GitHub App token. The system SHALL NOT post under any operator's personal GitHub account.

#### Scenario: Operator misconfigures with a personal token

- **WHEN** the bot is started with credentials that resolve to a human team member's GitHub login
- **THEN** the bot refuses to start and emits an error pointing to the bot-account requirement

#### Scenario: PR receives a pre-flight comment

- **WHEN** the bot posts to a PR
- **THEN** the comment is authored by the bot identity and is therefore filterable in GitHub's UI by author

### Requirement: AI never produces an approval action

The bot SHALL NOT, under any circumstance, submit a GitHub review with state `APPROVED` (or any equivalent merge-unblocking action). The bot SHALL only post issue-level comments. Human LGTM remains the merge condition.

#### Scenario: Inference output suggests approval

- **WHEN** the upstream inference output contains approval-style content
- **THEN** the bot still posts as a plain comment and never calls the GitHub Reviews API with `event: APPROVE`

#### Scenario: Code path attempts to call review-approval API

- **WHEN** any code path invokes the GitHub `submitReview` API
- **THEN** that change is rejected during review as a violation of the pre-flight-only contract

### Requirement: Single integrated comment per PR with `[pre-flight]` prefix

For each PR run, the bot SHALL post exactly one integrated comment whose body starts with `[pre-flight]`. Inline per-line comments are out of scope for the MVP.

#### Scenario: First run on a new PR

- **WHEN** the GitHub Action triggers for a newly opened PR
- **THEN** the bot posts one comment beginning with `[pre-flight]` to the PR's issue conversation, not a review with inline threads

#### Scenario: Action retried on the same PR

- **WHEN** the Action fires again for a PR that already has a `[pre-flight]` bot comment
- **THEN** the bot does not duplicate-post; it either updates the existing comment or skips, but does not flood the PR

### Requirement: GitHub Action trigger only

The MVP SHALL trigger inference solely through a GitHub Action listening on PR events from the team repo. Webhook receivers, polling-based triggers, or chat-based triggers are out of scope for the MVP.

#### Scenario: New PR opens

- **WHEN** a developer opens a new PR in the configured team repo
- **THEN** the configured GitHub Action runs, calls into the local inference service over the operator's tunnel/runner, and the bot posts the resulting pre-flight comment

#### Scenario: Non-PR event fires

- **WHEN** an event other than a PR open/sync arrives (e.g. issue comment, push to default branch)
- **THEN** the Action does not invoke inference

### Requirement: Local-runner topology for inference

The Action SHALL reach the local inference service via a self-hosted GitHub runner (or equivalent operator-controlled tunnel) so that PR diffs, prompts, and outputs do not transit external CI infrastructure beyond GitHub itself. This preserves the IP-protection constraint that motivates local-only inference.

#### Scenario: Action runs on a hosted runner by mistake

- **WHEN** the workflow attempts to execute on a GitHub-hosted runner
- **THEN** the workflow fails fast with an explicit error, rather than degrading to a remote inference path

### Requirement: Bot is a standalone component with its own CLI

The bot integration SHALL be implemented as its own component (`bot/`) with a CLI that accepts a PR id plus a body and posts (or updates) the pre-flight comment, so the operator can post manually if the Action path is unavailable.

#### Scenario: Action runner is down

- **WHEN** the GitHub Action runner is offline and a PR needs a pre-flight pass
- **THEN** the operator runs the bot CLI directly with the inference output and the comment is posted normally
