## REMOVED Requirements

### Requirement: Local-only inference

**Reason**: The IP-protection constraint that mandated local-only inference has been resolved at the organization level — sanctioned CLI agents (Claude, Codex) are approved for in-house use. The "weak local model compensated by RAG" architecture no longer has a reason to exist.

**Migration**: Inference now runs via sandboxed, sanctioned CLI agents (see ADDED: *Pluggable review-agent abstraction* and *Sandboxed read-only agent execution*). The safety guarantee shifts from network-locality to three replacements: (a) a human approval gate plus a deterministic whitelist gate (see `pre-flight-bot`), (b) sandboxed read-only agent execution, and (c) trajectory audit (see MODIFIED: *Auditable agent trajectory*). The `_assert_local` guard in `inference/llm.py` is retained only on the legacy Ollama adapter.

## MODIFIED Requirements

### Requirement: Spec/RAG split of responsibilities

The system SHALL split the review context between two sources with non-overlapping roles:

- **Spec layer (`SKILL.md` and OpenSpec docs)** governs *form*: comment structure templates, tone rules, category prefix usage, forbidden phrasings, and domain checklists.
- **Knowledge layer (tacit-knowledge store)** supplies *examples of judgment*: human-curated, team-specific concerns relevant to the current PR's diff (see capability `knowledge-capture`).

Both layers are injected into the agent's context; neither replaces the other. The agentic model brings general code-review competence, so the knowledge layer's role is to encode team-specific tacit knowledge the model cannot infer from code — not to compensate for a weak model.

#### Scenario: Tone change requested

- **WHEN** the team wants to change the comment tone (e.g. forbid imperative phrasing)
- **THEN** the change is made by editing the spec/`SKILL.md`, not by relabeling knowledge entries

#### Scenario: New domain hazard learned

- **WHEN** a new pattern of senior concern emerges (e.g. a recurring deadlock pitfall)
- **THEN** it enters the tacit-knowledge store via `knowledge-capture`; no spec edit is required for the model to start surfacing the pattern

### Requirement: RAG retrieval scope and seed corpus

For each review the system SHALL inject the top-N active tacit-knowledge entries most similar to the current PR's diff as the judgment layer. Relevance is computed against the human-curated store maintained by `knowledge-capture`; the system SHALL preserve the provenance (entry ids, source comment ids) of every injected entry for audit.

#### Scenario: New PR with diff similar to a known pattern

- **WHEN** a review run starts for a PR whose diff is semantically similar to active knowledge entries
- **THEN** those entries are injected into the agent context with their ids preserved, so the operator can audit which knowledge influenced the review

#### Scenario: Empty store on first run

- **WHEN** the review service runs before any active knowledge entries exist
- **THEN** the service still produces a review using only the spec layer, and records that no knowledge entries were injected

### Requirement: Single integrated pre-flight comment per PR

The review service SHALL produce a structured `ReviewResult` for the PR, not a single free-form prose body. The `ReviewResult` SHALL contain: a reviewer-oriented summary (intent, where risk/complexity concentrates, where to focus), zero or more inline findings (each anchored to file and line range), category evidence (machine-readable signals describing what kind of change the PR is), and open questions. The category evidence is input for the deterministic approve gate (see `pre-flight-bot`); the model SHALL NOT emit an approval decision.

#### Scenario: Review produces output for a new PR

- **WHEN** the review service runs on a new PR
- **THEN** it returns a structured `ReviewResult` (summary + inline findings + category evidence + open questions), destined for the triage router, not a single prose comment

#### Scenario: Model output suggests approval

- **WHEN** the agent's output contains approval or LGTM-style language
- **THEN** such phrasing is stripped or rejected, and no field of the `ReviewResult` is treated as an approval — approval is decided only by the deterministic gate

### Requirement: Auditable prompt assembly

For every review run the system SHALL log, in a form readable by the operator, the inputs and the agent's trajectory that produced the output: PR id, diff slice considered, spec/`SKILL.md` version hash, the ids of every injected knowledge entry, the agent name/version and model id, the files the agent read and commands it ran (best-effort per adapter), and a reference to the agent's raw session transcript.

#### Scenario: Operator audits an unexpected review

- **WHEN** the operator wants to understand why a particular review was produced
- **THEN** they can retrieve the full input set and the agent's trajectory (injected knowledge ids, files read, commands run, raw transcript reference) for that run from local logs

### Requirement: Inference component is a standalone CLI

The review service SHALL expose a CLI entry point that accepts a PR identifier, runs end-to-end, and prints the structured `ReviewResult` without posting anything to GitHub. The CLI SHALL accept an agent selector that overrides the configured default agent for that run.

#### Scenario: Operator dry-runs a review locally

- **WHEN** the operator invokes the review CLI on a closed historical PR
- **THEN** the CLI runs end-to-end and prints the `ReviewResult` without posting to GitHub

#### Scenario: Operator overrides the agent for one run

- **WHEN** the operator passes an agent selector (e.g. `--agent codex`) that differs from the configured default
- **THEN** the run uses the selected agent and the audit record names which agent produced the result

## ADDED Requirements

### Requirement: Pluggable review-agent abstraction

The system SHALL run inference through a single `ReviewAgent` contract implemented by per-tool adapters (e.g. Claude, Codex, legacy Ollama). The contract accepts a prepared review task (repo checkout, PR metadata, injected knowledge, form spec, output schema) and returns a structured `ReviewResult` plus a trajectory record. The active agent SHALL be chosen by a configured default with an optional per-run override; adding a new agent SHALL NOT require changes to callers of the contract. Output SHALL be coaxed into the system's own result schema (not dependent on any one tool's native output format).

#### Scenario: Adding a new agent

- **WHEN** a new CLI agent is integrated by implementing the adapter contract
- **THEN** existing callers (triage, bot, audit) work unchanged because they depend only on `ReviewResult` and the trajectory record

#### Scenario: Configured default with no override

- **WHEN** a review runs with no per-run agent override
- **THEN** the configured default agent is used

### Requirement: Sandboxed read-only agent execution

Because PR content is untrusted (a PR diff may carry prompt-injection attempting to subvert the review), the system SHALL run every agent in a sandboxed, read-only mode: no file mutation, no `git push`, and no network access beyond the sanctioned model/agent endpoint. The agent SHALL NOT be able to perform or authorize a merge-affecting action; approval authority lives outside the agent (see `pre-flight-bot`).

#### Scenario: Agent attempts a mutating action

- **WHEN** an agent (or PR content steering it) attempts to write files, push, or reach a disallowed network endpoint
- **THEN** the action is blocked by the sandbox and the attempt is recorded in the trajectory

#### Scenario: PR content attempts prompt injection to approve

- **WHEN** a PR's diff contains text instructing the agent to approve the PR
- **THEN** at most the agent's free-form output is affected; it cannot approve, because the approval decision is made by the deterministic gate outside the agent
