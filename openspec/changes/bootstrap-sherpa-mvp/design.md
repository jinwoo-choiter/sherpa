## Context

Sherpa는 팀 코드 리뷰의 표면적 검토를 자동화해 시니어 인지 자원을 깊은 판단에 재배치하기 위한 로컬 LLM 기반 시스템이다. 외부 API는 IP 보호 차원에서 사용하지 않으며, 운영 환경은 RTX 3090 24GB × 1 워크스테이션으로 고정되어 있다. 본 변경은 5일짜리 MVP를 정의·구축하며, 시스템의 정체성과 한계를 코드 이전에 합의된 spec(§2 핵심 원칙)으로 박아 둔다.

핵심 원칙(spec §2):

- AI는 **pre-flight**일 뿐이다. approve를 절대 발생시키지 않으며 머지 결정은 사람이 한다.
- 모든 작성자 식별자는 익명 해시로만 저장된다(salt는 운영자 1인 보관).
- 학습 코퍼스는 "좋은 케이스만" — 자동 휴리스틱 + 주간 시니어 검수의 2단계 필터를 거친 것만 RAG에 반영된다(주간 검수는 MVP 이후, MVP에서는 휴리스틱 단독).

## Goals / Non-Goals

**Goals:**

- 팀 단일 레포의 신규 PR이 열리면 GitHub Action이 자동 트리거되어 단일 통합 `[pre-flight]` 코멘트가 게시된다.
- 과거 6개월 시니어 코멘트 중 휴리스틱 통과분을 RAG 시드 인덱스로 사용한다.
- 코멘트 인과 추적(`comment_outcomes.resolution_type`)이 자동으로 채워져 추후 학습 후보 선별에 사용 가능한 상태가 된다.
- 모든 컴포넌트가 단독 CLI로 실행 가능해 운영자가 디버깅·수동 개입할 수 있다.

**Non-Goals (MVP 범위 외):**

- 에이전트 통합(opencode 등)
- 진단 리포트(팀 단위 집계)
- 주간 컨텍스트 PR 자동 생성과 시니어 라벨링 워크플로
- Webhook 기반 실시간 처리
- 카테고리(`nit`/`logic`/`design`/...) 자동 분류
- 인라인(라인별) 코멘트
- UI(웹/데스크톱). MVP의 UI는 CLI + GitHub 코멘트뿐.

## Decisions

### D1. RAG와 Spec의 역할 분담 (§3.2 재확인)

- **결정**: 표현 형식·톤·금지 표현·도메인 체크리스트는 **spec(SKILL.md/OpenSpec)**, "무엇을 의심해야 하는가"의 사례 감각은 **RAG**.
- **근거**: 톤을 RAG로 학습시키면 noisy하고 일관성 떨어짐. 반대로 의심의 감각을 spec으로 압축하려 하면 사례성을 잃음.
- **대안**: 단일 RAG로 전부 흡수 → 톤 흔들림. 단일 spec으로 전부 인코딩 → 도메인 사례 폭발. 둘 다 기각.

### D2. 추론 백엔드 선택: Ollama (vLLM 아님)

- **결정**: MVP는 **Ollama**. 모델 후보는 코드 특화 30B급 4-bit 양자화(Qwen2.5-Coder-32B 4-bit 등)로 시작해 실측 평가.
- **근거**: 셋업 단순성·1주 일정 적합성. vLLM은 처리량 이점이 있으나 단일 사용자 일배치 트리거 워크로드에서는 운영 복잡성을 정당화하지 못함.
- **대안**: vLLM, llama.cpp 직접 — MVP 종료 후 처리량/지연 측정 결과에 따라 재평가.

### D3. 트리거: GitHub Action + self-hosted runner

- **결정**: 신규 PR 이벤트만 트리거. 추론은 운영자 워크스테이션에 등록된 self-hosted runner에서 실행.
- **근거**: 외부 hosted runner를 쓰면 PR diff·프롬프트가 GitHub 외부 CI로 전달돼 IP 보호 원칙 위반. self-hosted runner는 GitHub→로컬 머신 단방향 폴링이라 방화벽 노출 없이 동작.
- **대안**: webhook 직접 수신(라우팅·인증·재시도 직접 구현 필요, MVP에 과함). polling 트리거(지연 길고 Action 자원 낭비). 둘 다 기각.

