# review-inference Specification

## Purpose
TBD - created by archiving change bootstrap-sherpa-mvp. Update Purpose after archive.
## Requirements
### Requirement: Local-only inference

The system SHALL run all LLM inference on the operator's local workstation (RTX 3090, 24GB VRAM). The inference path SHALL NOT call any external LLM API, embedding API, or third-party hosted service. This is a hard constraint motivated by IP protection.

#### Scenario: Inference invoked while offline

- **WHEN** the inference service is invoked on a machine with no outbound network access to public LLM providers
- **THEN** the service still produces a pre-flight comment using only the local LLM runtime and local indices

#### Scenario: New dependency reaches for a remote model

- **WHEN** a code change introduces a client targeting an external LLM/embedding endpoint
- **THEN** the change is rejected during review as a violation of this requirement

### Requirement: Spec/RAG split of responsibilities

The system SHALL split the LLM context between two sources with non-overlapping roles:

- **Spec layer (`SKILL.md` and OpenSpec docs)** governs *form*: comment structure templates, tone rules, category prefix usage, forbidden phrasings, and domain checklists (e.g. real-time / EtherCAT / synchronization-sensitive areas).
- **RAG layer** supplies *examples of judgment*: past senior review comments whose `resolution_type = 'addressed'`, surfaced for similarity to the current PR's diff.

Both layers are concatenated into the final prompt; neither replaces the other.

#### Scenario: Tone change requested

- **WHEN** the team wants to change the comment tone (e.g. forbid imperative phrasing)
- **THEN** the change is made by editing the spec/SKILL.md, not by relabeling RAG examples

#### Scenario: New domain hazard learned

- **WHEN** a new pattern of senior concern emerges (e.g. a recurring deadlock pitfall)
- **THEN** representative `addressed` senior comments enter the RAG index; no spec edit is required for the model to start surfacing the pattern

### Requirement: RAG retrieval scope and seed corpus

The system SHALL retrieve, for each new PR, the top-N most similar past senior comments that are labeled `accept` (or, prior to the first weekly review cycle, that auto-pass the heuristic of: senior author AND `resolution_type = 'addressed'` AND parent PR merged) and inject them into the prompt as exemplars. The MVP seed corpus SHALL be the past six months of such comments from the team repo.

#### Scenario: New PR with diff similar to a known pattern

- **WHEN** an inference run starts for a PR whose diff is semantically similar to past `accept`-labeled comments
- **THEN** those comments appear in the prompt with their original PR/comment ids preserved, so the operator can audit which exemplars influenced output

#### Scenario: Empty index on first run

- **WHEN** the inference service runs before the seed corpus has been built
- **THEN** the service still emits a pre-flight comment using only the spec layer, and logs that no RAG exemplars were available

### Requirement: Single integrated pre-flight comment per PR

The MVP inference output SHALL be a single integrated comment for the entire PR, not per-line inline comments. The output text SHALL begin with the prefix `[pre-flight]` so it is unmistakable as an AI pre-flight pass and never approves the PR.

#### Scenario: Inference produces output for a new PR

- **WHEN** the inference service runs on a new PR and the LLM returns a draft
- **THEN** the bot integration receives a single string body that starts with `[pre-flight]` and is destined for the PR-level comments thread, not for inline review threads

#### Scenario: LLM returns an "approve"-shaped output

- **WHEN** the LLM's draft suggests approval or LGTM-style language
- **THEN** the inference service strips or rejects such phrasing before passing the body to the bot, preserving the principle that AI never approves

### Requirement: Auditable prompt assembly

For every inference run the system SHALL log, in a form readable by the operator, the inputs that produced the comment: PR id, diff slice used, spec/SKILL.md version hash, and the ids of every RAG exemplar included.

#### Scenario: Operator audits an unexpected comment

- **WHEN** the operator wants to understand why a particular pre-flight comment was generated
- **THEN** they can retrieve the full input set (diff slice, spec version, exemplar ids) for that run from local logs

### Requirement: Inference component is a standalone CLI

The inference service SHALL expose a CLI entry point that accepts a PR identifier and prints the generated pre-flight body to stdout, independent of the GitHub Action trigger.

#### Scenario: Operator dry-runs inference locally

- **WHEN** the operator invokes the inference CLI on a closed historical PR
- **THEN** the CLI runs end-to-end and prints the body without posting anything to GitHub

