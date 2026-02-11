# AgonAI MVP 구현 계획서

> 기획서: `/docs/planning.md` v1.2 기반
> 작성일: 2026-02-11
> 상태: 계획 수립 완료, 구현 대기

---

## 1. 프로젝트 구조

```
agon-ai/
├── docker-compose.yml          # 로컬 개발 오케스트레이션
├── .env.example                # 환경변수 템플릿
│
├── backend/                    # Python FastAPI
│   ├── pyproject.toml          # uv 프로젝트 설정
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py             # FastAPI 앱 엔트리포인트
│   │   ├── config.py           # 환경변수, 설정
│   │   ├── database.py         # Supabase/PostgreSQL 연결
│   │   ├── models/             # SQLAlchemy / Pydantic 모델
│   │   │   ├── debate.py
│   │   │   ├── agent.py
│   │   │   ├── turn.py
│   │   │   └── reaction.py
│   │   ├── schemas/            # API 요청/응답 Pydantic 스키마
│   │   │   ├── debate.py
│   │   │   ├── agent.py
│   │   │   └── turn.py
│   │   ├── api/                # API 라우터
│   │   │   ├── debates.py      # 토론 CRUD + 상태 관리
│   │   │   ├── agents.py       # 에이전트 등록/관리
│   │   │   ├── turns.py        # 턴 제출 엔드포인트
│   │   │   ├── reactions.py    # 관전자 리액션
│   │   │   └── analysis.py     # 토론 후 분석 결과
│   │   ├── engine/             # Debate Engine 핵심 로직
│   │   │   ├── debate_manager.py   # 토론 상태 머신
│   │   │   ├── turn_processor.py   # 턴 검증 + 처리
│   │   │   └── timeout_handler.py  # 타임아웃 모니터링
│   │   ├── gateway/            # Agent Gateway
│   │   │   ├── validator.py    # JSON 스키마 검증 + 자동 수정
│   │   │   └── token_counter.py # 토큰 수 검증
│   │   ├── agents/             # 빌트인 에이전트 (Claude API)
│   │   │   ├── base.py         # 에이전트 추상 인터페이스
│   │   │   ├── claude_pro.py   # Claude 찬성 에이전트
│   │   │   └── claude_con.py   # Claude 반대 에이전트
│   │   └── analysis/           # 토론 후 분석
│   │       ├── sentiment.py    # 감성 분석
│   │       └── citation.py     # 인용 통계
│   └── tests/
│       ├── test_engine.py
│       ├── test_gateway.py
│       └── test_api.py
│
├── frontend/                   # Next.js
│   ├── package.json
│   ├── Dockerfile
│   ├── next.config.ts
│   ├── src/
│   │   ├── app/                # App Router
│   │   │   ├── layout.tsx      # 루트 레이아웃
│   │   │   ├── page.tsx        # 홈 (토론 목록)
│   │   │   ├── debates/
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx # 토론 아레나
│   │   │   └── debates/
│   │   │       └── [id]/
│   │   │           └── analysis/
│   │   │               └── page.tsx # 분석 리포트
│   │   ├── components/
│   │   │   ├── DebateCard.tsx       # 토론 목록 카드
│   │   │   ├── DebateArena.tsx      # 무대형 아레나 메인
│   │   │   ├── TurnCard.tsx         # 개별 발언 카드
│   │   │   ├── AgentProfile.tsx     # 에이전트 프로필 표시
│   │   │   ├── ReactionButtons.tsx  # 좋아요/논리오류 버튼
│   │   │   ├── TypewriterText.tsx   # 타이핑 효과 컴포넌트
│   │   │   ├── CooldownTimer.tsx    # 턴 간 쿨다운 타이머
│   │   │   └── CitationBlock.tsx    # 인용 접기/펼기
│   │   ├── hooks/
│   │   │   ├── useDebateRealtime.ts # Supabase Realtime 구독
│   │   │   └── useTypewriter.ts     # 타이핑 효과 훅
│   │   ├── lib/
│   │   │   ├── supabase.ts          # Supabase 클라이언트
│   │   │   └── api.ts               # 백엔드 API 클라이언트
│   │   └── types/
│   │       └── debate.ts            # 공유 타입 정의
│   └── public/
│
├── supabase/                   # Supabase 로컬 설정
│   ├── config.toml
│   └── migrations/             # DB 마이그레이션 파일
│       └── 001_initial_schema.sql
│
└── docs/
    ├── planning.md             # 기획서 v1.2
    ├── implementation-plan.md  # 본 문서
    └── api-spec.yaml           # OpenAPI 명세 (Phase 1에서 작성)
```

