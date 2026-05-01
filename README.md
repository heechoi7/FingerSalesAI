# FingerSalesAI

## 프로젝트 공통 문서

새 장비, 새 팀원, 새 Codex 세션에서 작업을 시작할 때는 아래 문서를 먼저 읽습니다.

- `docs/PROJECT_GUIDE.md`: 프레임워크, DB 구성, 메뉴 구성, 상세 로직, 공통 코드, 보안/역할, 운영 기준
- `docs/HANDOFF_WORKFLOW.md`: Windows/Mac 작업 연속성, 팀 협업, 다른 Codex 인수인계 절차
- `docs/AGENT_COMMANDS.md`: 에이전트 대화창 명령 케이스 레지스트리와 신규 명령 추가 절차
- `README.md`: 지금까지의 변경 이력, 검증 명령, 남은 작업

작업 후에는 `README.md`의 변경 이력과 관련 `docs/` 문서를 함께 갱신합니다.

FingerSalesAI는 기존 FingerSales CRM에 AI 기능을 덧붙이는 수준이 아니라, 입력을 최소화하고 AI가 영업 업무를 먼저 정리, 제안, 실행하는 세일즈 에이전트 클라우드입니다.

제품명:
- FingerSalesAI

핵심 문장:
- 영업사원이 입력하지 않아도, AI가 고객, 활동, 일정, 제안, 팔로업을 정리하고 다음 행동을 제안하는 AI 세일즈 클라우드

핵심 가치:
- Zero Input CRM
- Conversational Sales Agent
- Sales Intelligence

제품 방향:
- 기존 CRM은 사용자가 데이터를 입력해야 가치가 생기지만, FingerSalesAI는 AI가 명함, 미팅, 이메일, 일정, 견적, 계약 데이터를 읽고 정리해서 영업사원이 대화로 일하는 구조를 지향합니다.
- 명함 인식과 고객 등록은 첫 진입 기능이며, 최종 목표는 고객/활동/일정/제안/팔로업을 AI가 선제적으로 정리하고 다음 행동을 제안하는 업무 흐름입니다.
- 앞으로의 기능 개발은 "사용자가 직접 입력해야 하는 항목을 줄이는가", "AI가 다음 행동을 더 잘 제안하게 하는가", "대화만으로 영업 업무가 진행되는가"를 기준으로 판단합니다.

이 문서는 2026-04-30 현재까지 Codex와 함께 작업한 내역, 현재 구조, 실행 방법, 검증 방법, 그리고 앞으로 작업할 때 반드시 이어서 기록해야 할 변경 이력을 정리합니다.

## 작업 기록 작성 규칙

앞으로 이 프로젝트에서 기능 추가, 버그 수정, DB 스키마 연동, 화면 수정, 실행 방식 변경, 의존성 변경이 발생하면 이 `README.md`의 "변경 이력"과 관련 섹션을 함께 갱신합니다.

기록할 내용:
- 작업 날짜
- 변경한 파일
- 변경 목적
- API, DB, UI 동작 변화
- 실행 또는 검증한 명령
- 남은 이슈나 다음 작업

민감한 값은 직접 기록하지 않습니다. 예를 들어 API 키, 실제 운영 비밀번호, 토큰, 세션 서명 키는 값 대신 환경 변수 이름만 기록합니다.

## 현재 기술 구성

- Backend: FastAPI
- Runtime: Python, uv
- Frontend: 정적 HTML/CSS/JavaScript
- Database: MySQL 8.4
- AI/Agent: LangGraph, LangChain, Gemini, Tavily
- Auth: FastAPI API 로그인 + 서명된 HTTP-only 세션 쿠키
- Password verification: bcrypt 우선 지원

## 주요 파일

- `main.py`: FastAPI 앱, 인증 API, 고객/연락처 CRUD API, 명함 분석 API, 채팅 API
- `database.py`: MySQL 연결, 필수 테이블 확인, 테넌트 기본값, 연락처 조회 결과 변환
- `graph.py`: 명함 이미지 분석 및 회사 리서치 LangGraph 워크플로
- `index.html`: 메인 CRM/채팅 화면
- `login.html`: 멀티테넌트 로그인 화면
- `script.js`: 프론트엔드 이벤트, 고객 목록 로드, 명함 업로드, 채팅, 세션 표시, 로그아웃
- `styles.css`: 전체 UI 스타일
- `requirements.txt`: Python 의존성 목록
- `pyproject.toml`: uv가 프로젝트 의존성을 인식하도록 추가한 프로젝트 메타데이터
- `.env.example`: 로컬 실행에 필요한 환경 변수 예시

## 환경 변수

`.env`에 아래 값들이 필요합니다.

```env
GOOGLE_API_KEY=...
TAVILY_API_KEY=...

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=FingerSalesAI
MYSQL_USER=...
MYSQL_PASSWORD=...
MYSQL_TENANT_ID=1

APP_SESSION_SECRET=...
FSAI_EXTRA_ENV_PATH=
APP_ENV=development
APP_ALLOWED_HOSTS=
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=lax
MIN_PASSWORD_LENGTH=8
AUTH_RATE_LIMIT_MAX=10
AUTH_RATE_LIMIT_WINDOW_SECONDS=60
TRUST_PROXY_HEADERS=false
MYSQL_POOL_SIZE=10
MYSQL_CONNECTION_TIMEOUT=10
ALLOW_EXISTING_TENANT_SELF_JOIN=false
TENANT_JOIN_CODE=
MAX_UPLOAD_BYTES=5242880
MAX_SNS_LINKS_PER_REQUEST=3
SOCIAL_FETCH_TIMEOUT_SECONDS=3
```

주의:
- `.env`에는 실제 키와 비밀번호가 들어가므로 문서나 외부 공유물에 직접 복사하지 않습니다.
- `APP_SESSION_SECRET`은 로그인 세션 쿠키 서명에 사용됩니다. 운영 또는 외부 접속 환경에서는 긴 랜덤 값으로 설정해야 합니다.
- `APP_ENV=production`에서는 `APP_SESSION_SECRET`이 32자 이상이어야 서버가 시작됩니다.
- `ALLOW_EXISTING_TENANT_SELF_JOIN=false`가 기본이며, 기존 테넌트 가입은 관리자 초대/가입 코드 방식으로 제한해야 합니다.
- `MYSQL_TENANT_ID`는 로그인 이전 기본값 또는 로컬 기본값 용도였고, 현재 후속 작업 API는 로그인 세션의 `tenant_id`를 우선 사용합니다.
- `MAX_UPLOAD_BYTES`는 이미지 업로드 최대 크기입니다. 기본값은 5MB입니다.
- `MAX_SNS_LINKS_PER_REQUEST`는 SNS 링크 처리 요청 1회당 최대 링크 수입니다. 기본값은 3개입니다.
- `SOCIAL_FETCH_TIMEOUT_SECONDS`는 SNS 공개 메타데이터 후보 URL 1개당 fetch timeout입니다. 기본값은 3초입니다.
- 모든 업무 테이블은 soft delete를 기본 정책으로 사용합니다. 앱 시작 시 `init_db()`가 현재 스키마의 기본 테이블 중 `deleted_at` 컬럼이 없는 테이블에 `deleted_at DATETIME(6) NULL`을 보강합니다.
- 삭제 API나 삭제성 기능은 `DELETE FROM`을 사용하지 않고 `deleted_at = NOW(6)` 또는 상태 컬럼 변경으로 처리해야 합니다.
- 모든 DB CRUD는 `audit_logs`에 `action`, `entity_type`, `entity_id`, `before_json`, `after_json`, IP, user-agent를 남기는 것을 기본 정책으로 합니다.
- 고객 저장/수정/삭제는 업무 단위 로그와 별도로 `accounts`, `contacts` 테이블 단위 create/update/delete 감사 로그도 남깁니다.

## 실행 방법

처음 실행 또는 의존성 변경 후:

```powershell
uv run main.py
```

브라우저 접속:

```text
http://localhost:8000/login.html
```

로그인 성공 후 메인 화면:

```text
http://localhost:8000/
```

## 데이터베이스 구조 연동

사용자가 로컬 MySQL 8.4에 `FingerSalesAI` 데이터베이스와 CRM 테이블을 이미 생성한 상태에서 작업했습니다.

확인된 핵심 테이블:

- `tenants`: 테넌트
- `users`: 사용자
- `accounts`: 고객사
- `contacts`: 연락처

중요한 점:
- 사용자가 처음 `acounts`라고 언급했지만 실제 DB 테이블명은 `accounts`입니다.
- `accounts`는 고객사 정보를 저장합니다.
- `contacts`는 사람/연락처 정보를 저장합니다.
- 모든 후속 고객 작업은 로그인 세션의 `tenant_id`와 `user_id`를 사용합니다.

## 명함 저장 규칙

명함 이미지 분석 결과는 회사 정보와 연락처 정보로 나누어 저장됩니다.

저장 흐름:
1. 명함 이미지 업로드
2. `graph.py`의 LangGraph 워크플로가 명함 여부와 필드 추출
3. `main.py`의 `/api/extract`가 로그인 세션을 확인
4. 회사명과 로그인 사용자 ID 기준으로 `accounts` 조회
5. 같은 `tenant_id`, `owner_user_id` 안에 같은 회사명이 있으면 `accounts`는 신규 insert하지 않고 새 값으로 update
6. 같은 회사명이 없으면 `accounts`에 신규 고객사 insert
7. `contacts`에는 항상 새 연락처 행 insert
8. insert된 연락처를 `accounts`와 join해 프론트에 반환

`accounts` 업데이트 방식:
- 기존 값이 있고 새 값이 비어 있으면 기존 값을 유지합니다.
- 새로 들어온 홈페이지, 대표전화, 주소, 사업자등록번호, 산업군, owner user 값은 가능한 범위에서 반영합니다.

`contacts` insert 방식:
- 매번 새 행을 추가합니다.
- `tenant_id`는 로그인 세션에서 가져옵니다.
- `owner_user_id`는 로그인한 사용자 ID를 사용합니다.
- 이름이 추출되지 않으면 `"이름 미확인"`으로 저장합니다.

## 고객 목록과 상세 표시

고객 메뉴 동작:
- 앱이 열릴 때 로그인 세션 확인 후 `/api/customers`를 호출합니다.
- 고객 메뉴를 클릭할 때마다 DB에서 최신 연락처 목록을 다시 조회합니다.
- 조회는 로그인한 사용자의 `tenant_id`와 `user_id(owner_user_id)` 기준으로 제한됩니다.

그리드 행 클릭:
- 고객 그리드 행을 클릭하면 해당 행이 선택됩니다.
- 하단 상세 영역에 DB 기준 상세 정보를 표시합니다.
- 표시 항목은 테넌트 ID, 고객사 ID, 연락처 ID, 회사, 담당자, 직무/직위, 연락처, 이메일, 홈페이지, 주소, 대표전화, 추가 정보입니다.
- 채팅 질문을 보낼 때 선택된 고객 정보가 `selectedCustomer` 컨텍스트로 전달됩니다.
- 에이전트는 선택된 고객이 있으면 마지막 등록 고객보다 선택된 고객을 우선 작업 대상으로 삼습니다.

## 로그인과 멀티테넌트 처리

