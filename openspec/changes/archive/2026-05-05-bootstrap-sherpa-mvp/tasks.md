## 1. Day 0 — 운영 사전 준비 (코드 작업 전 1회성, 운영자 수기)

- [ ] 1.1 봇 GitHub 계정(`@sherpa-bot` 또는 팀 네임스페이스) 생성 및 PAT/GitHub App 토큰 발급
- [ ] 1.2 운영자 워크스테이션에 self-hosted GitHub Action runner 등록 (라벨: `sherpa-local`)
- [ ] 1.3 시스템 코드 / 데이터 / RAG 인덱스 / 컨벤션 spec 4개 저장소 분리 생성
- [ ] 1.4 운영자 home에 salt 파일 생성(권한 0400), 코드 레포 `.gitignore`에 salt 경로 사전 등록 _(코드 레포 `.gitignore` 부분은 완료; 나머지는 운영자 수기)_
- [ ] 1.5 Python 3.11+, `uv`(또는 `pip-tools`), `ruff`, `mypy` 툴체인 워크스테이션에 설치

## 2. Day 1 — DB 스키마 + GitHub 폴링 ingester

- [x] 2.1 `db/` 모듈에 SQLite 마이그레이션 작성 (5개 테이블: `pull_requests`, `review_comments`, `code_diffs`, `comment_outcomes`, `learning_labels`), 미사용 컬럼은 NULL 허용으로 미리 생성
- [x] 2.2 `db/` 모듈에 CRUD 헬퍼 작성 (다른 모듈은 SQL 직접 작성 금지를 코드 리뷰 룰로 합의)
- [x] 2.3 `ingester/` 모듈에 GitHub REST/GraphQL 클라이언트 wrapper 작성 (인증, rate-limit retry)
- [x] 2.4 `author_hash = hash(salt + github_login)` 유틸 작성, salt 부재 시 fail-fast
- [x] 2.5 PR 폴링 로직 작성 (watermark 기반, 부분 실패 시 watermark 미진행)
- [x] 2.6 review_comments / code_diffs 동반 적재 로직 작성
- [x] 2.7 `ingester/` 단독 CLI 진입점 (`python -m sherpa.ingester poll <repo>`) 작성
- [ ] 2.8 팀 repo 1개의 과거 6개월치를 백필 1회 실행해 DB에 적재 — **DoD: 행 수 sanity check 통과 + author_hash만 저장됨 확인** _(라이브 인프라 필요; 운영자 수기)_

## 3. Day 2 — comment_outcomes 휴리스틱

- [x] 3.1 `outcomes/` 모듈에 코멘트 라인 변경 판정 로직 작성 _(저장된 PR 파일 diff와 코멘트 라인 범위 overlap으로 구현; design D7 "필터일 뿐 정답이 아님" 가정)_
- [x] 3.2 4종 `resolution_type` 분류기 구현 (`addressed` / `discussed` / `dismissed` / `ignored`) — design D7 휴리스틱 그대로
- [x] 3.3 `dismissed` 판정용 반박 패턴 키워드 셋 정의 (작은 수동 셋으로 시작; 정확도 100% 불필요)
- [x] 3.4 `comment_outcomes.resulted_in_change`, `linked_diff_id` 채우기 로직 작성
- [x] 3.5 `outcomes/` 단독 CLI (`python -m sherpa.outcomes recompute --pr <id>`) 작성
- [ ] 3.6 백필 데이터에 outcomes 일괄 계산 1회 실행 — **DoD: senior 작성 + addressed 코멘트 셋이 비어있지 않음** _(2.8 선행 필요; 운영자 수기)_

## 4. Day 3 — 로컬 LLM 셋업 + 모델 후보 평가

- [ ] 4.1 워크스테이션에 Ollama 설치, 모델 후보 3종 다운로드 (Qwen2.5-Coder-32B 4-bit를 1순위로 포함) _(하드웨어 필요)_
- [x] 4.2 `inference/llm.py`에 Ollama 클라이언트 wrapper 작성 (외부 엔드포인트 호출 금지 강제) _(import-level은 환경 변수 의존이라 불가; 인스턴스 생성 + 매 호출마다 host loopback/RFC1918 검증)_
- [ ] 4.3 평가용 프롬프트 + 동일 PR 셋(과거 closed PR 5~10건) 준비 _(라이브 데이터 필요)_
- [ ] 4.4 모델 3종을 동일 입력에 돌려 응답 시간/품질 정성 평가, 결과를 `design.md` Open Questions에 답으로 남기는 짧은 메모 작성 _(하드웨어 필요)_
- [ ] 4.5 1순위 모델 1개 확정 — **DoD: 단일 PR 입력에 대해 워크스테이션에서 끝까지 응답이 나옴** _(하드웨어 필요)_