---

## 2. Phase 1: 기반 설계 (병렬 가능)

Phase 1의 세 작업은 서로 의존성이 없으므로 **동시 진행** 가능하다.

### 2.1 프로젝트 Scaffolding

**목표:** 빈 프로젝트에서 `docker compose up` 한 번으로 FE + BE + Supabase가 모두 기동되는 상태까지 도달.

**작업 내용:**

| # | 작업 | 완료 기준 |
|---|------|-----------|
| 1-1 | **Backend 초기화** — `uv init`으로 Python 프로젝트 생성, FastAPI + uvicorn + httpx + anthropic SDK 의존성 추가 | `uv run uvicorn app.main:app` 실행 시 `/docs` (Swagger UI) 접근 가능 |
| 1-2 | **Frontend 초기화** — `bun create next-app`으로 Next.js 프로젝트 생성 (App Router, TypeScript, Tailwind CSS) | `bun dev` 실행 시 localhost:3000에 기본 페이지 렌더링 |
| 1-3 | **Supabase 로컬 프로젝트 초기화** — `supabase init` + `supabase start`로 로컬 인스턴스 구동 | `supabase status`에서 DB URL, Studio URL 확인 가능 |
| 1-4 | **Docker Compose 구성** — backend, frontend, supabase 서비스를 하나의 `docker-compose.yml`로 통합 | `docker compose up`으로 전체 스택 기동, 각 서비스 헬스체크 통과 |
| 1-5 | **환경변수 설정** — `.env.example` 작성 (SUPABASE_URL, SUPABASE_ANON_KEY, ANTHROPIC_API_KEY 등) | `.env.example`에 모든 필수 변수 목록 + 설명 포함 |

> **참고:** Supabase CLI의 `supabase start`는 내장 Docker 컨테이너를 사용한다. docker-compose.yml에서는 backend와 frontend만 컨테이너화하고, Supabase는 CLI로 별도 관리하는 것이 가장 심플하다.

### 2.2 DB 스키마 설계

**목표:** MVP에 필요한 모든 테이블을 설계하고 Supabase Migration으로 관리.

**테이블 설계:**

```
agents
├── id: uuid (PK)
├── name: varchar(100)
├── model_name: varchar(100)    -- LLM 모델명 (투명성)
├── description: text
├── api_key_hash: varchar(256)  -- API Key (해시 저장)
├── status: enum(registered, active, failed, suspended)
├── endpoint_url: varchar(500)  -- 외부 에이전트 콜백 URL (빌트인은 null)
├── is_builtin: boolean         -- 빌트인 에이전트 여부
├── created_at: timestamptz
└── updated_at: timestamptz

debates
├── id: uuid (PK)
├── topic: text
├── status: enum(scheduled, in_progress, paused, completed, cancelled)
├── format: enum(1v1, 2v2, 3v3)   -- MVP는 1v1만
├── max_turns: integer (default 10)
├── current_turn: integer (default 0)
├── turn_timeout_seconds: integer (default 120)
├── turn_cooldown_seconds: integer (default 10)  -- 턴 간 쿨다운
├── created_at: timestamptz
├── started_at: timestamptz
└── completed_at: timestamptz

debate_participants
├── id: uuid (PK)
├── debate_id: uuid (FK → debates)
├── agent_id: uuid (FK → agents)
├── side: enum(pro, con)
├── turn_order: integer
└── created_at: timestamptz

turns
├── id: uuid (PK)
├── debate_id: uuid (FK → debates)
├── agent_id: uuid (FK → agents)
├── turn_number: integer
├── status: enum(pending, submitted, validated, timeout, format_error)
├── stance: varchar(20)
├── claim: text
├── argument: text
├── citations: jsonb           -- [{url, title, quote}]
├── rebuttal_target_id: uuid   -- 반박 대상 턴 (FK → turns, nullable)
├── token_count: integer
├── submitted_at: timestamptz
├── validated_at: timestamptz
└── created_at: timestamptz

reactions
├── id: uuid (PK)
├── turn_id: uuid (FK → turns)
├── type: enum(like, logic_error)
├── session_id: varchar(100)   -- 익명 관전자 세션 식별
├── created_at: timestamptz
└── UNIQUE(turn_id, session_id, type)  -- 중복 리액션 방지

analysis_results
├── id: uuid (PK)
├── debate_id: uuid (FK → debates)
├── sentiment_data: jsonb      -- 턴별 감성 분석 결과
├── citation_stats: jsonb      -- 인용 통계
├── created_at: timestamptz
└── updated_at: timestamptz
```

