## 1. 에이전트 추상화 (`ReviewAgent` 계약)

- [x] 1.1 `ReviewResult` 스키마 정의 (요약/인라인 findings{file,line,severity,body}/category evidence/open questions) — 직렬화·검증 가능
- [x] 1.2 `ReviewTask` 정의 (repo checkout·PR 메타·주입 지식·form_spec·출력 스키마)
- [x] 1.3 `ReviewAgent` 계약 + `AgentAdapter` 인터페이스(build_invocation→run→parse→extract_trajectory) 작성
- [x] 1.4 Claude 어댑터 작성 (비대화형 실행, 우리 스키마로 출력 coax + 파싱) _(live CLI 미검증; argv/파싱 단위테스트)_
- [x] 1.5 Codex 어댑터 작성 (동일 계약) _(live CLI 미검증)_
- [x] 1.6 레거시 Ollama 어댑터 — 기존 `inference/llm.py` `_assert_local` 가드 보존한 채 계약에 맞춤
- [x] 1.7 config 기본 에이전트(`SHERPA_REVIEW_AGENT`) + per-run override 선택 로직(`agent.resolve`) — **DoD: 미지정 시 기본, 지정 시 해당 에이전트** _(CLI `--agent` 플래그는 4.6)_

## 2. 샌드박스 실행 + trajectory 감사

- [x] 2.1 샌드박스 읽기전용 실행(파일 변경·git push·모델 API 외 네트워크 차단) 어댑터 공통 적용 (`agent/sandbox.py` 정책 + 어댑터 플래그)
- [ ] 2.2 차단된 mutating 시도를 trajectory에 기록 _(미완: Trajectory.blocked_attempts 필드·audit 직렬화는 존재, 어댑터 추출은 live stream 포맷 필요)_
- [x] 2.3 기존 `inference/audit.write()`를 trajectory로 확장 ({agent/model 버전, 읽은 파일, 실행 명령, 원본 transcript 참조} 추가)
- [ ] 2.4 어댑터별 세션 transcript → 정규화 trajectory 추출 (claude/codex 포맷) _(미완: claude는 model/session 기본 추출, files_read·commands_run 풍부 추출은 stream-json 검증 필요)_

## 3. 암묵지 포착 (`knowledge/`)

- [x] 3.1 암묵지 저장소 모듈(`knowledge/store.py` + `knowledge_entries` 테이블) — spec과 분리, 평문 login 미저장(provenance는 comment id)
- [x] 3.2 `comment_outcomes` good-cases-only(시니어+addressed+merged)에서 후보 distill 로직 — `db.fetch_addressed_senior_comments` 재사용, 멱등
- [x] 3.3 사람 큐레이션 게이트: 후보→active 확정/거부, active만 주입 대상, 거부는 재제안 안 됨
- [x] 3.4 현재 PR diff에 관련한 active 엔트리 주입(`knowledge/inject.py`) — **DoD 충족: 빈 저장소→[] (spec layer만)**. 유사도는 MVP 토큰오버랩(임베딩은 향후)
- [ ] 3.5 주입된 엔트리 id를 run audit에 기록 _(audit는 `knowledge_ids` 지원함; 실제 wiring은 4.1 runner)_
- [x] 3.6 `knowledge/` 단독 CLI (distill / confirm / reject / list)

## 4. 트리아지 라우터 + 게시 (approve 미동작 — Stage 1)

- [ ] 4.1 `inference/runner` 재작성: ReviewAgent 호출 → `ReviewResult` 반환 (프롬프트 조립 제거)
- [ ] 4.2 트리아지 라우터: ReviewResult → {approve-eligible(보류) / 변경 인라인 / 리뷰어 요약+집중} 분기
- [ ] 4.3 `bot/poster` 확장: 인라인 코멘트 게시 (file/line 앵커) + `[pre-flight]` 마커, 멱등(update/skip)
- [ ] 4.4 리뷰어 요약 + 집중 인라인 게시 경로
- [ ] 4.5 approve-style 표현 strip/reject 유지 (모델 출력은 절대 approve로 해석 안 함)
- [ ] 4.6 `inference/` 단독 CLI: PR id 입력 → `ReviewResult` stdout, 미게시 — **DoD: 과거 PR 1건 dry-run이 구조화 결과 출력**

## 5. 결정적 화이트리스트 게이트 (Stage 2 — shadow/advisory)

- [ ] 5.1 운영자 소유 화이트리스트 정의(PR 손 밖) 로드 — 초기: docs/생성/포맷-only
- [ ] 5.2 결정적 게이트: 변경된 *모든* 파일 매칭 검사, 하나라도 불일치/모호 → fail-closed
- [ ] 5.3 게이트 입력은 category evidence + 파일 목록(코드), 모델 출력 아님 — 인젝션 무관함 단위 테스트
- [ ] 5.4 화이트리스트 자체 수정 PR은 self-approve 불가 처리
- [ ] 5.5 shadow 모드: 게이트 판정을 기록만(머지 영향 0), revert 기준선 측정용 로그

## 6. binding approve + 안전 통제 (Stage 3)

- [ ] 6.1 게이트 승인 시 봇이 approving review 제출하는 경로 (게이트 통과 시에만 도달)
- [ ] 6.2 `tests/test_no_approve.py` 교체: "approve는 게이트로만 도달, 모델 경로는 Reviews-API 미접촉" 불변식 lock-in
- [ ] 6.3 운영자 kill-switch: approve만 비활성(리뷰·코멘트 지속)
- [ ] 6.4 auto-approve PR 추적 + 사후 revert/hot-fix 지표 기록
- [ ] 6.5 봇을 required reviewer/CODEOWNER로 등록 — **운영자 수기(라이브 인프라)**

## 7. 트리거 + 지표

- [ ] 7.1 PR hook(open/sync/reopen) 트리거 → 리뷰 실행 연결, 비-PR 이벤트 무시
- [ ] 7.2 학습 코퍼스 폴링(ingester)은 별개 트랙으로 유지 확인
- [ ] 7.3 신규 지표 쿼리: 암묵지 포착률, auto-approve revert율 (기존 §7에 추가)
- [ ] 7.4 over-trust 방어로 보완성 지표 유지·문서화

## 8. 마무리

- [ ] 8.1 README 운영 플레이북 갱신 (에이전트 선택, 화이트리스트 운영, kill-switch, 단계적 롤아웃)
- [ ] 8.2 `openspec validate --strict` 통과 + 단계적 롤아웃 Stage 1→2→3 절차 점검
- [ ] 8.3 테스트 PR로 end-to-end 검증 (Stage 1 코멘트, Stage 2 shadow 판정) — **운영자 수기(라이브 인프라)**