## 5. Day 4 — RAG 파이프라인 + 프롬프트 조립

- [ ] 5.1 임베딩 모델 후보 2~3개 비교 후 1개 선택 (코드 임베딩 우선) _(하드웨어 필요; 기본값으로 `nomic-embed-text` 지정. `config.py` `embedding_model`에 TODO 주석)_
- [x] 5.2 `rag/indexer.py` 작성: senior 작성 + addressed 코멘트를 본문+컨텍스트(diff)로 임베딩해 로컬 vector store에 적재
- [ ] 5.3 시드 인덱스 1회 빌드 (과거 6개월, 휴리스틱 자동 통과분만; 주간 검수는 MVP 외) _(2.8/3.6 선행 필요; 운영자 수기)_
- [x] 5.4 `rag/retriever.py` 작성: 입력 PR diff에 대해 top-N 유사 exemplar 반환
- [x] 5.5 `inference/prompt.py` 작성: spec(SKILL.md) + RAG exemplar + 현재 PR diff를 합쳐 단일 프롬프트로 조립
- [x] 5.6 출력 후처리 작성: 본문 prefix 강제(`[pre-flight]`), approve-style 표현 strip/reject
- [x] 5.7 감사 로그(input set: PR id, diff slice, spec 버전 hash, exemplar id 목록) 로컬 파일 출력 추가
- [x] 5.8 `inference/` 단독 CLI (`python -m sherpa.inference run --pr <id>`) 작성, 게시는 하지 않고 stdout 출력
- [ ] 5.9 과거 PR 1건에 dry-run — **DoD: 단일 통합 코멘트 본문이 stdout으로 출력되며 prefix·exemplar id가 감사 로그에 남음** _(라이브 인프라 필요; 운영자 수기)_

## 6. Day 5 — bot/ 컴포넌트 + GitHub Action 연결

- [x] 6.1 `bot/poster.py` 작성: PR id + body 입력 → issue-level comment 게시. 기존 `[pre-flight]` 코멘트가 있으면 update, 없으면 create
- [x] 6.2 봇 게시 경로에서 GitHub Reviews API 호출이 발생하지 않음을 단위 테스트로 lock-in _(소스 grep + httpx transport double, `tests/test_no_approve.py`)_
- [x] 6.3 시작 시 토큰의 viewer가 봇 계정인지 검증, 사람 계정이면 fail-fast _(`assert_bot_identity` + `SHERPA_BOTS_PATH` allowlist)_
- [x] 6.4 `bot/` 단독 CLI (`python -m sherpa.bot post --pr <owner/repo#n> --body-file <path>`) 작성 — runner 다운 시 fallback 경로
- [x] 6.5 GitHub Action workflow 작성 (`.github/workflows/sherpa-preflight.yml`): `pull_request: [opened, synchronize, reopened]` 트리거, `runs-on: [self-hosted, sherpa-local]`, hosted runner로 실행되면 fail-fast
- [x] 6.6 workflow에서 `inference/` CLI → `bot/` CLI를 순차 호출하도록 연결
- [ ] 6.7 테스트 PR 1건을 새로 열어 end-to-end 검증 — **DoD: PR에 봇 계정의 `[pre-flight]` 단일 통합 코멘트 1건이 자동 게시됨** _(라이브 인프라 필요; 운영자 수기)_

## 7. Day 5 종료 — 운영 점검 및 핸드오프

- [x] 7.1 §7.1 지표 4종(PR cycle time, TTFR, AI 코멘트 수용률, 보완성)을 SQL 쿼리 1개씩으로 작성해 운영자 README에 박아둠 (자동 리포트는 MVP 외)
- [x] 7.2 §7.2 kill criteria 임계치를 운영자가 분기마다 점검할 수 있도록 위 쿼리에 주석으로 표시
- [ ] 7.3 cron 등록: 일배치 폴링(매일 02:00 KST), outcomes 재계산(폴링 직후) _(README에 예시 라인 제공; 등록은 운영자 수기)_
- [x] 7.4 운영 체크리스트(salt 권한, 봇 토큰 만료일, runner 등록 상태) 1쪽 분량 작성 _(README "Operator checklist" 섹션)_
- [ ] 7.5 본 변경을 archive 가능한 상태로 정리하고 `/opsx:archive` 안내 _(운영자 수기 검수 후 실행)_