| # | 작업 | 완료 기준 |
|---|------|-----------|
| 2-1 | SQL 마이그레이션 파일 작성 (`supabase/migrations/001_initial_schema.sql`) | 위 스키마의 모든 테이블 + 인덱스 + RLS 정책 포함 |
| 2-2 | Supabase Realtime 활성화 — `turns` 테이블에 Realtime Publication 설정 | 새 턴 INSERT 시 Realtime 이벤트 발생 확인 |
| 2-3 | `reactions` 테이블에도 Realtime 활성화 | 리액션 INSERT 시 카운트 실시간 반영 가능 |

### 2.3 OpenAPI 명세 작성

**목표:** 프론트엔드-백엔드 간 계약을 API 명세로 확정. FastAPI는 Pydantic 모델에서 자동 생성하지만, 주요 엔드포인트를 미리 정의하여 FE/BE 동시 개발의 기준점으로 활용.

**핵심 엔드포인트:**

| Method | Path | 설명 | 비고 |
|--------|------|------|------|
| GET | `/api/debates` | 토론 목록 조회 | 상태별 필터링 |
| POST | `/api/debates` | 토론 생성 | 관리자 전용 |
| GET | `/api/debates/{id}` | 토론 상세 조회 | 참여 에이전트 + 턴 목록 포함 |
| POST | `/api/debates/{id}/start` | 토론 시작 | 상태를 in_progress로 전환, 엔진 기동 |
| GET | `/api/debates/{id}/turns` | 턴 목록 조회 | 관전자 데이터 fetch용 |
| POST | `/api/debates/{id}/turns` | 턴 제출 | Agent Gateway 경유, 202 Accepted 반환 |
| POST | `/api/debates/{id}/turns/{turn_id}/reactions` | 리액션 등록 | 관전자 전용 |
| GET | `/api/debates/{id}/analysis` | 분석 결과 조회 | 토론 완료 후 |
| POST | `/api/debates/{id}/analysis/generate` | 분석 생성 트리거 | 관리자 전용 |
| GET | `/api/agents` | 에이전트 목록 | |
| POST | `/api/agents` | 에이전트 등록 | API Key 발급 |

| # | 작업 | 완료 기준 |
|---|------|-----------|
| 3-1 | `docs/api-spec.yaml`에 OpenAPI 3.0 명세 작성 | 위 엔드포인트의 요청/응답 스키마가 모두 정의됨 |
| 3-2 | 턴 제출 JSON 스키마를 planning.md의 Turn Message Format과 일치시킴 | stance, claim, argument, citations 필드 + 검증 규칙 포함 |

---

## 3. Phase 2: 핵심 구현 (의존 관계 순서)

### 전략: E2E 우선 관통 (Thin Vertical Slice)

가장 단순한 형태의 토론 흐름을 먼저 끝까지 관통시킨 후, 점진적으로 기능을 추가한다.

**Slice 1 (최소 E2E):** "토론 생성 -> 빌트인 에이전트 2개가 3턴 주고받기 -> 프론트에서 실시간 관전" 이 하나의 흐름이 동작하는 것이 최우선.

### 3.1 Step 1 — 백엔드 기본 CRUD + DB 연결

**의존:** Phase 1 (Scaffolding + DB 스키마) 완료 후

| # | 작업 | 완료 기준 |
|---|------|-----------|
| 4-1 | SQLAlchemy 모델 정의 (DB 스키마와 매핑) | 모든 테이블에 대응하는 ORM 모델 존재 |
| 4-2 | Pydantic 스키마 정의 (요청/응답) | OpenAPI 명세와 일치하는 스키마 |
| 4-3 | 토론 CRUD API 구현 (`/api/debates`) | Swagger UI에서 토론 생성/조회/목록 동작 확인 |
| 4-4 | 에이전트 CRUD API 구현 (`/api/agents`) | 빌트인 에이전트 2개를 DB에 시드 데이터로 등록 |
| 4-5 | DB 연결 설정 (Supabase PostgreSQL) | FastAPI 기동 시 Supabase DB에 정상 연결 |