로그인 화면:
- `login.html`에서 테넌트 코드, 이메일, 비밀번호를 입력합니다.
- `/api/auth/login`으로 로그인 요청을 보냅니다.
- 로그인 성공 시 브라우저 `localStorage`에 마지막 로그인 테넌트 코드와 이메일만 저장합니다.
- 다음 로그인 화면 진입 시 저장된 테넌트 코드와 이메일을 자동으로 채웁니다.
- 비밀번호는 저장하지 않습니다.

서버 로그인 처리:
- `tenants.tenant_code`와 `users.email`로 사용자와 테넌트를 조회합니다.
- 사용자 상태는 `active`여야 합니다.
- 테넌트 상태는 `active` 또는 `trial`이어야 합니다.
- `users.password_hash`는 bcrypt 형식으로 검증합니다.
- 로그인 성공 시 `last_login_at`을 갱신합니다.
- 로그인 세션은 HTTP-only 쿠키 `fsai_session`에 서명된 토큰으로 저장합니다.

세션 확인:
- `/api/auth/me`는 현재 로그인 사용자와 테넌트 정보를 반환합니다.
- 세션 쿠키가 유효해도 API 요청마다 `users`와 `tenants`의 현재 상태를 다시 확인합니다.
- 삭제/비활성 사용자, 중지된 테넌트의 기존 쿠키는 더 이상 보호 API를 통과하지 못합니다.
- 메인 화면은 이 정보를 읽어 상단에 사용자 이름, 역할, 테넌트 이름을 표시합니다.

로그아웃:
- 상단 로그아웃 버튼 클릭 시 `/logout`으로 이동합니다.
- 서버가 세션 쿠키를 삭제한 뒤 `/login.html`로 리다이렉트합니다.

보호된 API:
- `/api/customers`
- `/api/customers/{customer_id}`
- `/api/extract`
- `/api/chat`

위 API들은 세션이 없으면 `401`을 반환하고, 프론트는 로그인 페이지로 이동합니다.

## API 요약

인증:

- `POST /api/auth/login`
  - body: `tenant_code`, `email`, `password`
  - 성공 시 세션 쿠키 발급

- `POST /api/auth/register`
  - body: `tenant_code`, `tenant_name`, `name`, `email`, `password`, `role`
  - 테넌트가 없으면 새로 생성하고, 있으면 해당 테넌트에 사용자를 추가
  - 성공 시 세션 쿠키를 발급하지 않고 로그인 화면에서 다시 로그인하도록 안내

- `GET /api/auth/me`
  - 현재 세션 사용자/테넌트 정보 반환

- `POST /api/auth/logout`
  - 세션 쿠키 삭제

- `GET /logout`
  - 세션 쿠키 삭제 후 `/login.html`로 리다이렉트

관리자:

- `/admin`
  - 우측 상단 도구 버튼에서 진입하는 별도 관리자 페이지
  - `owner`, `admin` 역할만 접근 가능

- `/settings/users`, `/settings/teams`, `/settings/pipeline`
  - 관리자 페이지의 사용자 관리, 팀 관리, 영업 단계 설정 화면으로 직접 진입하는 설정 라우트

- `GET /api/admin/summary`
  - 관리자 홈 요약, 테넌트 정보, 사용자/팀/영업 단계/감사 로그 수 반환

- `GET /api/admin/company`, `PUT /api/admin/company`
  - 현재 로그인 테넌트의 회사 정보 조회/수정
  - `tenants`, `tenant_settings` 테이블 사용

- `GET /api/admin/users`, `PUT /api/admin/users/{user_id}`, `DELETE /api/admin/users/{user_id}`
  - 현재 테넌트 사용자 목록 조회 및 이름/전화번호/팀/역할/상태 수정, 사용자 soft delete
  - 비밀번호 해시는 응답이나 감사 로그에 포함하지 않음

- `POST /api/admin/users/invite`
  - 사용자 초대
  - 초대 사용자는 `invited` 상태로 생성하고 임시 비밀번호를 반환
  - 역할은 `owner`를 제외한 관리자 허용 역할만 지정 가능

- `GET /api/admin/teams`, `POST /api/admin/teams`, `PUT /api/admin/teams/{team_id}`, `DELETE /api/admin/teams/{team_id}`
  - 팀 목록 조회, 추가, 수정, soft delete
  - `users.team_id`로 팀원 배정
  - 현재 `teams`에 팀장 컬럼이 없으므로 팀장 지정은 `tenant_settings.setting_key = team_leaders` JSON 매핑으로 관리

- `GET /api/admin/roles`
  - 현재 `users.role` enum과 서버 역할 정의 기준의 권한 설명 반환

- `GET /api/admin/codes`, `PUT /api/admin/codes`
  - `tenant_settings.setting_key = custom_codes`에 저장되는 테넌트별 사용자 정의 코드 그룹/항목 조회 및 저장
  - 별도 코드 테이블이 생기기 전까지 JSON 설정값으로 관리

- `GET /api/admin/pipeline-stages`, `POST /api/admin/pipeline-stages`, `PUT /api/admin/pipeline-stages/{stage_id}`, `DELETE /api/admin/pipeline-stages/{stage_id}`
  - `pipeline_stages` 기반 영업 단계 조회/추가/수정/soft delete

- `POST /api/admin/pipeline-stages/defaults`
  - 기본 영업 단계 `lead`, `prospect`, `opportunity`, `proposal`, `contract`, `success` 중 없는 단계만 생성

- `GET /api/admin/logs`
  - `audit_logs` 기반 사용로그 조회
  - 관리자 변경뿐 아니라 로그인/로그아웃, 주요 조회, 고객 CRUD, SNS 확인, 명함 인식, 에이전트 질문도 감사 로그로 기록

고객:

- `GET /api/customers`
  - 로그인 세션의 `tenant_id`, `user_id(owner_user_id)` 기준으로 contacts/accounts join 조회
  - 조회 조건: `company_name`, `contact_name`

- `GET /api/customers/{customer_id}`
  - 로그인 세션의 `tenant_id`, `user_id(owner_user_id)` 안에서 특정 연락처 조회

- `POST /api/customers`
  - 세션의 `tenant_id`, `user_id`를 사용해 사용자 소유 고객사 upsert + 연락처 insert

- `PUT /api/customers/{customer_id}`
  - 세션의 `tenant_id`, `user_id`를 사용해 사용자 소유 고객사 upsert + 연락처 update

- `DELETE /api/customers/{customer_id}`
  - 실제 삭제가 아니라 `contacts.deleted_at = NOW(6)` 소프트 삭제

메인 메뉴 조회:

- `GET /api/opportunities`
  - 영업기회 테이블 `opportunities` 기준 조회
  - 조회 조건: `name`(영업기회명), `status`(영업기회 상태), `company_name`
  - 로그인 세션의 `tenant_id`, `user_id(owner_user_id)` 기준으로 제한

- `GET /api/calendar`
  - `meetings`, `activities`, `action_items`를 년/월 범위로 합쳐 월간 캘린더에 표시
  - 조회 조건: `year`, `month`
  - 로그인 사용자가 주최/담당/보고자인 일정성 데이터만 조회
  - 에이전트 채팅에서 생성한 영업활동 일정은 `activities`에 저장되고 이 캘린더에 표시

- `GET /api/quotes`
  - 견적 테이블 `quotes` 기준 조회
  - 조회 조건: `company_name`, `contact_name`
  - 로그인 세션의 `tenant_id`, `user_id(owner_user_id)` 기준으로 제한
  - 업로드 문서가 연결된 경우 `document_id`, `document_filename`, `document_url`을 함께 반환

- `GET /api/contracts`
  - 계약 테이블 `contracts` 기준 조회
  - 조회 조건: `company_name`, `contact_name`
  - 로그인 세션의 `tenant_id`, `user_id(owner_user_id)` 기준으로 제한
  - 업로드 문서가 연결된 경우 `document_id`, `document_filename`, `document_url`을 함께 반환

명함:

- `POST /api/extract?skip_briefing=false`
  - 이미지 파일 업로드
  - 명함 정보 추출
  - accounts/contacts에 저장

- `POST /api/extract/document`
  - Word, Excel, PDF, CSV, TXT 파일 업로드
  - 문서 내용을 추출하고 견적서/계약서 여부를 분류
  - 견적서는 `quotes`, 계약서는 `contracts`에 저장
  - 필수 연결 데이터인 `accounts`, `opportunities`를 현재 로그인 사용자 범위에서 생성/보강
  - 원본 파일은 `uploads/documents`에 저장하고 `uploaded_documents`에 다운로드 링크 메타데이터를 기록

- `GET /api/documents/{document_id}/download`
  - 로그인 사용자의 `tenant_id`, `user_id` 범위에 속한 문서만 다운로드
  - 다운로드 시 `audit_logs`에 `uploaded_document` download 기록

에이전트 업무 실행:

- `POST /api/chat`
  - 요청 진입 직후, 메시지에 등록 고객의 회사명 또는 고객명이 포함되어 있는지 현재 `tenant_id`, `user_id(owner_user_id)` 범위에서 먼저 조회
  - 후보가 1건이면 해당 고객을 `selectedCustomer`로 자동 지정한 뒤 명령을 계속 처리
  - 후보가 여러 건이면 `customer_selection_required=true`와 후보 목록을 반환하고, 프론트에서 사용자가 고객을 선택하면 같은 명령을 이어서 재실행
  - 이 고객 선확인 흐름은 일정, SNS fallback, 일반 LLM 답변 등 `/api/chat`으로 들어오는 모든 명령의 공통 전처리입니다.
  - 일반 질문은 기존 대화/검색 에이전트 흐름으로 처리
  - "일정 등록", "영업활동 추가", "미팅 잡아줘", "전화 일정 등록"처럼 영업활동 일정 등록 의도가 감지되면 LLM 호출 전에 서버가 `activities`에 `planned` 상태로 저장
  - "일정 취소", "날짜 변경", "다음 주 화요일로 옮겨줘", "반복 일정 등록", "일정 목록 보여줘" 같은 일정 관리 명령도 서버가 직접 처리
  - 고객은 채팅 컨텍스트의 선택 고객을 우선 사용하고, 메시지에 등록된 고객의 회사명/고객명이 들어 있으면 해당 고객을 매칭
  - 일정 날짜는 `오늘`, `내일`, `모레`, `YYYY-MM-DD`, `M월 D일`, `이번/다음 주 요일` 형태를 지원
  - 시간은 `오전/오후 N시`, `HH:MM`, `N시 반` 형태를 지원하며, 시간이 없으면 오전 9시로 저장
  - 반복 일정은 `매일`, `매주`, `매월`, `N회`를 지원하며 `MAX_RECURRING_ACTIVITY_COUNT` 개수까지만 생성
  - 취소는 `activities.status='cancelled'`, 날짜 변경은 `activities.due_at` 업데이트로 처리
  - 저장 완료 응답에는 `activity_saved`, `activity`, `calendar`가 포함되고 프론트가 캘린더 메뉴를 자동으로 열어 해당 월을 표시

- `POST /api/extract/sns`
  - body: `message`
  - 에이전트 입력창에 입력된 SNS 링크를 감지
  - LinkedIn, Instagram, Facebook, X, YouTube, TikTok, GitHub, Naver Blog, Medium 등 지원 SNS를 플랫폼별로 구분
  - SNS 링크를 명함 입력과 같은 고객/연락처 필드로 정규화
  - 이름이 확인된 항목만 accounts/contacts에 저장
  - 한 번에 처리 가능한 링크 수는 `MAX_SNS_LINKS_PER_REQUEST`로 제한

