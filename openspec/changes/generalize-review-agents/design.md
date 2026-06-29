## Context

Sherpa MVP는 "외부 LLM API 금지(IP 보호) → 로컬 모델 전용"이라는 단일 전제 위에 서 있었다. 이 전제가 아래로 흘러내려 Ollama 백엔드(D2), self-hosted runner 강제(D3), `_assert_local` 가드, 익명화 정당화까지 묶여 있었다. 사내에서 Claude·Codex 등 CLI 에이전트가 승인되면서 이 전제가 조직 차원에서 해소되었고, "약한 로컬 모델 + RAG 보완" 구조의 존재 이유가 사라졌다.

본 변경은 프로젝트 목적을 **(1) 여러 CLI 에이전트를 선택적으로 쓰는 agentic 리뷰**와 **(2) 팀 암묵지를 자산화하는 플라이휠**로 재정의한다. 핵심 통찰: 같은 리뷰 행위가 지식의 *분배*(리뷰어 온램프)와 *수렴*(암묵지 포착)이 만나는 지점이며, Phase 1 품질이 Phase 2 플라이휠의 점화 플러그다. 어떤 결정도 코드 이전에 spec으로 합의한다.

## Goals / Non-Goals

**Goals:**

- PR hook으로 트리거되어, 샌드박스 agentic 에이전트가 repo를 직접 탐색하고 구조화된 `ReviewResult`를 낸다.
- 여러 CLI 에이전트를 단일 `ReviewAgent` 계약으로 추상화하고 config로 선택한다.
- 출력을 트리아지 라우터로 분기한다: 화이트리스트 binding approve / 인라인 변경 코멘트 / 리뷰어 요약+집중 인라인.
- approve는 **모델이 아니라 결정적 게이트(코드)**가, 에이전트 *밖*에서, fail-closed로 수행한다.
- 리뷰 결과(outcomes)에서 팀 암묵지를 distill·축적(사람 큐레이션)하고 후속 리뷰에 주입한다.
- 감사를 에이전트 trajectory 포착으로 확장한다.

**Non-Goals (본 변경 범위 외):**

- Phase 3 — 암묵지로 대상 레포 spec/convention/style-guide genesis·update 제안. 별도 변경.
- capability-aware 라우팅(에이전트 강점별 리뷰 종류 분배). 지표 후 opt-in.
- ④ 모델이 impact를 판단해 approve하는 위험-트리아지. 지표 검증 후 별도 결정.
- 범용 에이전트 오케스트레이션 플랫폼. scope는 (a) PR 리뷰 제품 유지.

## Decisions

### D1. 추론 모델 = agentic (텍스트 완성 아님)

- **결정**: 에이전트가 repo를 직접 탐색하게 한다(B안). diff를 프롬프트에 전부 조립하지 않는다.
- **근거**: Claude/Codex는 엔드포인트가 아니라 에이전트다. 스스로 컨텍스트를 수집하는 강점을 버릴 이유가 없다.
- **대안**: LCD 텍스트-in/out(`run(prompt)→text`) — 기존 파이프라인 보존엔 유리하나 에이전트의 핵심 가치를 버려 기각.

### D2. pluggable `ReviewAgent` 계약 + config 선택(A안)

- **결정**: 좁은 `ReviewAgent.review(task)→{ReviewResult, trajectory}` 계약. 어댑터는 얇게(claude/codex/ollama). 선택은 config 기본값 + per-run override. 출력은 *우리 스키마*로 coax(툴 native 포맷 비의존).
- **근거**: "필요에 따라 선택적으로"는 config/override로 충족되고 교체성이 유지된다.
- **대안**: capability-aware 두꺼운 라우팅 — 강력하나 교체성↓, 어느 에이전트가 어디서 나은지 *측정 후* 올리는 게 안전. 보류.

### D3. approve 게이트는 에이전트 "밖"에 — 모델은 approve하지 않는다

- **결정**: 에이전트는 findings + category evidence만 반환. binding approve는 Sherpa의 결정적 룰이 evidence 위에서 계산.
- **근거**: "AI는 approve하지 않는다" 원칙의 정신을 아키텍처 수준에서 보존. 또한 PR 내용발 프롬프트 인젝션의 구조적 방어선(에이전트가 jailbreak돼도 결정적 게이트는 무관).
- **대안**: 모델이 approve 판단(④) — binding과 결합 시 오판이 무인 머지로 직결되어 기각.

### D4. ③ 화이트리스트 + binding, 보수적·fail-closed·운영자 소유

- **결정**: 변경된 *모든* 파일이 운영자 소유 화이트리스트(기계적 안전 부류)에 매칭될 때만 binding approve. 혼합/모호 → 사람(fail-closed). 화이트리스트 정의는 PR 손 밖. 초기: docs/생성/포맷-only. test-only·lockfile은 안전장치 갖춰질 때까지 제외.
- **근거**: ③의 안전성은 경계가 *모델 판단*이 아니라 *하드 룰*이라는 데서 나온다. test 약화·공급망(lockfile)은 "안전해 보이는 배신자".
- **대안**: 자문(advisory) 모드 — 사용자가 binding 선택. 단 롤아웃은 단계적(Migration 참조).

### D5. 샌드박스 읽기전용 실행

