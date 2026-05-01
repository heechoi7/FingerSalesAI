# FingerSalesAI

## 프로젝트 공통 문서

새 장비, 새 팀원, 새 Codex 세션에서 작업을 시작할 때는 아래 문서를 먼저 읽습니다.

- `docs/PROJECT_GUIDE.md`: 프레임워크, DB 구성, 메뉴 구성, 상세 로직, 공통 코드, 보안/역할, 운영 기준
- `docs/HANDOFF_WORKFLOW.md`: Windows/Mac 작업 연속성, 팀 협업, 다른 Codex 인수인계 절차
- `README.md`: 지금까지의 변경 이력, 검증 명령, 남은 작업

작업 후에는 `README.md`의 변경 이력과 관련 `docs/` 문서를 함께 갱신합니다.

FingerSalesAI는 명함 이미지를 분석해 고객사와 연락처를 CRM 데이터베이스에 저장하고, 저장된 고객 정보를 기반으로 영업 대화와 리서치를 돕는 FastAPI 기반 로컬 웹 애플리케이션입니다.

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
```

주의:
- `.env`에는 실제 키와 비밀번호가 들어가므로 문서나 외부 공유물에 직접 복사하지 않습니다.
- `APP_SESSION_SECRET`은 로그인 세션 쿠키 서명에 사용됩니다. 운영 또는 외부 접속 환경에서는 긴 랜덤 값으로 설정해야 합니다.
- `MYSQL_TENANT_ID`는 로그인 이전 기본값 또는 로컬 기본값 용도였고, 현재 후속 작업 API는 로그인 세션의 `tenant_id`를 우선 사용합니다.

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
4. 회사명 기준으로 `accounts` 조회
5. 같은 `tenant_id` 안에 같은 회사명이 있으면 `accounts`는 신규 insert하지 않고 새 값으로 update
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

고객:

- `GET /api/customers`
  - 로그인 세션의 `tenant_id`, `user_id(owner_user_id)` 기준으로 contacts/accounts join 조회

- `GET /api/customers/{customer_id}`
  - 로그인 세션의 `tenant_id`, `user_id(owner_user_id)` 안에서 특정 연락처 조회

- `POST /api/customers`
  - 세션의 `tenant_id`, `user_id`를 사용해 고객사 upsert + 연락처 insert

- `PUT /api/customers/{customer_id}`
  - 세션의 `tenant_id`, `user_id`를 사용해 고객사 upsert + 연락처 update

- `DELETE /api/customers/{customer_id}`
  - 실제 삭제가 아니라 `contacts.deleted_at = NOW(6)` 소프트 삭제

명함:

- `POST /api/extract?skip_briefing=false`
  - 이미지 파일 업로드
  - 명함 정보 추출
  - accounts/contacts에 저장

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