- `POST /api/inspect/sns`
  - body: `message`
  - SNS 링크를 플랫폼/대상 유형/핸들로 구분
  - 공개 메타데이터와 URL 구조 기반 이름 후보, 설명, 후보 fetch URL을 반환
  - 고객 DB에는 저장하지 않음
  - 현재 프론트 SNS 입력 흐름은 이 API를 우선 사용
  - `context`를 함께 받아 회사명/고객명 후보가 여러 건이면 `/api/chat`과 같은 고객 선택 응답을 반환

채팅:

- `POST /api/chat`
  - 로그인 세션 필요
  - 프론트 세션 컨텍스트와 검색 결과를 활용해 답변 생성

## 검증한 명령

프론트 문법 검사:

```powershell
node --check script.js
```

Python 문법 검사:

```powershell
uv run python -m py_compile main.py database.py graph.py
```

FastAPI 앱 import 확인:

```powershell
uv run python -c "import main; print('app import ok')"
```

MySQL 필수 테이블 확인:

```powershell
uv run python -c "from database import init_db; init_db(); print('db ok')"
```

## 변경 이력

### 2026-05-01: Home 대시보드 날짜 표시 정리

변경 파일:
- `script.js`
- `styles.css`
- `README.md`

변경 내용:
- Home 상단 오른쪽 요약 박스를 제거하고 오늘 날짜만 간단히 표시하도록 변경했습니다.
- 일일 브리핑 섹션의 상태 문구를 제거하고 브리핑 작성 날짜와 시간을 보여주도록 변경했습니다.

검증:
- `node --check script.js`
- `git diff --check`

### 2026-05-01: Home 대시보드 시각화 개선

변경 파일:
- `script.js`
- `styles.css`
- `README.md`

변경 내용:
- Home 상단 지표 카드를 단순 숫자 박스에서 대시보드 카드 형태로 재구성했습니다.
- 고객, 파이프라인, 영업활동, 견적, 계약별 아이콘과 색상 톤을 분리했습니다.
- 각 카드에 올해 누적 핵심 수치, 일/월/년 값, 미니 바 차트, 월/년 진행률 바, 금액 배지를 추가했습니다.
- 카드 hover 효과, 바 차트 등장 애니메이션, 브리핑 카드 배경/그림자 효과를 추가해 홈 화면의 시각적 밀도를 높였습니다.

검증:
- `node --check script.js`
- `git diff --check`

### 2026-05-01: 로그인 초기 Home 대시보드와 일일 브리핑 저장

변경 파일:
- `database.py`
- `main.py`
- `script.js`
- `styles.css`
- `README.md`

변경 내용:
- 로그인 후 첫 화면과 좌측 상단 로고 클릭 시 표시되는 Home 화면을 추가했습니다. Home은 별도 메뉴 버튼 없이 좌측 패널 전체를 하나의 패널로 사용합니다.
- Home 상단 섹션에 고객, 파이프라인, 영업활동, 견적, 계약 지표를 일/월/년 기준으로 보여주는 대시보드를 구현했습니다.
- `daily_briefings` 테이블을 추가해 사용자별/일자별 브리핑을 하루 1회 저장하도록 했습니다.
- `/api/home` API를 추가해 현재 사용자/테넌트 기준 대시보드 수치와 오늘 브리핑을 반환합니다. 오늘 저장된 브리핑이 없으면 현재 DB 상황을 기반으로 브리핑을 생성해 저장합니다.
- 브리핑은 최근 고객, 예정 영업활동, 파이프라인 상태와 월간 수치를 바탕으로 텍스트 중심으로 구성했습니다.

검증:
- `node --check script.js`
- `.uv-python\cpython-3.11.15-windows-x86_64-none\python.exe -m py_compile main.py database.py`
- `UV_CACHE_DIR=.uv-cache uv run python -c "import main; print('app import ok')"`
- `UV_CACHE_DIR=.uv-cache uv run python -m unittest discover -s tests`

### 2026-05-01: 문서 뷰어 깨진 텍스트 표시 방지

변경 파일:
- `main.py`
- `script.js`
- `README.md`

변경 내용:
- 기존 `.doc`/`.xls` 파일을 `latin-1`로 강제 디코딩해 바이너리 문자열이 저장되던 로직을 제거했습니다.
- 레거시 Office 문서는 UTF-16LE, CP949, UTF-8 후보 중 읽을 수 있는 텍스트만 추출하도록 보완했습니다.
- 이미 DB에 저장된 깨진 추출 텍스트도 프론트에서 표시하지 않도록 가독성 검사를 추가했습니다.
- 내부 뷰어가 지원하지 않는 문서는 깨진 문자열 대신 안내 메시지와 다운로드 링크만 보여주도록 수정했습니다.

검증:
- `node --check script.js`
- `.venv\Scripts\python.exe -m py_compile main.py`
- `.venv\Scripts\python.exe -m unittest discover -s tests`

### 2026-05-01: 견적/계약 상세 탭 레이아웃 깨짐 수정

변경 파일:
- `index.html`
- `script.js`
- `styles.css`
- `README.md`

변경 내용:
- 견적/계약 상세 탭 컨테이너가 기존 상세 필드 그리드 스타일을 상속받아 왼쪽으로 찌그러지는 문제를 수정했습니다.
- 상세 항목 행에 `detail-field-row` 클래스를 부여하고 CSS 선택자를 해당 행에만 적용하도록 좁혔습니다.
- 문서 뷰어 컨테이너가 라벨/값 2열 레이아웃으로 강제되지 않도록 탭 내부 스타일 범위를 분리했습니다.

검증:
- `node --check script.js`
- `git diff --check`

### 2026-05-01: 견적/계약 상세 탭과 업로드 문서 내부 뷰어

변경 파일:
- `main.py`
- `script.js`
- `styles.css`
- `README.md`

변경 내용:
- 견적과 계약 목록에서 최근 연결된 업로드 문서의 콘텐츠 타입, 추출 텍스트, 내부 보기 URL을 함께 내려주도록 조회 API를 확장했습니다.
- `/api/documents/{document_id}/view` 엔드포인트를 추가해 인증된 동일 테넌트/사용자 문서만 inline 방식으로 열 수 있게 했습니다.
- 견적/계약 하단 상세 영역을 `상세`, `업로드 문서` 탭 구조로 바꾸고, PDF/이미지/텍스트는 내부 프레임으로, Word/Excel 등 브라우저 직접 보기 어려운 문서는 추출 텍스트 미리보기로 확인하도록 구성했습니다.
- 문서 탭에는 원본 다운로드 링크도 유지해 내부 미리보기와 원본 파일 확인을 함께 지원합니다.

검증:
- `node --check script.js`
- `.venv\Scripts\python.exe -m py_compile main.py`

### 2026-05-01: 그리드 필터 입력/검색 버튼 정렬 조정

변경 파일:
- `styles.css`
- `README.md`

작업 내용:
- 캘린더를 제외한 그리드 메뉴 필터에서 검색 텍스트 박스는 좌측 정렬되도록 조정했습니다.
- 검색 아이콘 버튼은 기존처럼 필터 영역의 우측 끝에 유지했습니다.

검증:
- `node --check script.js`
- `git diff --check`

### 2026-05-01: 그리드 필터와 스크롤 영역 밀도 조정

변경 파일:
- `styles.css`
- `README.md`

작업 내용:
- 메뉴별 조회 조건 입력 박스 높이와 너비를 줄여 필터 영역을 더 컴팩트하게 조정했습니다.
- 입력 박스 placeholder 텍스트 크기를 실제 입력 텍스트와 동일하게 맞췄습니다.
- 그리드가 있는 화면은 바깥 패널이 스크롤되지 않고 테이블 래퍼에만 스크롤이 생기도록 변경했습니다.
- 필터 영역은 고정되고 그리드 헤더는 sticky 상태로 보여지도록 스크롤 기준을 테이블 래퍼에 집중했습니다.
- 캘린더/카드형 화면도 같은 캔버스 overflow 변경에 맞춰 내부 영역에서 스크롤되도록 보정했습니다.

검증:
- `node --check script.js`
- `git diff --check`

### 2026-05-01: 그리드 필터 입력 UI 간소화

변경 파일:
- `script.js`
- `styles.css`
- `README.md`

작업 내용:
- 고객, 파이프라인, 견적, 계약 필터의 입력 박스 위 라벨 텍스트를 제거했습니다.
- 입력 의미는 placeholder와 `aria-label`로 유지했습니다.
- 조회 버튼을 텍스트 버튼에서 돋보기 아이콘 버튼으로 변경했습니다.
- 조회 아이콘 버튼은 필터 영역 우측 끝에 정렬되도록 고정했습니다.

검증:
- `node --check script.js`
- `git diff --check`

### 2026-05-01: 메뉴 진입 시 첫 데이터 자동 선택과 상세 항목 정리

변경 파일:
- `main.py`
- `script.js`
- `styles.css`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 고객, 파이프라인, 견적, 계약 메뉴는 조회 결과의 첫 번째 행을 자동 선택하고 하단 상세 패널을 즉시 갱신하도록 했습니다.
- 캘린더 메뉴는 진입 시 오늘 날짜를 선택하고 오늘 첫 번째 일정을 상세 패널에 표시합니다.
- 에이전트가 영업활동 일정을 등록해 캘린더를 여는 경우 등록된 해당 활동을 자동 선택하고 상세 패널에 표시합니다.
- 파이프라인, 견적, 계약 목록 정렬을 최신 등록 데이터가 위에 오도록 `created_at DESC, id DESC` 기준으로 맞췄습니다.
- 캘린더 API가 하단 상세 패널에 필요한 고객명, 활동 유형, 활동 내용 정보를 함께 반환하도록 보강했습니다.
- 메뉴별 상세 패널 항목을 요청한 항목 기준으로 정리했습니다.

검증:
- `node --check script.js`
- `.venv\Scripts\python.exe -m py_compile main.py database.py graph.py agent_commands.py tests\test_security_regressions.py`
- `.venv\Scripts\python.exe -m unittest discover -s tests`
- `.venv\Scripts\python.exe -c "import main; print('app import ok')"`

### 2026-05-01: 좌측 패널 상하 분리와 65:35 스플리터 적용

변경 파일:
- `index.html`
- `styles.css`
- `script.js`
- `README.md`

작업 내용:
- 좌측 영역을 우측 패널 구성과 같은 방식의 독립 패널 2개로 분리했습니다.
- 상단은 고객 리스트 패널, 하단은 고객 상세 정보 패널로 구성했습니다.
- 두 패널 사이에 상하 스플리터를 추가하고 기본 비율을 65:35로 지정했습니다.
- 스플리터는 마우스 드래그와 키보드 위/아래 방향키 조절을 지원합니다.
- 상세 정보 패널 헤더와 본문을 분리해 다른 패널과 같은 타이틀 구분 구조로 맞췄습니다.

검증:
- `node --check script.js`
- `.venv\Scripts\python.exe -c "import main; print('app import ok')"`

### 2026-05-01: favicon 요청 404 로그 제거

변경 파일:
- `main.py`
- `README.md`

