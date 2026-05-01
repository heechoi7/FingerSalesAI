# FingerSalesAI

## 프로젝트 공통 문서

새 장비, 새 팀원, 새 Codex 세션에서 작업을 시작할 때는 아래 문서를 먼저 읽습니다.

- `docs/PROJECT_GUIDE.md`: 프레임워크, DB 구성, 메뉴 구성, 상세 로직, 공통 코드, 보안/역할, 운영 기준
- `docs/HANDOFF_WORKFLOW.md`: Windows/Mac 작업 연속성, 팀 협업, 다른 Codex 인수인계 절차
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

- `GET /api/quotes`
  - 견적 테이블 `quotes` 기준 조회
  - 조회 조건: `company_name`, `contact_name`
  - 로그인 세션의 `tenant_id`, `user_id(owner_user_id)` 기준으로 제한

- `GET /api/contracts`
  - 계약 테이블 `contracts` 기준 조회
  - 조회 조건: `company_name`, `contact_name`
  - 로그인 세션의 `tenant_id`, `user_id(owner_user_id)` 기준으로 제한

명함:

- `POST /api/extract?skip_briefing=false`
  - 이미지 파일 업로드
  - 명함 정보 추출
  - accounts/contacts에 저장

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
