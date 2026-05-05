## Why

팀 코드 리뷰의 표면적 부담(컨벤션 일관성, 흔한 누락 케이스)이 시니어 리뷰어의 인지 자원을 잠식하고, 첫 리뷰까지의 지연(TTFR)이 개발 사이클을 늘리고 있다. 외부 API 사용은 IP 보호 관점에서 불가하므로, 로컬 워크스테이션(RTX 3090)에서 동작하는 팀 전용 리뷰 보조 시스템 **Sherpa**를 도입한다. 이 변경은 Sherpa의 1주(5일) MVP를 정의하고 구축한다.

핵심 원칙은 **"AI는 Pre-flight이지 Approval이 아니다"** — AI는 사람 리뷰어가 시작하기 전 표면적 항목만 정리하며, 머지 결정은 사람이 한다. 이름과 코멘트 prefix(`[pre-flight]`)에 이 한계를 박아 두어 자동화 편향을 구조적으로 방지한다.

## What Changes

- 팀 GitHub 레포지토리의 PR/코멘트를 일배치 폴링으로 수집해 로컬 SQLite에 적재한다 (개인 식별자는 작성자 해시로 익명화).
- 후속 커밋의 git blame 비교로 코멘트의 `resolution_type`(addressed/discussed/dismissed/ignored)을 자동 판정해 효력 있는 코멘트를 식별한다.
- 로컬 LLM 런타임(Ollama 기준, 코드 특화 30B급 4-bit 양자화 모델 후보)을 워크스테이션에 셋업한다.
- RAG 파이프라인을 구축한다: 과거 6개월 시니어 코멘트 중 `addressed`인 것을 초기 인덱스로 사용하고, 새 PR의 변경 컨텍스트와 함께 프롬프트에 주입한다.
- GitHub Action으로 새 PR에 단일 통합 `[pre-flight]` 코멘트를 자동 게시한다 (라인 인라인 코멘트는 MVP 범위 외).
- 봇 계정(`@sherpa-bot` 또는 동등) 분리, 시스템 코드 / 데이터 / RAG 인덱스 / 컨벤션 spec의 저장소 분리를 운영 사전 결정으로 확정한다.

명시적으로 MVP에서 제외하는 것: 에이전트 통합, 진단 리포트, 주간 컨텍스트 PR 자동 생성, Webhook 실시간 처리, 카테고리 자동 분류, 인라인 코멘트.

## Capabilities

### New Capabilities

- `pr-data-ingestion`: 팀 레포의 PR/리뷰 코멘트/diff/코멘트 outcome을 일배치로 수집·익명화·저장하는 능력. SQLite 5개 테이블(pull_requests, review_comments, code_diffs, comment_outcomes, learning_labels) 스키마를 포함한다.
- `review-inference`: 로컬 LLM과 RAG를 결합해 새 PR에 대한 pre-flight 리뷰 코멘트 초안을 생성하는 능력. 표현 형식 규칙은 spec(SKILL.md)으로, 추론 사례는 RAG로 분담한다.
- `pre-flight-bot`: GitHub Action 트리거를 받아 추론 결과를 `[pre-flight]` prefix가 붙은 단일 통합 코멘트로 PR에 게시하는 봇 통합 능력. AI는 절대 approve 액션을 발생시키지 않는다.

### Modified Capabilities

(해당 없음 — 신규 프로젝트의 첫 변경)

## Impact

- **새 코드**: `ingester/`, `db/`, `outcomes/`, `inference/`, `rag/`, `bot/` 디렉토리(컴포넌트별 분리, 각 디렉토리는 단독 실행 가능 CLI 보유). DB 접근은 `db/` 모듈에 캡슐화되며 다른 모듈은 SQL 직접 작성 금지.
- **언어/툴체인**: Python 3.11+, 타입 힌트 필수, `ruff` + `mypy` strict, 의존성 lock(`uv` 또는 `pip-tools`).
- **외부 의존성**: GitHub API (봇 계정 PAT 또는 GitHub App 토큰), Ollama, 로컬 임베딩 모델, SQLite.
- **인프라**: 운영자 워크스테이션 1대(RTX 3090 24GB). 외부 API 미사용.
- **저장소**: 시스템 코드 / 데이터 / RAG 인덱스 / 컨벤션 spec은 별도 레포로 분리(이 변경은 시스템 코드 레포 범위만 다룬다).
- **거버넌스**: 모든 작성자 식별자는 해시로만 저장되며 salt는 운영자만 보관. 어떤 출력도 개인 단위 통계를 노출하지 않는다(MVP에서는 진단 리포트 자체가 없음).
- **킬 기준**: 도입 3개월 후 AI 코멘트 수용률 < 25%, 보완성 지표 0(사람의 AI 맹신), 또는 팀 만족도 부정 시 일시 중지·재설계.