작업 내용:
- 브라우저가 자동 요청하는 `/favicon.ico`가 404로 기록되지 않도록 정적 asset 라우트에 `favicon.ico`를 추가했습니다.
- 별도 아이콘 파일을 만들지 않고 기존 `fingerai_logo.png`를 favicon 응답으로 매핑했습니다.
- favicon 응답에는 `image/png` 미디어 타입과 1일 캐시 헤더를 지정했습니다.

검증:
- `.venv\Scripts\python.exe -m py_compile main.py`
- `.venv\Scripts\python.exe -c "import main; print('app import ok')"`

### 2026-05-01: 에이전트 화면 리스트 DB 조회 명령 추가

변경 파일:
- `agent_commands.py`
- `main.py`
- `script.js`
- `docs/AGENT_COMMANDS.md`
- `docs/PROJECT_GUIDE.md`
- `README.md`
- `tests/test_security_regressions.py`

작업 내용:
- `business_record_list_query` command case를 추가했습니다.
- "고객 리스트", "파이프라인 리스트", "캘린더/영업활동 리스트", "견적 리스트", "계약 리스트" 표현을 일반 LLM 답변이 아니라 DB 조회 명령으로 라우팅합니다.
- "고객 리스트 중에서 직위가 팀장인 고객 리스트 알려줘" 같은 요청에서 `직위=팀장` 조건을 추출해 현재 로그인 사용자의 고객 DB를 기준으로 필터링합니다.
- 리스트 조회는 현재 세션의 `tenant_id`, `user_id`, `deleted_at IS NULL` 범위를 지킵니다.
- 채팅 응답에는 `db_list_query`, `target_menu`, `count`, `records`를 포함하고, 프론트는 해당 메뉴를 자동으로 열어 조회 화면을 함께 보여줍니다.

검증:
- `.venv\Scripts\python.exe -m py_compile main.py database.py graph.py agent_commands.py tests\test_security_regressions.py`
- `.venv\Scripts\python.exe -m unittest discover -s tests`
- `node --check script.js`

### 2026-05-01: 에이전트 대화 명령 레지스트리 도입

변경 파일:
- `agent_commands.py`
- `main.py`
- `docs/AGENT_COMMANDS.md`
- `docs/PROJECT_GUIDE.md`
- `README.md`
- `tests/test_security_regressions.py`

작업 내용:
- 에이전트 대화창에서 처리되는 업무 명령을 `AgentCommandCase` 단위로 관리하는 `agent_commands.py`를 추가했습니다.
- `/api/chat`은 메시지를 먼저 `route_agent_command()`로 분류한 뒤 SNS 프로필 리서치, 영업활동 일정 관리, 일반 LLM 대화로 분기합니다.
- command case에는 `case_id`, 우선순위, matcher, 고객 선확인 필요 여부, 처리 플로우, 테스트 포인트를 함께 기록합니다.
- `/api/agent/command-cases` API를 추가해 현재 등록된 대화 명령 케이스와 플로우를 조회할 수 있게 했습니다.
- 라우팅 결과를 `audit_logs`에 `route / agent_command`로 기록해 어떤 대화 명령이 사용되는지 추적할 수 있게 했습니다.
- 신규 대화 명령 추가 절차와 충돌 방지 기준을 `docs/AGENT_COMMANDS.md`에 문서화했습니다.

검증:
- `.venv\Scripts\python.exe -m py_compile main.py database.py graph.py agent_commands.py tests\test_security_regressions.py`
- `.venv\Scripts\python.exe -m unittest discover -s tests`
- `node --check script.js`

### 2026-05-01: DB/시스템 에러 응답 코드와 예외 처리 강화

변경 파일:
- `main.py`
- `script.js`
- `login.html`
- `tests/test_security_regressions.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 모든 요청에 `X-Request-ID`를 부여하고 에러 응답에도 `request_id`를 포함하도록 했습니다.
- 공통 에러 응답 형식을 `success=false`, `message`, `error`, `error_code`, `request_id`, `details`로 정리했습니다.
- FastAPI HTTP 예외, 입력 검증 오류, MySQL 오류, 미처리 시스템 오류에 대한 전역 exception handler를 추가했습니다.
- MySQL 오류는 중복 키, 참조 무결성, 연결 실패, 잠금/데드락/타임아웃, 일반 DB 오류로 분류해 `FSI-DB-*` 에러코드와 상황 설명을 반환합니다.
- 각 API 내부에서 잡는 DB 오류도 공통 DB 에러 응답을 사용하도록 보강했습니다.
- 메인 화면과 로그인 화면은 서버가 내려준 `error_code`, `request_id`, DB 오류번호, 상황 설명을 사용자 메시지에 포함합니다.
- 감사 로그의 `request_id` 컬럼에 실제 요청 ID를 기록하도록 변경했습니다.

검증:
- `.venv\Scripts\python.exe -m py_compile main.py database.py graph.py tests\test_security_regressions.py`
- `.venv\Scripts\python.exe -m unittest discover -s tests`
- `node --check script.js`
- `.venv\Scripts\python.exe -c "import main; print('app import ok')"`
- FastAPI TestClient로 인증 없는 `/api/customers` 요청이 `FSI-AUTH-REQUIRED`와 `request_id`를 반환하는지 확인

### 2026-05-01: 드래그앤드롭 파일 중복 첨부 방지

변경 파일:
- `script.js`
- `README.md`

작업 내용:
- 대화창에 파일을 드래그앤드롭할 때 `chat-panel`, `chat-stream`, `chat-input`의 drop 이벤트가 중첩 처리되어 같은 파일이 두 번 첨부될 수 있는 문제를 보완했습니다.
- drag/drop 이벤트에서 `stopPropagation()`을 적용해 한 번의 드롭이 한 번만 처리되도록 했습니다.
- 같은 파일이 다시 들어와도 `name`, `size`, `lastModified` 기준으로 중복 첨부를 건너뛰도록 `addFiles()`에 중복 방지 로직을 추가했습니다.

검증:
- `node --check script.js`

### 2026-05-01: 문서 업로드 기반 견적/계약 자동 저장

변경 파일:
- `.gitignore`
- `.env.example`
- `database.py`
- `main.py`
- `script.js`
- `styles.css`
- `tests/test_security_regressions.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- Word, Excel, PDF, CSV, TXT 파일을 에이전트 입력창에 첨부하면 문서 분석 API(`/api/extract/document`)로 처리하도록 했습니다.
- 문서 텍스트를 추출하고 견적서/계약서 여부를 분류해 견적서는 `quotes`, 계약서는 `contracts`에 저장합니다.
- 저장에 필요한 `accounts`, `opportunities`, `pipeline_stages` 연결 데이터를 현재 로그인 사용자의 테넌트/사용자 범위 안에서 생성 또는 보강합니다.
- 원본 파일은 `uploads/documents/{tenant_id}/{user_id}` 아래에 저장하고, `uploaded_documents` 테이블에 파일 링크 메타데이터와 추출 결과를 기록합니다.
- 견적/계약 목록 API가 연결 문서의 `document_url`을 반환하고, 상세 패널에서 원본 파일 다운로드 링크를 표시합니다.
- 저장 완료 후 프론트가 견적 또는 계약 메뉴를 자동으로 열어 저장된 데이터를 보여줍니다.

검증:
- `uv run python -m py_compile main.py database.py graph.py tests\test_security_regressions.py`
- `uv run python -m unittest discover -s tests`
- `node --check script.js`
- `uv run python -c "from database import init_db; init_db(); print('db init ok')"`
- FastAPI TestClient로 텍스트 견적 문서 업로드, `quotes` 저장, `uploaded_documents` 링크 생성 확인 후 테스트 데이터 soft delete

### 2026-05-01: 에이전트 명령창 줄바꿈과 고객 선확인 흐름

변경 파일:
- `index.html`
- `styles.css`
- `script.js`
- `main.py`
- `tests/test_security_regressions.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 에이전트 명령 입력창을 단일 input에서 textarea로 변경했습니다.
- Enter는 명령 전송, Shift+Enter는 줄바꿈으로 동작하도록 키 처리를 추가했습니다.
- `/api/chat` 시작 단계에서 메시지에 포함된 회사명 또는 고객명을 현재 로그인 사용자의 고객 DB에서 먼저 조회하도록 공통 전처리를 추가했습니다.
- 고객 후보가 1건이면 자동으로 선택 고객 컨텍스트에 주입하고, 여러 건이면 프론트에 후보 선택 UI를 표시한 뒤 같은 명령을 이어서 처리합니다.
- 자동 선택된 고객은 프론트의 선택 고객/상세 패널에도 반영합니다.
- 고객 후보 조회는 로그인 세션의 `tenant_id`, `user_id(owner_user_id)` 범위와 soft delete 조건을 따르는 기존 고객 조회 함수를 재사용합니다.

검증:
- `uv run python -m py_compile main.py database.py graph.py tests\test_security_regressions.py`
- `uv run python -m unittest discover -s tests`
- `node --check script.js`

### 2026-05-01: DB CRUD 감사 로그와 soft delete 정책 강화

변경 파일:
- `database.py`
- `main.py`
- `tests/test_security_regressions.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 앱 시작 시 모든 기본 테이블에 `deleted_at` 컬럼이 있는지 확인하고, 누락된 테이블에는 `deleted_at DATETIME(6) NULL COMMENT '소프트 삭제 일시'`를 자동 추가하도록 했습니다.
- 현재 로컬 MySQL 스키마에 `init_db()`를 실행해 `ai_outputs`, `ai_tasks`, `audit_logs`, `meeting_participants`, `refresh_tokens`, `tenant_settings` 등 누락 테이블의 `deleted_at` 컬럼을 보강했습니다.
- 고객 생성/수정 로직에서 `accounts`, `contacts` 테이블 단위 create/update 감사 로그를 남기도록 했습니다.
- 고객 삭제 로직에서 `contacts` soft delete와 동시에 테이블 단위 delete 감사 로그를 남기도록 했습니다.
- 회원가입 시 신규 `tenants`, `users` 생성도 `audit_logs`에 기록하도록 했습니다.
- 회귀 테스트에 `DELETE FROM` 하드 삭제 SQL 금지 검사를 추가했습니다.

검증:
- `node --check script.js` 통과
- `node --check admin.js` 통과
- `uv run python -m py_compile main.py database.py graph.py tests/test_security_regressions.py` 통과
- `uv run python -m unittest discover -s tests` 통과
- `uv run python -c "from database import init_db; init_db(); print('db init ok')"` 통과
- INFORMATION_SCHEMA 기준 `deleted_at` 누락 테이블 0건 확인

### 2026-05-01: 영업활동 일정 관리 명령 확장

변경 파일:
- `main.py`
- `script.js`
- `tests/test_security_regressions.py`
- `.env.example`
- `README.md`