- **결정**: 모든 에이전트는 파일 변경·git push·모델 API 외 네트워크 차단 상태로 실행.
- **근거**: PR을 리뷰한다 = 공격자 영향 코드 위에서 에이전트를 돌린다. 협상 불가한 보안 요구.

### D6. 트리아지 라우터 출력 + 인라인 ON

- **결정**: 출력을 단일 코멘트에서 3-way 라우팅으로. 인라인 코멘트 허용.
- **근거**: 산출물을 "결함 목록"이 아니라 "리뷰어 지도(여기를 보라)"로 만들면 over-trust를 구조적으로 누른다. 인라인을 막던 유일한 이유(앵커링 정확도)는 agentic 파일 접근으로 해소.

### D7. 암묵지는 spec과 별도, 사람 큐레이션, outcomes에서 distill

- **결정**: 팀 암묵지 저장소를 SKILL.md와 분리. `comment_outcomes`의 good-cases-only(시니어+addressed+merged)에서 후보 distill → 사람 확인 후 active → 리뷰에 주입. 추후 spec으로 진화(Phase 3).
- **근거**: RAG의 역할이 "약한 모델 보완"에서 "frontier도 모르는 팀 암묵지 주입"으로 이동. 휴리스틱은 후보 필터일 뿐 자동 신뢰 금지(D5 원본 정신 유지).

### D8. 감사 = trajectory 포착(기존 audit 확장)

- **결정**: 기존 audit 레코드(pr id, diff slice, spec hash, 주입 지식 id)에 {agent/model 버전, 읽은 파일, 실행 명령, 원본 transcript 참조} 추가.
- **근거**: agentic 비결정성을 사후 재구성 가능하게. audit은 더 중요해짐.

### D9. PR hook 트리거(event-driven), 학습 폴링은 별개 트랙

- **결정**: 리뷰는 PR open/sync/reopen hook. 학습 코퍼스 수집(ingester 폴링)은 독립 트랙 유지.
- **근거**: 리뷰는 실시간, 코퍼스 갱신은 일배치로 충분.

### D10. 익명화 유지

- **결정**: ingest 시점 `author_hash`, 암묵지 저장소도 평문 login 미저장.
- **근거**: D5(원본) 근거는 "외부 유출"이 아니라 "사내 신뢰/평가-데이터"여서 외부 API 사용과 무관하게 살아남는다.

### D11. `test_no_approve`는 교체(삭제 아님)

- **결정**: "approve 경로는 결정적 게이트로만 도달, 모델 출력 경로는 Reviews-API에 닿지 않음"으로 불변식 강화.

## Risks / Trade-offs

- **[over-trust 증폭]** frontier + auto-approve는 맹신 위험 최대치 → 지도형 출력(주의 라우팅) + 보완성 지표 유지 + kill-switch.
- **[화이트리스트 오분류 → 무인 머지]** → 게이트는 결정적(모델 아님) + fail-closed + 사후 revert율 지표로 화이트리스트 느슨함 탐지.
- **[봇 토큰이 머지 권한 보유]** binding 위해 봇을 required reviewer/CODEOWNER 등록 → 토큰 유출=임의 머지 → 토큰 보안 등급↑, 만료·회전 운영.
- **[PR 내용발 프롬프트 인젝션]** → 샌드박스 + 게이트-에이전트-밖(D3, D5).
- **[agentic 비결정성 → 재현성 저하]** → trajectory + 원본 transcript 보존(D8).
- **["Claude 래퍼"로 보일 위험]** 초기 암묵지가 비면 vanilla Claude와 구분 안 됨 → 1일차부터 암묵지 주입을 척추로(차별화가 일찍 보여야 채택됨).
- **[공급망: lockfile 화이트리스트]** → 초기 제외, patch-level+CI green 등 안전장치 갖춘 뒤 추가.

## Migration Plan

기존 MVP에서 단계적 롤아웃(binding이 목적지, 안전하게 도달):

1. agentic 리뷰 + 트리아지(인라인/요약), **approve 미동작** — `ReviewAgent` 계약·샌드박스·trajectory 감사 안착.
2. 결정적 게이트를 **shadow/advisory**로 가동 — 화이트리스트 분류·revert 기준선 측정(머지엔 영향 없음).
3. 운영 준비(봇 CODEOWNER 등록, kill-switch, 사후 모니터링) 후 **binding 전환**.

롤백: PR hook 비활성 또는 kill-switch로 approve만 차단(리뷰·코멘트는 지속). 데이터·암묵지·인덱스는 보존.

## Open Questions

- **② 암묵지 저장소 형식**: 구조화 스키마 vs DB 테이블 vs md 노트, 유사도/관련성 메커니즘(임베딩 vs 에이전트 주도 검색). spec은 형식 비의존이므로 구현 시 결정.
- **③ 실행 위치**: self-hosted runner 유지 vs 클라우드/호스티드. 외부 API OK라 풀림 — 비용·지연·토큰 노출 trade-off로 결정.
- **④ 지표 세트**: 기존 §7(cycle time, TTFR, 수용률, 보완성) + 신규(암묵지 포착률, auto-approve revert율)의 구체 쿼리·임계.
- **에이전트 transcript 추출**: claude/codex 각 세션 로그 포맷을 trajectory로 정규화하는 어댑터별 방법.
- **화이트리스트 확장 판정**: "test 약화" 같은 위험 부류를 결정적으로 탐지하는 규칙(향후 화이트리스트 확대 전제).