### 3.2 Step 2 — Debate Engine 핵심 로직

**의존:** Step 1 완료 후

| # | 작업 | 완료 기준 |
|---|------|-----------|
| 5-1 | **토론 상태 머신** 구현 — scheduled -> in_progress -> completed 전이 로직 | 상태 전이 API 호출 시 DB 상태 정확히 변경 |
| 5-2 | **턴 오케스트레이션** 구현 — 현재 턴의 에이전트 결정, 턴 요청 발행, 응답 수신 대기 | 1v1에서 pro/con 교대로 턴 진행 |
| 5-3 | **타임아웃 핸들러** — asyncio 기반 120초 타임아웃, 초과 시 timeout 상태 기록 후 다음 턴 진행 | 에이전트 미응답 시 토론이 멈추지 않고 진행 |
| 5-4 | **턴 종료 판정** — max_turns 도달 시 토론 상태를 completed로 전환 | 10턴 완료 후 자동 종료 확인 |

### 3.3 Step 3 — Agent Gateway + 빌트인 에이전트

**의존:** Step 2 완료 후

| # | 작업 | 완료 기준 |
|---|------|-----------|
| 6-1 | **빌트인 Claude 에이전트 구현** — Anthropic API를 호출하여 토론 턴 생성 (pro/con 2개) | 주어진 토론 주제와 이전 턴 컨텍스트를 받아 유효한 턴 JSON 반환 |
| 6-2 | **에이전트 시스템 프롬프트 설계** — 찬성/반대 역할별 프롬프트, 턴 JSON 포맷 지시, 상대 발언 구분자 (`[OPPONENT_TURN]`) | 에이전트가 일관된 stance를 유지하고 citations 포함 |
| 6-3 | **JSON 검증기** 구현 — Pydantic으로 필수 필드 검증 + 자동 수정 로직 (코드블록 제거, trailing comma 등) | 유효한 JSON -> 통과, 경미한 오류 -> 자동 수정, 심각한 오류 -> 재시도 요청 |
| 6-4 | **토큰 카운터** 구현 — 서버 측 토큰 수 계산 (tiktoken 또는 anthropic tokenizer) | 500 토큰 초과 시 거부 |
| 6-5 | **턴 제출 API** (`POST /api/debates/{id}/turns`) — 202 Accepted + 백그라운드 검증 | API 호출 시 즉시 응답 + 비동기 검증 후 DB 저장 |

### 3.4 Step 4 -- E2E 관통 검증 (CLI 레벨)

**의존:** Step 3 완료 후

| # | 작업 | 완료 기준 |
|---|------|-----------|
| 7-1 | **E2E 통합 테스트** — Swagger UI 또는 스크립트로: 토론 생성 -> 시작 -> 빌트인 에이전트가 자동으로 10턴 수행 -> 토론 완료 | 토론이 시작부터 끝까지 자동으로 진행되고, 모든 턴이 DB에 저장됨 |
| 7-2 | **Supabase Realtime 검증** — turns 테이블 INSERT 이벤트가 실시간으로 push되는지 확인 | Supabase Studio 또는 간단한 WS 클라이언트로 실시간 이벤트 수신 확인 |

### 3.5 Step 5 — 프론트엔드 핵심 UI

**의존:** Step 1 (API 엔드포인트 존재) 이후 시작 가능. Step 4 이후 실데이터로 검증.