작업 내용:
- 에이전트 채팅에서 영업활동 일정 취소, 날짜/시간 변경, 반복 일정 등록, 예정 일정 조회를 처리하도록 확장했습니다.
- 일정 취소는 대상 `activities` 행의 `status`를 `cancelled`로 변경합니다.
- 날짜/시간 변경은 대상 `activities.due_at`을 새 일정으로 업데이트합니다.
- 반복 일정은 `매일`, `매주`, `매월` 규칙과 `N회` 횟수를 파싱해 여러 개의 `activities` 행으로 저장합니다.
- 반복 생성 개수는 `MAX_RECURRING_ACTIVITY_COUNT` 환경 변수로 제한하며 기본값은 `24`입니다.
- 일정 변경/취소 후에도 캘린더 메뉴를 자동으로 열어 반영된 월을 보여주도록 프론트 메시지를 일반화했습니다.
- 한국어 날짜 파서가 `일정`의 `일`을 요일로 오인하거나 `2회`를 `2분`으로 오인하지 않도록 보강했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py tests/test_security_regressions.py` 통과
- `uv run python -m unittest discover -s tests` 통과
- FastAPI TestClient로 반복 등록, 날짜 변경, 취소를 실제 DB에서 확인 후 테스트 활동 soft delete

### 2026-05-01: 에이전트 채팅 기반 영업활동 일정 등록

변경 파일:
- `main.py`
- `script.js`
- `tests/test_security_regressions.py`
- `.env.example`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 채팅 메시지에서 영업활동 일정 등록 의도를 감지하는 서버 로직을 추가했습니다.
- 선택 고객 또는 메시지에 포함된 회사명/고객명을 기준으로 로그인 사용자의 기존 고객을 찾아 `activities`에 저장합니다.
- 저장되는 활동은 `status='planned'`이며, 메시지에 따라 `call`, `email`, `visit`, `demo`, `task` 타입을 자동 선택합니다.
- 날짜/시간 파싱은 오늘/내일/모레, `YYYY-MM-DD`, `M월 D일`, 이번/다음 주 요일, 오전/오후 시간 표현을 지원합니다.
- 일정 저장이 완료되면 에이전트가 저장 완료 메시지를 답변하고, 프론트가 캘린더 메뉴를 자동으로 열어 저장된 월을 보여줍니다.
- 저장 이벤트는 `audit_logs`에 `activity` create로 기록됩니다.
- 날짜 파싱 기준 시간대는 `APP_TIMEZONE`으로 설정하며 기본값은 `Asia/Seoul`입니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py tests/test_security_regressions.py` 통과
- `uv run python -m unittest discover -s tests` 통과
- FastAPI TestClient로 선택 고객 컨텍스트 기반 `/api/chat` 일정 저장, `/api/calendar` 표시 확인 후 테스트 활동 soft delete

### 2026-05-01: 메인 메뉴별 조회 화면 구현

변경 파일:
- `main.py`
- `index.html`
- `script.js`
- `styles.css`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 메인 메뉴 버튼에 `data-menu` 식별자를 추가해 메뉴별 화면 전환 기준을 명확히 했습니다.
- 고객 메뉴에 회사명/고객명 조건 조회 폼을 추가하고 `/api/customers`에 `company_name`, `contact_name` 조건을 반영했습니다.
- 파이프라인 메뉴에 영업기회명/상태/회사명 조건 조회 화면을 추가하고 `/api/opportunities` API를 구현했습니다.
- 캘린더 메뉴를 구글 캘린더와 유사한 월간 그리드 UI로 구성하고 `/api/calendar?year=&month=` API를 구현했습니다.
- 캘린더 데이터는 `meetings`, `activities`, `action_items`를 월 범위로 합쳐 표시합니다.
- 견적 메뉴에 회사명/고객명 조건 조회 화면을 추가하고 `/api/quotes` API를 구현했습니다.
- 계약 메뉴에 회사명/고객명 조건 조회 화면을 추가하고 `/api/contracts` API를 구현했습니다.
- 각 목록 행 또는 캘린더 이벤트를 클릭하면 하단 상세 패널에 선택 항목의 상세 정보를 표시합니다.
- 모든 신규 조회 API는 로그인 세션의 `tenant_id`와 사용자 ID 기준으로 범위를 제한하고 `audit_logs`에 조회 로그를 남깁니다.
- 메인 우측 실행 플랜/추론 로그/스케줄러 패널 사이 간격을 `10px`로 조정했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py tests/test_security_regressions.py` 통과
- FastAPI TestClient로 `finger / james@crm.co.kr` 로그인 후 `/api/customers`, `/api/opportunities`, `/api/calendar`, `/api/quotes`, `/api/contracts` 응답 확인

### 2026-05-01: 관리자 CRUD와 사용로그 보강

변경 파일:
- `main.py`
- `admin.js`
- `styles.css`
- `tests/test_security_regressions.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 사용자 관리 화면에 삭제 버튼을 추가하고 `DELETE /api/admin/users/{user_id}` API를 구현했습니다.
- 사용자 삭제는 실제 행 삭제가 아니라 `status='disabled'`, `team_id=NULL`, `deleted_at=NOW(6)` 기반 soft delete로 처리합니다.
- 본인 계정 삭제는 서버에서 차단해 관리자 세션을 스스로 끊어버리는 실수를 막았습니다.
- 관리자 조회 화면, 고객 목록/상세/생성/수정/삭제, 명함 인식, SNS 링크 확인, 에이전트 질문, 로그인/로그아웃을 `audit_logs`에 기록하도록 보강했습니다.
- 사용로그 기록 실패가 실제 사용자 업무 흐름을 중단하지 않도록 `record_audit_event()`는 예외를 흡수하고 서버 콘솔에만 남깁니다.
- 관리자 사용로그 화면은 기존 `audit_logs` 테이블을 그대로 조회하되, 이제 운영 행동 로그까지 함께 확인할 수 있습니다.

검증:
- `node --check admin.js` 통과
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py tests/test_security_regressions.py` 통과
- `uv run python -m unittest discover -s tests` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
- FastAPI TestClient로 `finger / james@crm.co.kr` 로그인 후 `/settings/users`, `/settings/teams`, `/settings/pipeline`, `/api/admin/users`, `/api/admin/logs` 응답 확인

### 2026-05-01: 설정 라우트 기반 관리자 기능 확장

변경 파일:
- `main.py`
- `admin.js`
- `styles.css`
- `tests/test_security_regressions.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- `/settings/users`, `/settings/teams`, `/settings/pipeline` 라우트를 추가해 관리자 세부 화면으로 직접 진입할 수 있게 했습니다.
- 관리자 메뉴 클릭 시 해당 설정 라우트로 브라우저 history를 갱신하도록 변경했습니다.
- 사용자 관리에 사용자 초대 기능을 추가했습니다.
- `POST /api/admin/users/invite`는 초대 사용자를 `invited` 상태로 만들고 임시 비밀번호를 반환합니다.
- 기존 사용자 관리 목록에서 역할 변경, 팀 배정, 상태 변경을 계속 지원합니다.
- 팀 관리에서 팀장 지정과 팀원 다중 배정을 지원하도록 확장했습니다.
- 현재 `teams` 테이블에 팀장 컬럼이 없으므로 팀장 지정은 `tenant_settings.setting_key = team_leaders` JSON 매핑으로 저장합니다.
- 팀원 배정은 기존 `users.team_id`를 사용합니다.
- 영업 단계 설정에 기본 단계 생성 버튼과 `POST /api/admin/pipeline-stages/defaults` API를 추가했습니다.
- 기본 단계는 `lead`, `prospect`, `opportunity`, `proposal`, `contract`, `success`이며 이미 존재하는 단계는 중복 생성하지 않습니다.

검증:
- `node --check admin.js` 통과
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py tests/test_security_regressions.py` 통과
- `uv run python -m unittest discover -s tests` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
- FastAPI TestClient로 `finger / james@crm.co.kr` 로그인 후 `/settings/users`, `/settings/teams`, `/settings/pipeline`, `/api/admin/users`, `/api/admin/teams`, `/api/admin/pipeline-stages` 응답 확인

### 2026-05-01: 관리자 코드 관리 메뉴 추가

변경 파일:
- `main.py`
- `admin.html`
- `admin.js`
- `styles.css`
- `tests/test_security_regressions.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 관리자 사이드 메뉴에 `코드 관리`를 추가했습니다.
- 전용 코드 테이블이 아직 없으므로 기존 `tenant_settings`의 JSON 설정값을 사용해 `custom_codes`를 저장하도록 구현했습니다.
- `GET /api/admin/codes`, `PUT /api/admin/codes` API를 추가했습니다.
- 코드 그룹은 `group_code`, `name`, `description`, `sort_order`, `is_active`, `items` 구조로 관리합니다.
- 코드 항목은 `code`, `name`, `description`, `sort_order`, `is_active` 구조로 관리합니다.
- 코드/그룹 코드는 영문/숫자/언더스코어/하이픈 기반 토큰으로 정규화하고 중복을 서버에서 차단합니다.
- 코드 변경 작업은 `audit_logs`에 `custom_codes` 대상으로 기록합니다.
- 관리자 요약 카드에 코드 항목 수를 표시하도록 변경했습니다.

검증:
- `node --check admin.js` 통과
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py tests/test_security_regressions.py` 통과
- `uv run python -m unittest discover -s tests` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
- FastAPI TestClient로 `finger / james@crm.co.kr` 로그인 후 `/admin`, `/api/admin/summary`, `/api/admin/codes` 응답 확인

### 2026-05-01: 관리자 페이지 및 관리 API 추가

변경 파일:
- `main.py`
- `index.html`
- `admin.html`
- `admin.js`
- `script.js`
- `styles.css`
- `tests/test_security_regressions.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 우측 상단 도구 버튼을 `/admin` 관리자 페이지로 연결했습니다.
- `/admin`은 별도 관리자 화면이며 `owner`, `admin` 역할만 접근할 수 있습니다.
- 일반 사용자에게는 상단 도구 버튼을 숨기고, 서버 라우트/API에서도 관리자 권한을 다시 확인합니다.
- 관리자 사이드 메뉴를 `회사 정보`, `사용자 관리`, `팀 관리`, `권한 관리`, `영업 단계 설정`, `사용로그`로 구성했습니다.
- 회사 정보는 `tenants`, `tenant_settings`를 조회하고 `tenants` 기본 정보를 수정합니다.
- 사용자 관리는 `users`와 `teams`를 기준으로 사용자 이름, 전화번호, 팀, 역할, 상태를 수정합니다.
- 사용자 조회/감사 로그에는 `password_hash`를 포함하지 않도록 제한했습니다.
- 팀 관리는 `teams` 기준 목록, 추가, 수정, soft delete를 지원합니다.
- 권한 관리는 현재 `users.role` enum과 서버 역할 정의를 기준으로 역할별 설명과 사용자 수를 보여줍니다.
- 영업 단계 설정은 `pipeline_stages` 기준 목록, 추가, 수정, soft delete를 지원합니다.
- 사용로그는 `audit_logs` 기준으로 관리자 변경 이력을 조회합니다.
- 관리자 변경 작업은 `audit_logs`에 create/update/delete 행위로 기록합니다.