### D4. SQLite 단일 파일

- **결정**: 5개 테이블을 단일 SQLite 파일에 둔다. 미사용 컬럼(예: `review_comments.category`)은 NULL 허용으로 미리 만들어 둔다.
- **근거**: 단일 사용자, 일배치 부하, 백업 단순성. Postgres 도입은 MVP에서 운영 복잡도만 늘림.
- **트리거**: 동시성 충돌 또는 GB 단위 성장 시 재평가.

### D5. 작성자 익명화는 ingest 시점에 수행

- **결정**: GitHub login은 어떤 테이블에도 평문으로 저장하지 않는다. ingester가 `hash(salt + login)`을 계산해 `author_hash`로만 기록.
- **근거**: spec §2.2 — "한 번 평가 자료처럼 보이는 데이터가 만들어지면 신뢰는 회복 불가능." 평문이 한 컬럼이라도 남으면 SELECT 한 번에 무력화됨.
- **운영**: salt는 워크스테이션의 운영자-only readable 파일. 코드 레포에는 절대 commit 금지(.gitignore + 시작 시 부재 검증).

### D6. 통합 코멘트 1건만 (인라인 X)

- **결정**: PR당 `[pre-flight]` prefix가 붙은 단일 issue-level comment 1건. 인라인은 MVP 이후 §9 우선순위 1번.
- **근거**: 인라인은 anchoring(파일 경로·라인 번호) 정확도 요구가 높아 모델·diff 파싱 안정화 후 도입해야 함. MVP에서 인라인을 시도하면 잘못된 라인에 코멘트가 달려 신뢰 손상.

### D7. resolution_type 휴리스틱은 학습 필터에만 사용

- **결정**: 100% 정확하지 않아도 무방. 다음 4종으로 분류:
  - `addressed`: 후속 커밋이 코멘트 라인을 수정 (git blame 비교)
  - `discussed`: 후속 코멘트 5+ AND 코드 변경 있음
  - `dismissed`: 후속 코멘트에 반박 패턴 AND 코드 변경 없음 AND 머지됨
  - `ignored`: 후속 활동 없음 AND 머지됨
- **근거**: 이 라벨은 "RAG 시드 후보 선별"이라는 단일 목적에만 쓰임. 머지 차단·평가에 쓰이지 않으므로 정확도 목표를 낮게 잡아도 시스템 가치가 줄지 않음.

### D8. 리포지토리 분리

- **결정**: 시스템 코드 / 데이터(SQLite) / RAG 인덱스 / 컨벤션 spec(SKILL.md)을 별도 레포로 분리. 본 변경은 시스템 코드 레포에만 적용.
- **근거**: 코드와 데이터의 lifecycle이 다르고, 스펙·인덱스는 시니어가 PR로 손대는 자산이라 권한 경계가 다름. 단일 레포에 합치면 권한·CI·릴리스가 엉킴.

### D9. 컴포넌트 구조와 CLI 의무

- **결정**: 디렉토리는 `ingester/`, `db/`, `outcomes/`, `inference/`, `rag/`, `bot/`. 각 컴포넌트는 단독 CLI 진입점을 제공한다. DB 접근은 `db/` 모듈에 캡슐화하고 다른 모듈은 SQL 직접 작성 금지.
- **근거**: 운영자가 새벽에 디버깅할 수 있어야 함. 결합도 낮으면 한 컴포넌트 장애가 전체를 멈추지 않음.

### D10. 일배치 폴링 (webhook 아님)

- **결정**: 데이터 수집은 cron 일배치(예: 매일 02:00 KST). 추론 트리거(D3)와는 별개 경로.
- **근거**: 학습 코퍼스 갱신은 실시간일 필요가 없음. webhook 운영 부담을 MVP가 감당할 이유 없음.

