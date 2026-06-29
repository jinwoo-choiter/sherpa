## Why

사내에서 Claude·Codex 등 CLI 기반 frontier 에이전트를 사용할 수 있게 되면서, Sherpa의 창립 전제였던 "외부 LLM API 금지(IP 보호) → 로컬 모델 전용"이 조직 차원에서 해소되었다. 약한 로컬 모델을 RAG로 보완하던 구조의 존재 이유가 사라졌고, 대신 (1) 여러 CLI 에이전트를 필요에 따라 선택적으로 쓰고, (2) 단순 리뷰 봇을 넘어 팀 암묵지를 자산화하는 방향으로 프로젝트 목적을 재정의한다.

재정의된 목적: **모든 PR에 "리뷰어 지도"를 먼저 띄워 누구나 복잡한 코드 리뷰를 시작할 수 있게 돕고(분배), 그 리뷰에 대한 시니어 판단을 포착해 팀 암묵지로 축적하며(수렴), 궁극적으로 대상 레포의 spec/convention 갱신을 제안하는 — 사람이 항상 승인 게이트를 쥔, 선택 가능한 CLI 에이전트 기반 지식 시스템.**

## What Changes

- **BREAKING** "Local-only inference" 하드 제약 제거. 추론은 사내 승인된 CLI 에이전트(Claude/Codex 등)로 위임하며, 안전망은 "로컬 실행"이 아니라 **사람 승인 게이트 + trajectory 감사**로 교체된다.
- **BREAKING** "never-approve" 불변식을 정제한다. **모델은 여전히 approve하지 않는다.** 대신 **결정적 화이트리스트 게이트(코드)**가, 기계적으로 안전한 부류(초기: docs/생성/포맷-only)에 한해 **binding approve**를 수행할 수 있다. 게이트는 에이전트 출력 *밖*에 있고 fail-closed이며, 화이트리스트 정의는 PR 손이 닿지 않는 운영자 소유다.
- 추론을 **agentic**으로 전환: 프롬프트에 diff를 전부 조립하는 대신, 샌드박스(읽기전용) 에이전트가 repo를 직접 탐색한다. RAG의 역할은 "약한 모델 보완"에서 **"팀 암묵지 주입"**으로 이동한다.
- 여러 CLI 에이전트를 **단일 ReviewAgent 계약**으로 추상화하고, **config 기본값 + per-run override**로 선택한다(필요에 따라 선택적 사용).
- 출력을 단일 통합 코멘트에서 **트리아지 라우터**로 확장: PR 영향도에 따라 ① 화이트리스트 binding approve ② 변경점 **인라인 코멘트** ③ 사람 판단 필요 시 리뷰어용 요약 + "여기 집중" 인라인. (인라인 코멘트 ON — 원래 막던 앵커링 문제가 agentic 파일 접근으로 해소됨)
- **Phase 2(암묵지 포착)**를 1일차 척추로 도입: 리뷰에 대한 사람 반응을 신호로 팀 암묵지를 distill·축적하고, 다음 리뷰에 주입한다.
- 트리거를 일배치 폴링에서 **PR hook(event-driven)**으로 전환(학습 코퍼스 수집 폴링은 별도 트랙으로 유지).
- 감사(audit)를 **에이전트 trajectory 포착**으로 확장: 무엇을 읽고 실행했는지 + 원본 세션 transcript 참조를 기존 audit 레코드에 추가한다.

**Out of scope (이번 변경 아님, 향후 단계):**
- Phase 3 — 포착된 암묵지로 대상 레포의 spec/convention/style-guide 발생(genesis)·갱신(update) 제안(OpenSpec change 형태). 별도 변경으로 분리.
- capability-aware 라우팅(에이전트 강점별로 리뷰 종류를 분배)은 지표가 쌓인 뒤 opt-in.
- ④ 위험-트리아지 approve(모델이 impact를 판단해 approve)로의 승격은 지표 검증 후 별도 결정.

## Capabilities

### New Capabilities
- `knowledge-capture`: 리뷰 결과(comment outcomes)에서 시니어 판단을 distill해 팀 암묵지 저장소에 축적하고, 후속 리뷰의 컨텍스트로 주입한다(Phase 2). spec과 별도로 관리하되, 추후 spec으로 진화하는 자산.

### Modified Capabilities
- `review-inference`: local-only 제거; 추론을 pluggable·sandbox(읽기전용)·config 선택 가능한 agentic CLI 에이전트로 위임; 출력은 구조화된 ReviewResult 스키마; 감사는 trajectory 포착으로 확장; RAG는 암묵지 주입으로 역할 이동.
- `pre-flight-bot`: 트리아지 라우팅(approve-eligible / 인라인 변경 코멘트 / 리뷰어 요약) 도입; 인라인 코멘트 허용; 결정적 화이트리스트 **binding approve 게이트**(fail-closed, 에이전트 밖, 운영자 소유 화이트리스트) 추가; never-approve를 "모델은 approve하지 않고 결정적 게이트만 approve한다"로 정제.

## Impact

- **코드 재사용**: `db`·`anon`·`ingester`·`outcomes`(승격)·`rag`(역할 이동)·`bot`. 변경 핵심: `inference`(→ 에이전트 러너 + 어댑터), 신규 `knowledge`(암묵지 저장소).
- **테스트**: `tests/test_no_approve.py`는 삭제가 아니라 **더 빡센 불변식으로 교체** — "approve 경로는 결정적 게이트로만 도달, 모델 출력 경로는 Reviews-API에 닿지 않음".
- **외부 의존성**: Claude/Codex CLI 바이너리 + 사내 에이전트 인증. Ollama는 레거시 어댑터로 유지 가능.
- **운영(BREAKING)**: binding approve를 위해 봇을 required reviewer/CODEOWNER로 등록 → 봇 토큰이 머지 권한을 보유(토큰 보안 등급 ↑). PR hook 수신을 위한 트리거 인프라. 무인 머지 대비 kill-switch + 사후 revert 모니터링.
- **보안**: PR 내용은 신뢰 불가(프롬프트 인젝션) → 에이전트 샌드박스 + 게이트-에이전트-밖 설계로 방어.