검증:
- `node --check admin.js` 통과
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py tests/test_security_regressions.py` 통과
- `uv run python -m unittest discover -s tests` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
- FastAPI TestClient로 `finger / james@crm.co.kr` 로그인 후 `/api/admin/summary`, `/api/admin/users` 응답 확인
- FastAPI TestClient로 `/admin`, `/admin.js`, `/styles.css` 응답 확인

### 2026-04-30: MySQL 연결 및 고객 CRUD 1차 구현

변경 파일:
- `database.py`
- `main.py`
- `script.js`
- `requirements.txt`
- `.env.example`
- `.env`

작업 내용:
- MySQL 연결 모듈을 추가했습니다.
- 처음에는 단일 `customers` 테이블 CRUD로 구현했습니다.
- 명함 추출 결과를 DB에 저장하고 화면 진입 시 고객 목록을 불러오도록 연결했습니다.
- `mysql-connector-python` 의존성을 추가했습니다.

후속 변경:
- 사용자 요구에 따라 단일 `customers` 테이블 방식은 폐기하고 `accounts`/`contacts` 분리 저장으로 변경했습니다.

### 2026-04-30: accounts/contacts 분리 저장 구조 적용

변경 파일:
- `database.py`
- `main.py`
- `script.js`
- `.env.example`
- `.env`

작업 내용:
- 실제 DB 스키마와 테이블 주석을 조회했습니다.
- 실제 테이블명이 `accounts`임을 확인했습니다.
- `accounts`는 고객사, `contacts`는 연락처로 매핑했습니다.
- 같은 테넌트 안에서 같은 회사명이 있으면 `accounts`는 insert하지 않고 update하도록 변경했습니다.
- 명함 입력마다 `contacts`에는 새 행을 추가하도록 변경했습니다.
- 고객 조회 API는 `contacts`와 `accounts`를 join해서 프론트가 기존 그리드 형식으로 사용할 수 있게 반환합니다.
- 삭제 API는 물리 삭제 대신 `contacts.deleted_at` 갱신으로 변경했습니다.

검증:
- Python 문법 검사 통과
- MySQL 연결 및 필수 테이블 확인 통과
- `script.js` 문법 검사 통과

### 2026-04-30: uv 실행 의존성 정리

변경 파일:
- `pyproject.toml`
- `requirements.txt`

작업 내용:
- `uv run main.py` 실행 시 `mysql.connector` 모듈을 찾지 못하는 문제가 발생했습니다.
- `requirements.txt`만으로는 `uv run`이 프로젝트 의존성을 자동 인식하지 않아 `pyproject.toml`을 추가했습니다.
- `mysql-connector-python`을 프로젝트 dependencies에 포함했습니다.

검증:
- `uv run python -c "import mysql.connector; print('mysql connector ok')"` 통과
- Python 문법 검사 통과

### 2026-04-30: 고객 메뉴 재조회 및 상세 패널 개선

변경 파일:
- `script.js`

작업 내용:
- 앱 시작 시 고객 목록을 DB에서 조회합니다.
- 상단 고객 메뉴 클릭 시 `/api/customers`를 다시 호출해 최신 DB 정보를 표시합니다.
- 고객 그리드 행 클릭 시 하단 상세 영역에 DB 기준 상세 정보를 표시하도록 개선했습니다.
- 상세 정보에 `tenant_id`, `account_id`, `contact_id`를 포함했습니다.

검증:
- `node --check script.js` 통과
- Python 문법 검사 통과

### 2026-04-30: 멀티테넌트 로그인, 세션, 로그아웃 구현

변경 파일:
- `main.py`
- `database.py`
- `login.html`
- `index.html`
- `script.js`
- `styles.css`
- `requirements.txt`
- `pyproject.toml`
- `.env.example`

작업 내용:
- `tenants`와 `users` 테이블 스키마와 주석을 확인했습니다.
- `login.html`을 테넌트 코드, 이메일, 비밀번호 기반 로그인 화면으로 변경했습니다.
- `/api/auth/login`, `/api/auth/me`, `/api/auth/logout` API를 추가했습니다.
- 로그인 성공 시 HTTP-only 세션 쿠키 `fsai_session`을 발급합니다.
- 세션 토큰은 `APP_SESSION_SECRET`으로 HMAC 서명합니다.
- `users.password_hash`의 bcrypt 형식을 확인하고 bcrypt 검증을 추가했습니다.
- 상단에 로그인한 사용자 이름, 역할, 테넌트 이름을 표시합니다.
- 로그아웃 버튼을 구현하고 로그아웃 후 `/login.html`로 이동하도록 했습니다.
- 고객 조회, 명함 저장, 고객 생성/수정/삭제, 채팅 API가 로그인 세션의 `tenant_id`를 사용하도록 변경했습니다.
- 명함 저장 시 `owner_user_id`는 로그인한 사용자 ID로 저장합니다.
- 세션이 없는 상태에서 `/`에 접근하면 `/login.html`로 리다이렉트합니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과

### 2026-04-30: 고객 패널 조회 범위에 로그인 사용자 ID 적용

변경 파일:
- `main.py`
- `database.py`
- `script.js`
- `README.md`

작업 내용:
- 고객 목록 조회가 기존에는 로그인 세션의 `tenant_id`만 사용하던 것을 확인했습니다.
- `/api/customers` 조회 조건에 `contacts.owner_user_id = 로그인 user_id`를 추가했습니다.
- 고객 상세 조회, 수정, 삭제도 `tenant_id`와 `owner_user_id`를 함께 확인하도록 변경했습니다.
- 명함 저장과 고객 생성/수정은 기존처럼 로그인 세션의 `user_id`를 `contacts.owner_user_id`에 저장합니다.
- 고객 상세 패널에 사용자 ID를 표시하도록 추가했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과

### 2026-04-30: 로그아웃 세션 쿠키 삭제 보강

변경 파일:
- `main.py`
- `index.html`
- `script.js`
- `README.md`

작업 내용:
- 우측 상단 로그아웃 컨트롤을 JS 전용 버튼에서 `/logout` 링크로 변경했습니다.
- JS가 실행되지 않거나 캐시 타이밍이 꼬여도 링크 자체로 로그아웃 라우트에 접근할 수 있습니다.
- 서버의 세션 쿠키 삭제 로직을 `clear_session_cookie` 함수로 분리했습니다.
- `/api/auth/logout`과 `/logout` 모두 동일한 세션 삭제 함수를 사용합니다.
- 기존 쿠키 옵션 차이로 삭제가 실패할 가능성을 줄이기 위해 복수의 만료 `Set-Cookie` 헤더를 내려보내도록 보강했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과

### 2026-04-30: 로그인 세션 표시 및 고객 조회 쿠키 전달 보강

변경 파일:
- `main.py`
- `script.js`
- `login.html`
- `README.md`

작업 내용:
- `finger / james@crm.co.kr` 계정으로 서버 내부 로그인 재현을 수행했습니다.
- 서버에서는 `/api/auth/login`, `/api/auth/me`, `/api/customers`가 정상 응답하는 것을 확인했습니다.
- 브라우저에서 상단 라벨이 기본값인 `사용자`로 남는 문제를 줄이기 위해 `/` HTML 응답에 서버가 검증한 세션을 `window.__FSAI_SESSION__`으로 주입하도록 변경했습니다.
- 프론트는 `window.__FSAI_SESSION__`이 있으면 즉시 상단 라벨을 갱신한 뒤 `/api/auth/me`로 최신 세션을 다시 확인합니다.
- API 호출에서 쿠키 전달이 명확하도록 `fetch`에 `credentials: "same-origin"`을 명시했습니다.
- 로그인 쿠키 발급 시 `path="/"`를 명시했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과

### 2026-04-30: 선택 고객 기반 에이전트 답변 우선순위 적용

변경 파일:
- `script.js`
- `main.py`
- `README.md`

작업 내용:
- 고객 그리드에서 선택된 행을 `memory.selectedCustomer`에 별도 저장하도록 변경했습니다.
- 채팅 요청 컨텍스트에 `selectedCustomer`를 포함하도록 변경했습니다.
- 서버의 `build_chat_context`가 `selected_customer_highest_priority` 필드를 생성하도록 변경했습니다.
- 시스템 프롬프트와 컨텍스트 규칙에 선택 고객이 있으면 최신 등록 고객보다 선택 고객을 우선하도록 명시했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과

### 2026-05-01: 프로젝트 공통 가이드 및 인수인계 문서 추가

변경 파일:
- `README.md`
- `docs/PROJECT_GUIDE.md`
- `docs/HANDOFF_WORKFLOW.md`

작업 내용:
- Windows 데스크탑과 MacBook에서 작업 흐름이 끊기지 않도록 공통 문서 구조를 추가했습니다.
- 다른 팀원과 다른 Codex 세션이 읽고 같은 기준으로 작업할 수 있도록 프로젝트 가이드를 작성했습니다.
- 프레임워크, DB 구성, 메뉴 구성, 각 메뉴별 상세 로직, 공통 코드, 보안 및 역할, 협업 워크플로우를 문서화했습니다.
- 장비 이동, 팀원별 작업 분리, 검증 명령, 변경 이력 작성 템플릿을 문서화했습니다.
- README 상단에 공통 문서 인덱스를 추가했습니다.

검증:
- `docs/PROJECT_GUIDE.md` 생성 및 핵심 섹션 확인
- `docs/HANDOFF_WORKFLOW.md` 생성 및 핵심 섹션 확인
- README 문서 인덱스와 2026-05-01 변경 이력 확인

### 2026-05-01: private Git 저장소 준비

변경 파일:
- `.gitignore`
- `database.py`
- `.env.example`
- `docs/HANDOFF_WORKFLOW.md`
- `README.md`

작업 내용:
- Windows 환경에 Git을 설치했습니다.
- 프로젝트 폴더를 로컬 Git 저장소로 초기화했습니다.
- 기본 브랜치를 `main`으로 만들었습니다.
- `.env`, `.venv`, `.uv-cache`, `.uv-python`, `__pycache__`, 로그 파일, DB dump 파일이 Git에 올라가지 않도록 `.gitignore`를 추가했습니다.
- `.env.example`에서 실제 DB 비밀번호 값을 제거하고 예시 값으로 변경했습니다.
- `database.py`의 DB 비밀번호 기본값에서 실제 비밀번호를 제거했습니다.
- 커밋 작성자 정보는 개인 이메일 노출을 피하기 위해 로컬 저장소에 `FingerSalesAI Codex <codex@example.local>`로 설정했습니다.
- 첫 로컬 커밋을 생성했습니다.
- 원격 private 저장소 연결 절차를 `docs/HANDOFF_WORKFLOW.md`에 기록했습니다.

검증:
- `git status --ignored --short`로 민감/로컬 파일 제외 확인
- `git check-ignore`로 `.env`, 가상환경, 캐시, 로그 제외 확인
- 커밋 대상 파일에서 실제 API 키/DB 비밀번호가 추적되지 않는지 확인
- 첫 커밋 생성 완료

남은 작업:
- 원격 저장소 연결 완료: `https://github.com/heechoi7/FingerSalesAI.git`
- `main` 브랜치가 `origin/main`을 추적하도록 설정 완료
- 최초 push 완료

### 2026-05-01: GitHub 원격 저장소 연결 및 push

변경 파일:
- `README.md`
- `docs/HANDOFF_WORKFLOW.md`

작업 내용:
- GitHub 저장소 `https://github.com/heechoi7/FingerSalesAI.git`를 `origin`으로 추가했습니다.
- Git의 dubious ownership 경고를 해결하기 위해 이 프로젝트 폴더를 safe.directory로 등록했습니다.
- 로컬 `main` 브랜치를 `origin/main`에 push했습니다.
- MacBook에서 clone할 수 있도록 원격 저장소 정보를 문서화했습니다.

검증:
- `git push -u origin main` 성공

### 2026-05-01: 제품 정의를 AI 세일즈 클라우드 방향으로 재정의