## Risks / Trade-offs

- **[로컬 모델 품질이 기대 미달]** → 1주차 Day 3에 모델 후보 3개를 동일 PR 셋에 돌려 정성·정량 평가. 미달 시 D1의 spec 비중을 늘려 컨벤션 점검 위주로 좁힘. 그래도 §7.2 kill criteria(수용률 25% 미만, 3개월) 위반 시 일시 중지.
- **[자동화 편향: 사람이 AI 출력을 맹신]** → spec §7 보완성 지표("AI가 통과시킨 PR에서 사람이 단 substantive 코멘트") 0이 되면 즉시 중지. 이름·prefix·"approve 금지"가 1차 방어선이지만 충분치 않을 수 있음.
- **[salt 유출]** → 운영자 머신만 권한 보유, 시작 시 부재 검증, 코드 레포 .gitignore. 유출 시 salt 회전 후 전 데이터 재해시 절차가 필요(MVP에는 자동화하지 않고 운영자 수기 절차로 둠).
- **[git blame 휴리스틱 오판]** → "필터일 뿐 정답이 아님"(D7). 주간 시니어 검수가 도입되는 MVP 이후 단계에서 false positive가 자연 정리됨.
- **[GitHub Action self-hosted runner 가용성]** → runner가 다운되면 자동 게시 실패. `bot/` 컴포넌트의 단독 CLI(D9)가 fallback. spec `pre-flight-bot`에 명시.
- **[코멘트 중복 게시]** → Action 재시도 시 같은 PR에 `[pre-flight]` 코멘트가 누적될 위험. 봇은 기존 `[pre-flight]` 코멘트를 author=bot 기준으로 조회 후 update 또는 skip(spec 요구사항).
- **[scope creep으로 1주 일정 깨짐]** → §8.1의 "빼는 것" 목록을 design.md Goals/Non-Goals에 그대로 옮겨 박아둠. 변경 요청 시 본 design 갱신 PR 필수(임의 추가 금지).

## Migration Plan

신규 시스템이라 마이그레이션 없음. 단, 운영 시작 절차:

1. 봇 GitHub 계정(`@sherpa-bot` 또는 동등) 생성, PAT/GitHub App 발급, 시스템 코드 레포에 토큰 secret 등록.
2. 운영자 워크스테이션에 self-hosted runner 등록(GitHub Action용).
3. salt 파일을 운영자 home에 0400 권한으로 생성(코드 레포 .gitignore 사전 확인).
4. SQLite 초기화 후 과거 6개월 PR 백필 1회 실행.
5. 휴리스틱으로 `comment_outcomes` 채움 → 시드 RAG 인덱스 빌드.
6. 단일 테스트 PR을 열어 end-to-end 코멘트 게시 확인.

롤백: GitHub Action workflow 비활성화로 즉시 일시 중지. 데이터·인덱스는 보존(재개 시 복구 비용 절감).

## Open Questions

- **모델 후보**: Qwen2.5-Coder-32B 4-bit가 RTX 3090 24GB에서 우리 평균 PR diff 크기로 응답을 충분히 빠르게 내는가? Day 3 실측 후 결정.
- **유사도 검색 임베딩 모델**: 코드 임베딩 전용 모델(예: code-retrieval 계열) vs 일반 다국어 임베딩. 시드 인덱스 품질에 직접 영향. Day 4에 2~3개 비교.
- **봇 코멘트 update vs new**: 같은 PR에 force-push가 들어와 새 추론을 돌렸을 때 기존 `[pre-flight]` 코멘트를 update하는 게 좋은가, 새 코멘트를 다는 게 좋은가? UX 관점은 update, 감사 관점은 new. MVP는 update로 시작하되 변경 이력은 GitHub API의 edit history에 남는 것으로 충분하다고 가정.
- **봇 코멘트의 길이 상한**: 컨텍스트 늘어났을 때 코멘트가 너무 길면 PR이 시끄러워짐. 절단 정책(상위 N개 항목만, 또는 길이 임계) 미정.