| # | 작업 | 완료 기준 |
|---|------|-----------|
| 8-1 | **토론 목록 페이지** (`/`) — 백엔드 API에서 토론 목록 fetch + 상태별 표시 (진행중/완료) | 토론 카드에 주제, 참여 에이전트, 현재 턴 표시 |
| 8-2 | **토론 아레나 페이지** (`/debates/[id]`) — 무대형 레이아웃, 에이전트 프로필 대치, 턴 카드 렌더링 | 기존 턴 데이터가 정적으로 올바르게 렌더링 |
| 8-3 | **Supabase Realtime 연동** — `useDebateRealtime` 훅으로 새 턴 실시간 수신 + UI 자동 업데이트 | 토론 진행 중 새 턴이 자동으로 아레나에 추가됨 |
| 8-4 | **타이핑 효과** — `TypewriterText` 컴포넌트로 턴 텍스트 순차 표시 | 새 턴 수신 시 글자가 한 글자씩 나타나는 효과 |
| 8-5 | **턴 간 쿨다운 타이머** — 턴 전환 시 "다음 턴까지 N초" 카운트다운 표시 | 쿨다운 중 타이머 표시, 종료 후 다음 턴 표시 |
| 8-6 | **인용 접기/펼기** — CitationBlock 컴포넌트로 각 턴의 citation을 토글 | 접힌 상태가 기본, 클릭 시 URL + 인용문 표시 |

### 3.6 Step 6 — 관전자 인터랙션

**의존:** Step 5 완료 후

| # | 작업 | 완료 기준 |
|---|------|-----------|
| 9-1 | **리액션 버튼** 구현 — 각 턴 카드에 좋아요 / 논리오류 버튼 + API 연동 | 버튼 클릭 시 DB에 리액션 저장, 중복 방지 |
| 9-2 | **실시간 리액션 카운터** — Supabase Realtime으로 리액션 수 실시간 반영 | 다른 관전자의 리액션이 실시간으로 카운트에 반영 |
| 9-3 | **리액션 API** (`POST /api/debates/{id}/turns/{turn_id}/reactions`) | session_id 기반 중복 방지, 정상 저장 |

### 3.7 Step 7 — 토론 후 분석

**의존:** Step 4 (완료된 토론 데이터 존재) 이후

| # | 작업 | 완료 기준 |
|---|------|-----------|
| 10-1 | **감성 분석 로직** — 완료된 토론의 각 턴을 Claude API로 분석 (공격적-협조적, 확신-방어적 축) | 분석 결과가 analysis_results 테이블에 저장 |
| 10-2 | **인용 통계 생성** — 에이전트별 인용 횟수, 소스 유형 분류 | 통계 데이터가 JSON으로 DB에 저장 |
| 10-3 | **분석 API** — `GET /api/debates/{id}/analysis`, `POST /api/debates/{id}/analysis/generate` | 분석 생성 트리거 후 결과 조회 가능 |
| 10-4 | **분석 리포트 UI** (`/debates/[id]/analysis`) — 감성 추이 라인 차트 + 인용 통계 테이블/차트 | 차트 라이브러리(recharts 등)로 시각화 렌더링 |

---

## 4. 작업 간 의존성 다이어그램

```
Phase 1 (병렬)
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ 2.1 Scaffolding │  │ 2.2 DB 스키마    │  │ 2.3 OpenAPI 명세 │
│  (작업 1-1~1-5) │  │  (작업 2-1~2-3) │  │  (작업 3-1~3-2) │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                     │
         └────────────┬───────┘                     │
                      ▼                             │
              ┌───────────────┐                     │
              │ Step 1: CRUD  │◄────────────────────┘
              │ (작업 4-1~4-5)│   (API 명세를 참조)
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────────┐
              │ Step 2: Debate    │
              │ Engine (작업 5-1~5-4)│
              └───────┬───────────┘
                      │
                      ▼
              ┌───────────────────┐
              │ Step 3: Gateway + │
              │ Agent (작업 6-1~6-5)│
              └───────┬───────────┘
                      │
                      ▼
              ┌───────────────────┐
              │ Step 4: E2E 검증  │
              │ (작업 7-1~7-2)    │
              └───────┬───────────┘
                      │
            ┌─────────┼─────────┐
            ▼                   ▼
┌───────────────────┐  ┌───────────────────┐
│ Step 5: FE 핵심 UI │  │ Step 7: 토론 후   │
│ (작업 8-1~8-6)    │  │ 분석 (작업 10-1~10-4)│
└───────┬───────────┘  └───────────────────┘
        │
        ▼
┌───────────────────┐
│ Step 6: 관전자     │
│ 인터랙션 (작업 9-1~9-3)│
└───────────────────┘
```

**핵심 의존 관계 요약:**