변경 파일:
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- FingerSalesAI를 단순히 AI 기능이 붙은 CRM이 아니라 세일즈 에이전트 클라우드로 정의했습니다.
- 핵심 문장을 "영업사원이 입력하지 않아도, AI가 고객, 활동, 일정, 제안, 팔로업을 정리하고 다음 행동을 제안하는 AI 세일즈 클라우드"로 문서화했습니다.
- 핵심 가치를 `Zero Input CRM`, `Conversational Sales Agent`, `Sales Intelligence`로 정리했습니다.
- 명함 인식/고객 등록은 첫 진입 기능이며, 최종 방향은 명함, 미팅, 이메일, 일정, 견적, 계약 데이터를 AI가 읽고 영업사원이 대화로 일하는 구조임을 명시했습니다.
- 앞으로의 개발 판단 기준을 사용자 입력 최소화, AI의 선제 정리/제안/실행, 멀티테넌트 클라우드 안정성으로 정리했습니다.
- 남은 작업 후보에 AI 입력 채널 확장, 다음 행동 추천, 대화형 영업 에이전트, Sales Intelligence 데이터 모델 확장을 추가했습니다.

검증:
- 문서 변경으로 코드 실행 검증은 필요하지 않습니다.

### 2026-05-01: 우측 실행 패널 표시 밀도 개선

변경 파일:
- `styles.css`
- `README.md`

작업 내용:
- 우측 상단 실행 플랜의 카드 패딩, 카드 간격, 설명 문구 여백, 상태 텍스트 크기, 진행바 높이를 줄였습니다.
- 명함/대화 실행 플랜의 이미지 미리보기 최대 높이를 줄여 플랜 항목이 더 많이 보이도록 했습니다.
- 중간 추론 로그의 행 패딩, 시간 컬럼 폭, 행 간격, 폰트 크기, 상태 점 위치를 줄였습니다.
- 하단 스케줄러의 행 패딩, 시간 컬럼 폭, 행 간격, 폰트 크기를 줄였습니다.
- 변경 범위를 우측 패널 계열 스타일에 맞춰 적용해 고객 그리드나 채팅 메시지 레이아웃에는 영향을 최소화했습니다.

검증:
- CSS/문서 변경으로 별도 코드 실행 검증은 필요하지 않습니다.

### 2026-05-01: 고객 패널 모눈 배경 제거

변경 파일:
- `styles.css`
- `README.md`

작업 내용:
- 고객 그리드 바깥 캔버스 영역의 모눈종이 형태 `linear-gradient` 배경을 제거했습니다.
- 캔버스 영역 배경을 다른 패널과 같은 단색 `surface` 배경으로 변경했습니다.

검증:
- CSS/문서 변경으로 별도 코드 실행 검증은 필요하지 않습니다.

### 2026-05-01: 우측 패널 타이틀 구분선 통일

변경 파일:
- `styles.css`
- `README.md`

작업 내용:
- 실행 플랜, 추론 로그, 스케줄러 패널의 타이틀 영역을 고객 패널/에이전트 패널의 헤더와 같은 패딩과 하단 구분선 구조로 맞췄습니다.
- 우측 패널의 본문 리스트 밀도는 기존 컴팩트 스타일을 유지했습니다.

검증:
- CSS/문서 변경으로 별도 코드 실행 검증은 필요하지 않습니다.

### 2026-05-01: 우측 패널 간격 미세 조정

변경 파일:
- `styles.css`
- `README.md`

작업 내용:
- 실행 플랜, 추론 로그, 스케줄러 사이의 세로 간격을 14px에서 12px로 줄였습니다.

검증:
- CSS/문서 변경으로 별도 코드 실행 검증은 필요하지 않습니다.

### 2026-05-01: 에이전트 패널 확대 시 우측 패널 유지

변경 파일:
- `styles.css`
- `README.md`

작업 내용:
- 에이전트 패널 확대 상태(`focus-chat`)에서 우측 실행 플랜, 추론 로그, 스케줄러 패널이 숨겨지지 않도록 변경했습니다.
- 에이전트 확대 시 좌측 고객 패널만 숨기고, 에이전트 패널과 우측 3개 패널을 함께 표시하는 그리드 구조로 조정했습니다.
- 우측 패널 크기 조절 splitter도 유지되도록 했습니다.

검증:
- CSS/문서 변경으로 별도 코드 실행 검증은 필요하지 않습니다.

### 2026-05-01: SNS 링크 기반 고객 등록 구현

변경 파일:
- `main.py`
- `script.js`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 에이전트 입력창에 SNS 링크를 입력하면 일반 채팅 응답 대신 SNS 고객 등록 흐름으로 분기하도록 했습니다.
- `POST /api/extract/sns` API를 추가했습니다.
- LinkedIn, Instagram, Facebook, X, YouTube, TikTok, GitHub, Naver Blog, Medium 링크를 감지하고 플랫폼별로 구분합니다.
- `https://`가 없는 `linkedin.com/in/...` 형태도 SNS 링크로 감지합니다.
- SNS 링크를 `회사명`, `이름`, `직무`, `직위`, `홈페이지`, `SNS종류`, `SNS대상`, `SNS핸들`, `SNS링크` 필드로 정규화합니다.
- 정규화된 SNS 정보는 명함 입력과 같은 `save_extracted_customer` 경로를 사용해 `accounts`는 upsert, `contacts`는 insert합니다.
- 프론트 실행 플랜에 SNS 구분, 프로필 정규화, 고객 등록 단계를 추가했습니다.
- SNS 처리 결과를 채팅창과 고객 그리드에 즉시 반영하도록 했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
- `extract_social_links` 수동 호출로 LinkedIn 개인/회사, Instagram 링크 분류 확인

### 2026-05-01: LinkedIn 서브도메인 SNS 감지 보강

변경 파일:
- `main.py`
- `script.js`
- `README.md`

작업 내용:
- LinkedIn 링크가 답변 플로우로 빠지고 고객 정보가 저장되지 않을 수 있는 원인을 확인했습니다.
- 기존 감지 규칙은 `linkedin.com`, `www.linkedin.com`, `m.linkedin.com` 중심이라 `kr.linkedin.com` 같은 지역 서브도메인을 놓칠 수 있었습니다.
- 프론트와 백엔드 SNS URL 감지 규칙을 `*.linkedin.com` 형태까지 인식하도록 확장했습니다.
- 같은 방식으로 지원 SNS의 일반 서브도메인 URL도 더 안정적으로 감지되도록 했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
- `extract_social_links` 수동 호출로 `kr.linkedin.com/in/...`, `www.linkedin.com/company/...`, `m.linkedin.com/in/...` 감지 확인

### 2026-05-01: LinkedIn 상세 브리핑 및 저장 fallback 보강

변경 파일:
- `main.py`
- `script.js`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- `https://www.linkedin.com/in/hyundohbak/?locale=ko_KR` 입력이 일반 답변으로 빠지고 DB 저장이 누락되는 문제를 재점검했습니다.
- SNS 링크 처리 시 Tavily 검색과 Gemini 정리를 사용해 이름, 회사, 직무, 직위, 이메일 후보, 요약, 영업 브리핑을 보강하도록 했습니다.
- SNS 상세 브리핑을 채팅창에도 표시하고, 고객 컨텍스트에도 기억하도록 했습니다.
- 브라우저가 예전 `script.js`를 캐시해 SNS 분기 로직을 못 쓰는 상황을 줄이기 위해 `/` 응답의 script URL에 파일 수정 시간 기반 `v` query를 붙였습니다.
- `script.js`와 `styles.css` 정적 응답에 `Cache-Control: no-cache`를 적용했습니다.
- 그래도 프론트가 일반 `/api/chat`으로 보내는 경우를 대비해, `/api/chat`도 SNS 링크를 감지하면 답변 생성 대신 SNS 브리핑/고객 저장 fallback을 수행하도록 했습니다.
- `/api/chat` fallback 결과가 내려오면 프론트 고객 그리드에도 즉시 반영하도록 했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
- `extract_social_links` 수동 호출로 `https://www.linkedin.com/in/hyundohbak/?locale=ko_KR` 감지 확인

### 2026-05-01: Facebook 공개 프로필 이름 추출 보강

변경 파일:
- `main.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- SNS 링크 처리 시 검색 결과만 보지 않고 공개 프로필 HTML의 `og:title`, `twitter:title`, `title`, `description` 메타데이터를 먼저 읽도록 했습니다.
- `박광영 | Facebook` 같은 공개 프로필 제목은 `박광영`으로 정리해 연락처 이름 후보로 사용합니다.
- 공개 메타데이터에서 확인한 이름과 검색/AI 추출 이름이 충돌하면 잘못된 회사, 직책, 이메일을 저장하지 않도록 방어했습니다.
- 공개 메타데이터 이름이 URL 핸들이 아닌 실제 이름으로 보이면 그 이름을 최우선 근거로 사용합니다.
- Facebook이 로그인 화면이나 차단 페이지를 반환하는 경우에는 해당 제목을 이름으로 쓰지 않고 기존 검색 기반 보강으로 fallback합니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
- `social_profile_name_from_metadata({'og_title': '박광영 | Facebook'}, 'Facebook')` 수동 호출로 `박광영` 추출 확인
- 공개 메타데이터 이름과 AI 결과가 충돌하는 단위 테스트에서 잘못된 회사/이메일이 제거되는 것 확인

### 2026-05-01: SNS 프로필 이름 정확도 우선 저장 정책 적용

변경 파일:
- `main.py`
- `script.js`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- SNS 개인/프로필 링크는 검색 결과나 AI 추론만으로 `이름`을 확정하지 않도록 변경했습니다.
- 공개 프로필 메타데이터에서 이름을 확정하지 못하면 `accounts`/`contacts`에 저장하지 않고 `이름 확인 필요` 결과로 응답합니다.
- 프론트는 이름 확인이 필요한 SNS 항목을 고객 그리드에 추가하지 않고, 확인 필요 사유를 채팅창에 표시합니다.
- 일반 `/api/chat` fallback으로 SNS 링크가 들어와도 저장 완료 항목만 고객 그리드에 반영합니다.
- 명함 이미지가 아니더라도 SNS 프로필 화면 캡처로 판단되고 화면에 보이는 이름이 있으면, 해당 이름을 직접 근거로 고객 저장하도록 업로드 흐름을 확장했습니다.
- SNS 프로필 화면 캡처에서도 이름이 보이지 않으면 저장하지 않습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
- 공개 메타데이터 이름이 없는 Facebook 링크 단위 테스트에서 `saved=False`, `needs_confirmation=True`, `customer=None` 확인
- 공개 메타데이터 이름이 있는 경우 `contact_name=박광영`, `name_verified=True`, 충돌한 회사/이메일 제거 확인

### 2026-05-01: SNS 결과 표시 및 LinkedIn 이름형 URL 처리 개선

변경 파일:
- `main.py`
- `script.js`
- `styles.css`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- SNS 처리 결과 카드가 명함 결과용 2열 레이아웃을 사용하면서 긴 URL과 안내 문구가 겹쳐 보이는 문제를 수정했습니다.
- SNS 결과 목록은 1열 전용 레이아웃으로 표시하고, 상태/대상/URL/사유를 줄 단위로 분리했습니다.
- Facebook/LinkedIn 공개 페이지 접근이 막히는 경우를 줄이기 위해 Facebook은 `www`, `m`, `mbasic`, LinkedIn은 `www`, `kr` 후보 URL의 공개 메타데이터를 순차 확인합니다.
- LinkedIn 개인 URL slug가 `희진-김-9b0b62278`처럼 이름 토큰 2개 이상을 포함하면 검색 결과가 아닌 URL 직접 근거로 이름을 사용할 수 있도록 보완했습니다.
- 숫자 ID, 해시성 토큰, 일반 영문 단일 핸들은 이름으로 저장하지 않습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- LinkedIn URL slug `%ED%9D%AC%EC%A7%84-%EA%B9%80-9b0b62278`에서 내부 유니코드 기준 `희진 김` 추출 확인
- 공개 메타데이터가 없어도 이름형 LinkedIn URL slug는 `name_verified=True`, `name_source=linkedin_profile_url_slug`로 처리되는 것 확인

### 2026-05-01: PR 리뷰 기반 SaaS 보안/안정성 보강

변경 파일:
- `main.py`
- `script.js`
- `.env.example`
- `tests/test_security_regressions.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 세션 쿠키 서명과 만료만 확인하던 구조를 보강해, 보호 API 요청마다 `users`와 `tenants`의 현재 상태를 DB에서 다시 확인하도록 했습니다.
- 비활성/삭제 사용자 또는 active/trial이 아닌 테넌트의 기존 세션 쿠키는 더 이상 보호 API를 통과하지 못합니다.
- `accounts` upsert 범위를 `tenant_id + owner_user_id + 회사명`으로 좁혀 같은 테넌트의 다른 사용자가 같은 회사명을 저장해도 고객사 정보가 서로 덮어쓰기 되지 않도록 했습니다.
- 공개 `/api/db/health` 응답에서 DB명, MySQL 버전, 기본 테넌트 ID 노출을 제거하고 단순 상태만 반환하도록 했습니다.
- 이미지 업로드는 `MAX_UPLOAD_BYTES` 기준으로 제한하고, 초과 시 `413`을 반환하도록 했습니다.
- SNS 링크 처리는 요청당 `MAX_SNS_LINKS_PER_REQUEST`개로 제한하고, 공개 메타데이터 fetch timeout을 `SOCIAL_FETCH_TIMEOUT_SECONDS`로 관리하도록 했습니다.
- 예외 응답은 내부 오류 문자열을 그대로 사용자에게 반환하지 않고, sanitized 메시지와 적절한 HTTP status를 반환하도록 정리했습니다.
- 프론트가 FastAPI `detail` 오류 메시지도 사용자에게 표시하도록 에러 메시지 처리를 보강했습니다.
- 세션 상태 재검증, 업로드 크기 제한, LinkedIn slug 파싱을 검증하는 `unittest` 회귀 테스트를 추가했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
- `uv run python -m unittest discover -s tests` 통과

### 2026-05-01: SNS 링크 정보 확인 단계 분리

변경 파일:
- `main.py`
- `script.js`
- `tests/test_security_regressions.py`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- SNS 링크 입력 흐름을 고객 저장 중심에서 `SNS 종류 구별 + 공개 정보 확인` 중심으로 조정했습니다.
- 신규 `POST /api/inspect/sns` API를 추가했습니다.
- inspect API는 링크를 플랫폼, 대상 유형, 핸들, 표시명, 이름 후보, 공개 메타데이터, 후보 fetch URL, 저장 가능 여부로 정리해 반환합니다.
- 프론트의 SNS 링크 입력은 `/api/extract/sns` 저장 API 대신 `/api/inspect/sns`를 호출하도록 변경했습니다.
- 채팅 fallback으로 SNS 링크가 들어와도 고객 저장 대신 SNS 정보 확인 결과를 반환하도록 변경했습니다.
- 기존 `/api/extract/sns` 저장 API는 호환용으로 유지했습니다.
- SNS 결과 UI는 “아직 고객 정보로 저장하지 않음”을 명확히 표시합니다.
- SNS 플랫폼 분류와 inspect 결과에 대한 회귀 테스트를 추가했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py tests/test_security_regressions.py` 통과
- `uv run python -m unittest discover -s tests` 통과
- `uv run python -c "import main; print('app import ok')"` 통과

### 2026-05-01: 클라우드 SaaS 운영 기준 보안/안정성 보강

변경 파일:
- `main.py`
- `database.py`
- `login.html`
- `.env.example`
- `README.md`
- `docs/PROJECT_GUIDE.md`

작업 내용:
- 운영 환경에서 짧거나 비어 있는 `APP_SESSION_SECRET`으로 서버가 시작되지 않도록 방어했습니다.
- 세션 쿠키에 `path`, `secure`, `samesite` 설정을 환경 변수 기반으로 명확히 적용했습니다.
- 보안 응답 헤더 middleware를 추가했습니다.
- production 환경에서 HSTS 헤더를 추가하도록 했습니다.
- `APP_ALLOWED_HOSTS` 설정 시 Trusted Host middleware를 적용하도록 했습니다.
- `TRUST_PROXY_HEADERS`가 켜진 경우에만 `X-Forwarded-For`를 신뢰하도록 해 프록시가 없는 환경에서 클라이언트 IP 위조 가능성을 줄였습니다.
- 로그인/회원가입 API에 IP 기반 in-memory rate limit을 추가했습니다.
- 비밀번호 최소 길이를 `MIN_PASSWORD_LENGTH` 환경 변수로 관리하고 기본 8자로 강화했습니다.
- 기존 테넌트 self-join을 기본 차단했습니다.
- 신규 테넌트 첫 사용자는 서버에서 `owner`로 생성하도록 했습니다.
- 기존 테넌트 self-join을 열 경우 가입 코드와 제한된 역할만 허용하도록 했습니다.
- DB 연결을 매 요청 신규 연결에서 MySQL connection pool 방식으로 변경했습니다.
- `database.py`가 직접 `.env`를 로드하도록 해 환경 변수 로드 순서 문제를 줄였습니다.
- 다른 로컬 프로젝트의 `.env`를 하드코딩해서 읽던 경로를 제거하고, 필요한 경우 `FSAI_EXTRA_ENV_PATH`로 명시하도록 변경했습니다.
- 회원가입 화면에 가입 코드 입력을 추가하고 역할 선택을 제한했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과

남은 작업:
- Redis 기반 rate limit으로 교체
- 운영 로그/모니터링/알림 구성
- reverse proxy의 forwarded header 신뢰 범위와 배포 설정 확정
- DB migration 도입
- 업로드 파일 크기 제한 및 스토리지 분리
- 역할별 권한 정책 세분화

### 2026-04-30: 상단 사용자 표시 중복 제거

변경 파일:
- `index.html`
- `README.md`

작업 내용:
- 우측 상단에 남아 있던 정적 `관리자 (관리자)` 텍스트를 제거했습니다.
- 예전 `/login.html` 로그아웃 링크 아이콘을 제거했습니다.
- 상단에는 로그인 세션에서 읽은 사용자 이름/역할/테넌트 라벨과 `/logout` 링크만 표시되도록 정리했습니다.

검증:
- 정적 HTML 변경으로 별도 빌드 검증은 필요하지 않습니다.

### 2026-04-30: 상단 세션 라벨 표시 형식 변경

변경 파일:
- `script.js`
- `README.md`

작업 내용:
- 우측 상단 로그인 사용자 표시를 `테넌트 이름 / 사용자 이름 / 사용자 역할 이름` 형식으로 변경했습니다.
- 역할 이름은 서버의 `role_label` 값을 사용합니다.

검증:
- `node --check script.js` 통과

### 2026-04-30: 로그아웃 안정화 및 회원가입 후 로그인 유도

변경 파일:
- `main.py`
- `script.js`
- `login.html`
- `README.md`

작업 내용:
- 상단 로그아웃 버튼이 `fetch` 호출 대신 `/logout` 전용 라우트로 이동하도록 변경했습니다.
- `/logout` 라우트는 서버에서 세션 쿠키를 삭제한 뒤 `/login.html`로 리다이렉트합니다.
- `/api/auth/logout`도 쿠키 삭제 path를 명시하도록 보강했습니다.
- `/api/auth/register`가 더 이상 세션 쿠키를 발급하지 않도록 변경했습니다.
- 회원가입 성공 시 로그인 탭으로 돌아오고 테넌트 코드와 이메일을 채운 뒤 직접 로그인하도록 안내합니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과

## 남은 작업 후보

- 제품 방향 기준으로 명함, 미팅, 이메일, 일정, 견적, 계약 데이터를 AI가 읽는 입력 채널 확장
- 고객별 다음 행동 추천, 팔로업 초안, 일정 제안 같은 세일즈 에이전트 기능 설계
- 사용자가 직접 입력하는 CRM 폼보다 AI가 정리한 내용을 확인/수정/승인하는 화면 흐름 설계
- 대화로 고객 조회, 활동 등록, 일정 생성, 제안서/견적 준비를 수행하는 Conversational Sales Agent 구조 설계
- Sales Intelligence를 위한 고객/활동/거래/계약 데이터 모델 확장
- 실제 로그인 계정 생성/초기 비밀번호 세팅 스크립트 정리
- 비밀번호 변경 화면과 안전한 해시 생성 API 추가
- 고객 생성/수정 UI 추가
- 연락처 중복 판단 정책 추가
- accounts update 시 어떤 필드를 덮어쓸지 정책 세분화
- 세션 만료 안내 UI 추가
- 운영 환경용 HTTPS, Secure cookie, CORS, CSRF 정책 정리
- 테스트 코드 추가
- 현재 일부 기존 파일에 깨진 한글 문자열이 있어 UTF-8 기준 문구 정리 필요

### 2026-04-30: 마지막 로그인 정보 자동 채움

변경 파일:
- `login.html`
- `README.md`

작업 내용:
- 로그인 성공 후 마지막 로그인 테넌트 코드와 이메일을 `localStorage`에 저장하도록 했습니다.
- 로그인 페이지 진입 시 저장된 테넌트 코드와 이메일을 자동으로 채우도록 했습니다.
- 비밀번호는 저장하지 않습니다.

검증 예정:
- `node --check`는 인라인 스크립트가 있는 HTML에는 직접 적용하지 않았습니다.
- FastAPI 앱 import 및 Python 문법 검사는 다음 변경과 함께 수행합니다.

### 2026-04-30: 로그인 화면 회원가입 추가

변경 파일:
- `main.py`
- `login.html`
- `styles.css`
- `README.md`

작업 내용:
- 사용자 역할을 `owner`, `admin`, `manager`, `sales`, `viewer`로 서버 상수화했습니다.
- `/api/auth/register` API를 추가했습니다.
- 회원가입 시 테넌트 코드가 없으면 `tenants`에 새 테넌트를 생성합니다.
- 테넌트 코드가 이미 있으면 해당 테넌트에 사용자를 추가합니다.
- 같은 테넌트 안에 같은 이메일의 활성 사용자가 있으면 중복 오류를 반환합니다.
- 비밀번호는 bcrypt 해시로 `users.password_hash`에 저장합니다.
- 회원가입 성공 시 로그인 탭으로 돌아와 직접 로그인하도록 안내합니다.
- 로그인 화면에 로그인/회원가입 탭을 추가했습니다.
- 회원가입 폼에 테넌트 코드, 테넌트 이름, 이름, 이메일, 역할, 비밀번호 입력을 추가했습니다.

검증:
- `node --check script.js` 통과
- `uv run python -m py_compile main.py database.py graph.py` 통과
- `uv run python -c "import main; print('app import ok')"` 통과