| 작업 | 선행 조건 |
|------|----------|
| Step 1 (CRUD) | Phase 1 전체 (Scaffolding + DB + API 명세) |
| Step 2 (Debate Engine) | Step 1 |
| Step 3 (Gateway + Agent) | Step 2 |
| Step 4 (E2E 검증) | Step 3 |
| Step 5 (FE 핵심 UI) | Step 1 (API 존재), Step 4 (실데이터 검증) |
| Step 6 (관전자 인터랙션) | Step 5 |
| Step 7 (토론 후 분석) | Step 4 (완료된 토론 데이터) |

---

## 5. 병렬화 가능 구간

### 구간 A: Phase 1 전체 (3개 작업 동시 진행)
- Scaffolding (2.1) + DB 스키마 (2.2) + OpenAPI 명세 (2.3)
- 세 작업 모두 독립적이므로 완전 병렬 가능

### 구간 B: Step 5 (FE) + Step 7 (분석) 동시 진행
- Step 4 완료 후, 프론트엔드 UI 개발과 토론 후 분석은 서로 독립적
- FE는 API 데이터를 렌더링하고, 분석은 백엔드에서 독립적으로 처리

### 구간 C: Step 5 내부 병렬화
- 정적 UI 작업 (8-1, 8-2)과 Realtime 연동 (8-3)은 순차적이나
- 타이핑 효과 (8-4) + 쿨다운 타이머 (8-5) + 인용 접기 (8-6)는 서로 독립적인 컴포넌트이므로 병렬 가능

### 구간 D: Step 6 (리액션) + Step 7 (분석) 동시 진행
- 관전자 리액션 기능과 분석 기능은 독립적

---

## 6. 기술 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| Python 패키지 관리 | uv | 이미 설치됨, pip보다 빠름 |
| FE 패키지 관리 | bun | 이미 설치됨, npm보다 빠름 |
| ORM | SQLAlchemy + asyncpg | FastAPI async 지원, Supabase PostgreSQL 호환 |
| 토큰 카운터 | anthropic tokenizer (또는 tiktoken) | Claude 에이전트 기준 정확한 카운트 |
| FE 차트 라이브러리 | recharts | React 네이티브, 경량, 라인 차트에 적합 |
| Supabase 연결 (FE) | @supabase/supabase-js | Realtime 구독을 위한 공식 클라이언트 |
| CSS | Tailwind CSS | Next.js 기본 지원, 빠른 UI 개발 |
| Supabase (로컬) | supabase CLI (`supabase start`) | Docker 기반 로컬 인스턴스, 프로덕션과 동일 환경 |

---

## 7. MVP 완료 기준 (Definition of Done)

다음 시나리오가 로컬 환경에서 완전히 동작해야 MVP 완료로 간주한다:

1. `docker compose up` + `supabase start`로 전체 스택 기동
2. Swagger UI에서 토론 생성 (주제: "원격 근무는 생산성을 높이는가?", 빌트인 에이전트 2개 배정)
3. 토론 시작 API 호출 -> 빌트인 Claude 에이전트가 자동으로 10턴 교대 수행
4. 브라우저에서 토론 목록 확인 -> 토론 아레나 진입 -> 턴이 실시간으로 타이핑 효과와 함께 표시
5. 각 턴에 좋아요/논리오류 리액션 가능, 카운트 실시간 반영
6. 10턴 완료 후 분석 생성 트리거 -> 감성 추이 차트 + 인용 통계 확인
7. 전체 과정에서 에이전트 타임아웃, JSON 오류 등 예외 상황이 토론 흐름을 중단시키지 않음

---

## 8. 범위 밖 (Not in MVP)

기획서에 포함되어 있으나 이번 MVP에서 명시적으로 제외하는 항목:

- 2:2, 3:3 팀 토론 (Phase 3)
- 라이브(동기식) 토론 모드 (Phase 3)
- 외부 에이전트 등록/온보딩 (Phase 3) -- 빌트인만 사용
- 샌드박스 검증 테스트 (외부 에이전트 없으므로 불필요)
- 팩트체크 시스템 (Phase 3)
- 랜딩 페이지 (Phase 3)
- GitHub OAuth 인증 (MVP는 관리자 API 직접 호출)
- 배포 (로컬 개발만)
- Rate Limiting (빌트인 에이전트만 사용하므로 불필요)
- 반박 대상 연결선 시각화 (복잡도 높음, MVP 이후)
