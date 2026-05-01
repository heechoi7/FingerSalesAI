# FingerSalesAI 프로젝트 가이드

이 문서는 Windows 데스크탑, MacBook, 다른 팀원의 개발 환경, 다른 Codex 세션에서 같은 흐름으로 작업을 이어가기 위한 공통 기준 문서입니다.

작업을 시작하는 사람과 Codex는 먼저 아래 문서를 순서대로 읽습니다.

1. `README.md`: 지금까지의 작업 이력과 실행/검증 기록
2. `docs/PROJECT_GUIDE.md`: 프로젝트 구조와 기능/업무 흐름
3. `docs/HANDOFF_WORKFLOW.md`: 장비 이동, 팀 협업, Codex 작업 인수인계 규칙

새로운 작업을 하면 `README.md`의 변경 이력과 이 문서의 관련 섹션을 함께 갱신합니다.

## 0. 제품 정의와 개발 방향

FingerSalesAI는 기존 FingerSales CRM에 AI 기능을 단순히 추가한 CRM이 아닙니다.

제품 정의:
- 입력을 최소화하고, AI가 영업 업무를 먼저 정리, 제안, 실행하는 세일즈 에이전트 클라우드

핵심 문장:
- 영업사원이 입력하지 않아도, AI가 고객, 활동, 일정, 제안, 팔로업을 정리하고 다음 행동을 제안하는 AI 세일즈 클라우드

핵심 가치:
- Zero Input CRM
- Conversational Sales Agent
- Sales Intelligence

개발 판단 기준:
- 사용자가 직접 입력해야 하는 데이터가 줄어드는가
- 명함, 미팅, 이메일, 일정, 견적, 계약 같은 영업 데이터를 AI가 자동으로 읽고 구조화하는가
- 고객, 활동, 일정, 제안, 팔로업이 하나의 대화형 업무 흐름으로 이어지는가
- AI가 단순 답변이 아니라 다음 행동을 제안하거나 실행 준비까지 돕는가
- 멀티테넌트 클라우드 환경에서 보안, 감사 가능성, 속도, 안정성을 해치지 않는가

명함 인식과 고객 등록은 첫 진입 기능입니다. 이후 기능은 "데이터 입력 화면을 더 많이 만드는 것"보다 "AI가 읽고 정리한 결과를 영업사원이 확인, 수정, 실행하는 것"을 우선합니다.

## 1. 프레임워크

### 1.1 전체 구성

FingerSalesAI는 현재 단일 FastAPI 애플리케이션과 정적 프론트엔드로 구성되어 있습니다.

- Backend: FastAPI
- Frontend: 정적 HTML/CSS/JavaScript
- Runtime/Package: Python, uv
- Database: MySQL 8.4
- AI workflow: LangGraph
- LLM/Search: Gemini, Tavily, LangChain
- Auth: 서버 서명 HTTP-only 쿠키 기반 세션

### 1.2 실행 진입점

메인 서버 파일:

```text
main.py
```

실행 명령:

```powershell
uv run main.py
```

로컬 접속:

```text
http://localhost:8000/login.html
```

### 1.3 주요 파일 역할

```text
main.py
```

- FastAPI 앱 생성
- 인증 API
- 고객/연락처 API
- 명함 분석 API
- 채팅 API
- 정적 페이지 응답
- 세션 쿠키 발급/검증/삭제

```text
database.py
```

- MySQL 연결 설정
- 필수 테이블 존재 확인
- 테넌트 기본값
- 고객 조회 결과 변환

```text
graph.py
```

- 명함 이미지 분석 LangGraph 워크플로
- Gemini 모델 생성
- 명함 필드 추출
- 회사 검색/브리핑 생성

```text
login.html
```

- 로그인 UI
- 회원가입 UI
- 마지막 로그인 테넌트 코드/이메일 자동 채움

```text
index.html
```

- 메인 CRM/채팅 화면 구조
- 상단 메뉴
- 고객 패널
- 채팅 패널
- 우측 작업/로그 패널

```text
script.js
```

- 세션 로드
- 고객 목록 로드
- 고객 선택
- 명함 업로드
- 채팅 요청
- 로그아웃
- 화면 상호작용

```text
styles.css
```

- 로그인 화면 스타일
- 메인 레이아웃
- 고객 그리드
- 상세 패널
- 채팅 UI
- 우측 패널 UI

### 1.4 의존성 관리

`requirements.txt`와 `pyproject.toml`이 함께 있습니다.

- `requirements.txt`: 전통적인 Python 의존성 목록
- `pyproject.toml`: `uv run`이 프로젝트 의존성을 인식하기 위한 메타데이터
- `uv.lock`: uv 잠금 파일

새 의존성을 추가하면 두 파일을 함께 갱신합니다.

검증:

```powershell
uv run python -m py_compile main.py database.py graph.py
uv run python -c "import main; print('app import ok')"
```

프론트 JS 검증:

```powershell
node --check script.js
```

## 2. DB 구성

### 2.1 DB 기본 정보

현재 로컬 DB는 MySQL 8.4를 기준으로 합니다.

스키마 이름:

```text
FingerSalesAI
```

환경 변수:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=FingerSalesAI
MYSQL_USER=...
MYSQL_PASSWORD=...
MYSQL_TENANT_ID=1
APP_SESSION_SECRET=...
FSAI_EXTRA_ENV_PATH=
```

주의:

- 실제 비밀번호와 API 키는 문서에 쓰지 않습니다.
- `.env.example`에는 형식과 변수 이름만 유지합니다.
- 다른 프로젝트의 `.env`를 자동으로 읽지 않으며, 특별히 필요할 때만 `FSAI_EXTRA_ENV_PATH`에 명시합니다.

### 2.2 핵심 테이블

#### tenants

테넌트 테이블입니다.

주요 컬럼:

- `id`: 테넌트 ID
- `tenant_code`: 로그인 시 입력하는 테넌트 코드
- `name`: 테넌트 이름
- `status`: `active`, `trial`, `suspended`, `closed`
- `timezone`: 기본 시간대
- `locale`: 기본 로케일
- `deleted_at`: 소프트 삭제 일시

로그인 가능한 테넌트 상태:

- `active`
- `trial`

#### users

사용자 테이블입니다.

주요 컬럼:

- `id`: 사용자 ID
- `tenant_id`: 소속 테넌트 ID
- `email`: 로그인 이메일
- `password_hash`: bcrypt 해시
- `name`: 사용자 이름
- `role`: 사용자 역할
- `status`: 사용자 상태
- `last_login_at`: 마지막 로그인 일시
- `deleted_at`: 소프트 삭제 일시

사용자 역할:

- `owner`: 소유자
- `admin`: 관리자
- `manager`: 매니저
- `sales`: 영업
- `viewer`: 조회

로그인 가능한 사용자 상태:

- `active`

#### accounts

고객사 테이블입니다.

주요 컬럼:

- `id`: 고객사 ID
- `tenant_id`: 테넌트 ID
- `owner_user_id`: 담당 사용자 ID
- `name`: 고객사 이름
- `account_type`: 고객사 유형
- `industry`: 산업군
- `business_no`: 사업자등록번호
- `website`: 웹사이트
- `phone`: 대표 전화번호
- `address`: 주소
- `status`: 고객사 상태
- `deleted_at`: 소프트 삭제 일시

저장 규칙:

- 같은 `tenant_id` 안에 같은 회사명이 있으면 새 `accounts` 행을 만들지 않습니다.
- 기존 `accounts` 행을 새 값으로 보강합니다.
- 빈 값으로 기존 값을 덮어쓰지 않습니다.

#### contacts

연락처 테이블입니다.

주요 컬럼:

- `id`: 연락처 ID
- `tenant_id`: 테넌트 ID
- `account_id`: 고객사 ID
- `owner_user_id`: 담당 사용자 ID
- `name`: 연락처 이름
- `title`: 직함
- `department`: 부서
- `email`: 이메일
- `phone`: 전화번호
- `mobile`: 휴대전화번호
- `is_primary`: 대표 연락처 여부
- `deleted_at`: 소프트 삭제 일시

조회 규칙:

- 고객 패널은 반드시 로그인 세션의 `tenant_id`와 `user_id`를 함께 사용합니다.
- 실제 SQL 조건은 `contacts.tenant_id = session.tenant_id`와 `contacts.owner_user_id = session.user_id`입니다.
- 다른 사용자가 같은 테넌트에서 등록한 연락처는 현재 사용자 화면에 보이지 않습니다.

### 2.3 명함 저장 흐름

1. 사용자가 채팅 입력창에 명함 이미지를 첨부합니다.
2. 프론트가 `/api/extract`로 이미지를 전송합니다.
3. 서버는 세션 쿠키를 검증합니다.
4. `graph.py`가 명함 정보를 추출합니다.
5. 추출된 회사명을 기준으로 `accounts`를 찾습니다.
6. 같은 회사가 있으면 `accounts`를 보강 update합니다.
7. 같은 회사가 없으면 `accounts`를 insert합니다.
8. `contacts`에는 항상 새 행을 insert합니다.
9. `contacts.owner_user_id`는 로그인한 사용자 ID로 저장합니다.
10. 프론트는 반환된 고객을 그리드에 추가하고 선택 상태로 표시합니다.

### 2.4 고객 조회 흐름

1. 메인 화면 진입 시 `/api/auth/me`로 세션 확인
2. `/api/customers` 호출
3. 서버는 세션에서 `tenant_id`, `user_id`를 읽음
4. `contacts`와 `accounts`를 join
5. 조건:
   - `contacts.tenant_id = session.tenant_id`
   - `contacts.owner_user_id = session.user_id`
   - `contacts.deleted_at IS NULL`
6. 프론트는 받은 목록을 고객 그리드에 표시

### 2.5 고객 수정/삭제 정책

현재 UI에는 별도 고객 생성/수정 폼은 없지만 API는 준비되어 있습니다.

- `PUT /api/customers/{customer_id}`
  - `tenant_id`와 `owner_user_id`가 모두 맞는 연락처만 수정

- `DELETE /api/customers/{customer_id}`
  - 물리 삭제가 아니라 `contacts.deleted_at = NOW(6)` 처리
  - `tenant_id`와 `owner_user_id`가 모두 맞아야 삭제 가능

## 3. 메뉴 구성

### 3.1 상단 메뉴

현재 메뉴:

- 고객
- 파이프라인
- 캘린더
- 견적
- 계약

현재 실제 동작이 구현된 메뉴:

- 고객

나머지 메뉴는 UI 구조만 있으며 실제 데이터 로직은 추후 구현 예정입니다.

### 3.2 상단 우측 사용자 영역

표시 형식:

```text
테넌트 이름 / 사용자 이름 / 사용자 역할 이름
```

예:

```text
핑거포스트 / 제임스 / 관리자
```

처리 흐름:

1. `/` 요청 시 서버가 세션 쿠키를 검증
2. 세션이 없으면 `/login.html`로 redirect
3. 세션이 있으면 서버가 `window.__FSAI_SESSION__`을 HTML에 주입
4. `script.js`가 이 값을 읽어 상단 라벨 즉시 표시
5. 이어서 `/api/auth/me`로 최신 세션 확인

### 3.3 로그아웃

우측 상단 로그아웃 아이콘은 `/logout` 링크입니다.

처리 흐름:

1. 사용자가 로그아웃 아이콘 클릭
2. 브라우저가 `/logout`으로 이동
3. 서버가 `fsai_session` 쿠키를 만료
4. 서버가 `/login.html`로 redirect

## 4. 각 메뉴별 설명 및 상세 로직

### 4.1 고객 메뉴

목적:

- 로그인한 사용자가 등록한 고객사/연락처를 조회합니다.
- 명함 인식 결과를 고객 목록에 반영합니다.
- 선택된 고객을 기반으로 에이전트가 답변하도록 합니다.

화면 구성:

- 좌측 고객 그리드
- 좌측 하단 상세 패널
- 중앙 채팅 패널
- 우측 작업 로그/계획 패널

고객 그리드 컬럼:

- 회사명
- 이름
- 직무
- 직위
- 휴대전화
- 이메일
- 홈페이지
- 추가 정보
- 등록 시간

고객 행 클릭:

1. 기존 선택 행의 selected 스타일 제거
2. 클릭한 행에 selected 스타일 적용
3. `memory.selectedCustomer` 갱신
4. 상세 패널 갱신

선택 고객 기반 채팅:

1. 사용자가 고객 그리드 행 선택
2. `script.js`가 선택 고객을 `memory.selectedCustomer`에 저장
3. 채팅 질문 시 `context.selectedCustomer`로 서버에 전달
4. `main.py`가 `selected_customer_highest_priority` 컨텍스트 생성
5. 에이전트 프롬프트가 선택 고객을 마지막 등록 고객보다 우선

### 4.2 채팅 메뉴/패널

현재 별도 상단 메뉴는 없고 중앙 패널로 항상 표시됩니다.

지원 기능:

- 텍스트 질문
- 이미지 파일 첨부
- 명함 이미지 인식
- 회사 브리핑 생성
- Tavily 검색 기반 답변
- 최근 대화/고객 컨텍스트 전달

채팅 컨텍스트 우선순위:

1. 선택 고객
2. 최근 명함/고객 목록
3. 최근 대화 기록
4. 외부 검색 결과

### 4.3 파이프라인 메뉴

현재 상태:

- 상단 메뉴 항목만 존재
- 실제 DB/API/UI 로직 미구현

추후 예상:

- 영업 기회 목록
- 단계별 파이프라인
- 고객사/연락처 연결
- 예상 매출, 진행 단계, 담당자

### 4.4 캘린더 메뉴

현재 상태:

- 상단 메뉴 항목만 존재
- 실제 DB/API/UI 로직 미구현

추후 예상:

- 고객 미팅 일정
- 후속 연락 일정
- 제안/견적 마감일

### 4.5 견적 메뉴

현재 상태:

- 상단 메뉴 항목만 존재
- 실제 DB/API/UI 로직 미구현

추후 예상:

- 견적서 생성
- 고객사 연결
- 품목/금액/상태 관리

### 4.6 계약 메뉴

현재 상태:

- 상단 메뉴 항목만 존재
- 실제 DB/API/UI 로직 미구현

추후 예상:

- 계약 목록
- 계약 상태
- 계약 금액
- 고객사/담당자 연결

## 5. 공통 코드 및 관리 형태

### 5.1 API 인증 공통 흐름

보호 API는 `require_session(request)`를 사용합니다.

세션 검증:

```text
request.cookies["fsai_session"]
-> read_session_token
-> HMAC 서명 검증
-> 만료 시간 검증
-> session dict 반환
```

세션 dict 주요 필드:

- `tenant_id`
- `tenant_code`
- `tenant_name`
- `tenant_status`
- `user_id`
- `user_name`
- `email`
- `role`
- `exp`

### 5.2 프론트 API 호출 공통 흐름

`script.js`의 `apiFetch`를 사용합니다.

역할:

- `credentials: "same-origin"` 명시
- 401 응답 시 `/login.html`로 이동

새 API 호출을 추가할 때는 특별한 이유가 없으면 `fetch` 대신 `apiFetch`를 사용합니다.

### 5.3 프론트 상태 관리

현재 별도 프레임워크 없이 `script.js`의 메모리 객체를 사용합니다.

```js
const memory = {
  cards: [],
  messages: [],
  selectedCustomer: null,
};
```

역할:

- `cards`: 최근 고객/명함 컨텍스트
- `messages`: 최근 채팅 기록
- `selectedCustomer`: 사용자가 고객 그리드에서 선택한 고객

### 5.4 문서 관리

작업 시 반드시 갱신할 문서:

- `README.md`: 변경 이력, 검증 명령, 남은 이슈
- `docs/PROJECT_GUIDE.md`: 구조나 정책 변경 시 갱신
- `docs/HANDOFF_WORKFLOW.md`: 협업/장비 이동 절차 변경 시 갱신

### 5.5 코드 변경 원칙

- 기존 구조를 크게 바꾸기 전에 README와 docs를 먼저 확인합니다.
- DB 컬럼 의미는 information_schema의 한글 주석을 우선 참고합니다.
- 사용자/테넌트 범위가 있는 API는 반드시 세션의 `tenant_id`, `user_id`를 검토합니다.
- 민감한 값은 로그와 문서에 남기지 않습니다.
- 기능 변경 후 가능한 검증 명령을 실행합니다.

## 6. 보안 및 역할

### 6.1 인증

로그인:

- `POST /api/auth/login`
- 입력: `tenant_code`, `email`, `password`
- 서버는 `tenants`와 `users`를 join해 사용자 확인
- bcrypt로 password_hash 검증
- 성공 시 HTTP-only 세션 쿠키 발급

회원가입:

- `POST /api/auth/register`
- 입력: `tenant_code`, `tenant_name`, `name`, `email`, `password`, `role`
- 테넌트가 없으면 생성
- 테넌트가 없으면 첫 사용자는 서버에서 `owner`로 생성
- 기존 테넌트 가입은 기본적으로 차단
- 기존 테넌트 self-join을 허용하려면 `ALLOW_EXISTING_TENANT_SELF_JOIN=true` 설정 필요
- `TENANT_JOIN_CODE`가 설정되어 있으면 가입 코드가 일치해야 기존 테넌트에 참여 가능
- 기존 테넌트 self-join에서 허용되는 역할은 `sales`, `viewer` 중심이며, 서버가 권한 상승을 제한
- 비밀번호는 bcrypt 해시로 저장
- 회원가입 성공 후 자동 로그인하지 않고 로그인 화면으로 복귀

보안 보강:

- 로그인/회원가입 API에는 IP 기반 in-memory rate limit이 적용됩니다.
- 기본값은 60초 동안 10회입니다.
- 운영 다중 인스턴스 환경에서는 Redis 같은 공유 저장소 기반 rate limit으로 교체해야 합니다.

로그아웃:

- `GET /logout`
- 세션 쿠키 삭제
- `/login.html`로 redirect

### 6.2 세션 쿠키

쿠키 이름:

```text
fsai_session
```

특성:

- HTTP-only
- SameSite=Lax
- path=/
- production 환경에서는 Secure cookie 사용
- HMAC 서명
- 기본 만료 시간 12시간

서명 키:

```env
APP_SESSION_SECRET
```

운영에서는 반드시 긴 랜덤 값으로 설정합니다.

운영 환경:

- `APP_ENV=production`이면 `APP_SESSION_SECRET`은 32자 이상이어야 합니다.
- `APP_ALLOWED_HOSTS`로 허용 host를 제한할 수 있습니다.
- `TRUST_PROXY_HEADERS=true`는 신뢰 가능한 reverse proxy 뒤에서만 켜고, 그렇지 않으면 클라이언트가 보낸 `X-Forwarded-For`를 신뢰하지 않습니다.
- 보안 응답 헤더가 기본 적용됩니다.
- production에서는 HSTS 헤더가 추가됩니다.

### 6.3 역할 정의

서버 상수:

```text
owner
admin
manager
sales
viewer
```

현재 역할별 API 권한 차등은 아직 세분화되어 있지 않습니다.

현재 적용된 범위 제한:

- 모든 고객 조회/수정/삭제는 `tenant_id`와 `owner_user_id` 기준으로 제한
- 즉 같은 테넌트라도 다른 사용자의 연락처는 보이지 않음

추후 필요:

- owner/admin은 테넌트 전체 조회 가능
- manager는 팀 단위 조회 가능
- sales는 본인 데이터만 조회 가능
- viewer는 읽기 전용

### 6.4 민감 정보 관리

문서에 기록하지 않는 값:

- 실제 API 키
- 실제 DB 비밀번호
- 세션 토큰
- password_hash 전체 값
- 사용자가 입력한 비밀번호

허용되는 기록:

- 환경 변수 이름
- 컬럼 이름
- 해시 알고리즘 종류
- 테스트 결과 상태 코드

### 6.5 안정성 및 성능 기준

DB 연결:

- `database.py`는 MySQL connection pool을 사용합니다.
- 기본 pool size는 `MYSQL_POOL_SIZE=10`입니다.
- 연결 timeout은 `MYSQL_CONNECTION_TIMEOUT`으로 제어합니다.

서버 보안 헤더:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- production에서 `Strict-Transport-Security`

추후 클라우드 필수 작업:

- Redis 기반 rate limit
- 중앙 로그/모니터링
- structured logging
- request id 전파
- reverse proxy의 forwarded header 신뢰 범위 문서화와 운영 설정
- DB migration
- 백업/복구 전략
- 비동기 작업 큐
- 파일 업로드 크기 제한과 스토리지 분리

## 7. Windows/Mac 작업 연속성

### 7.1 공통 기준

Windows 데스크탑과 MacBook에서 같은 흐름으로 작업하려면 아래를 맞춥니다.

- 동일한 Git 원격 저장소 사용
- 같은 브랜치 전략 사용
- `.env.example`은 공유하되 `.env`는 장비별로 유지
- MySQL 스키마 버전을 동일하게 유지
- `uv.lock`을 공유해 Python 의존성 차이를 줄임
- 작업 전 README와 docs 확인
- 작업 후 README 변경 이력 갱신

### 7.2 장비별 로컬 설정

공통:

```powershell
uv run main.py
```

Windows PowerShell:

```powershell
uv run python -m py_compile main.py database.py graph.py
node --check script.js
```

Mac zsh/bash:

```bash
uv run python -m py_compile main.py database.py graph.py
node --check script.js
```

### 7.3 .env 관리

`.env`는 장비별로 따로 관리합니다.

공유하지 않습니다.

필요한 변수 목록은 `.env.example`을 기준으로 합니다.

### 7.4 DB 동기화

현재는 로컬 MySQL을 직접 사용합니다.

팀 작업을 고려하면 추후 아래 중 하나가 필요합니다.

- 공용 개발 DB
- Docker Compose 기반 MySQL
- DB migration 도구
- seed script
- schema.sql

현재 가장 필요한 다음 작업:

- DB 스키마를 파일로 추출
- migration 정책 수립
- 초기 tenant/user seed 절차 정리

## 8. 팀 협업 워크플로우

### 8.1 작업 시작 전

1. 최신 코드 받기
2. README 변경 이력 확인
3. `docs/PROJECT_GUIDE.md` 확인
4. 맡은 작업 범위 확인
5. 관련 파일만 수정

### 8.2 작업 중

1. DB/API/UI 변경 범위를 분리해 생각
2. 테넌트/사용자 범위 누락 여부 확인
3. 인증이 필요한 API는 `require_session` 사용
4. 프론트 API 호출은 `apiFetch` 사용
5. 명함/고객 컨텍스트 변경 시 채팅 컨텍스트도 확인

### 8.3 작업 후

1. 검증 명령 실행
2. README 변경 이력 추가
3. docs 관련 섹션 업데이트
4. 남은 이슈 기록

### 8.4 권장 검증 세트

```powershell
node --check script.js
uv run python -m py_compile main.py database.py graph.py
uv run python -c "import main; print('app import ok')"
```

가능하면 브라우저에서 확인:

1. 로그인
2. 상단 사용자 표시
3. 고객 목록 로드
4. 고객 행 선택
5. 선택 고객 기반 채팅 질문
6. 로그아웃

## 9. 다른 Codex가 반드시 알아야 할 사항

다른 Codex가 새 세션에서 이 프로젝트를 맡으면 먼저 아래를 확인합니다.

1. `README.md`
2. `docs/PROJECT_GUIDE.md`
3. `docs/HANDOFF_WORKFLOW.md`
4. 현재 작업 요청
5. 관련 파일의 실제 코드

중요 규칙:

- README 변경 이력을 계속 갱신합니다.
- 사용자 요청 없이 기존 변경을 되돌리지 않습니다.
- DB 권한/테넌트/사용자 범위를 항상 확인합니다.
- 고객 관련 API는 본인 데이터만 조회하는 정책이 현재 기본입니다.
- 선택된 고객 컨텍스트가 채팅 답변 우선순위입니다.
- 회원가입은 자동 로그인하지 않고 로그인 화면으로 돌아갑니다.
- 로그아웃은 `/logout` 라우트를 사용합니다.

## 10. 앞으로 추가하면 좋은 문서

추후 팀 규모가 커지면 아래 문서를 추가합니다.

- `docs/API_REFERENCE.md`
- `docs/DB_SCHEMA.md`
- `docs/TESTING.md`
- `docs/DEPLOYMENT.md`
- `docs/SECURITY.md`
- `docs/UI_GUIDE.md`
- `docs/AI_AGENT_CONTEXT.md`

## 11. SNS 링크 기반 고객 등록 흐름

목적:
- 명함 이미지뿐 아니라 에이전트 입력창에 붙여 넣은 SNS 링크도 고객 등록 입력으로 처리합니다.
- 이 흐름은 제품 방향인 Zero Input CRM과 Conversational Sales Agent를 위한 입력 채널 확장입니다.

처리 흐름:
1. 사용자가 에이전트 입력창에 SNS 링크를 입력합니다.
2. `script.js`가 LinkedIn, Instagram, Facebook, X, YouTube, TikTok, GitHub, Naver Blog, Medium 링크를 감지합니다.
3. SNS 링크가 있으면 일반 `/api/chat` 요청 대신 `/api/extract/sns`로 전송합니다.
4. 서버는 세션 쿠키를 검증합니다.
5. `main.py`가 URL을 플랫폼별로 구분하고 개인/회사/채널/블로그/프로필 유형을 판단합니다.
6. SNS 링크를 `회사명`, `이름`, `직무`, `직위`, `홈페이지`, `SNS종류`, `SNS대상`, `SNS핸들`, `SNS링크` 필드로 정규화합니다.
7. 정규화된 데이터는 명함 입력과 같은 `save_extracted_customer` 경로를 사용합니다.
8. 같은 `tenant_id` 안에 같은 회사명이 있으면 `accounts`는 신규 insert하지 않고 update합니다.
9. `contacts`에는 매번 새 연락처 행을 insert합니다.
10. 프론트는 저장 결과를 채팅창, 고객 그리드, 선택 고객 상세 정보에 즉시 반영합니다.

현재 한계:
- SNS 공개 페이지를 직접 크롤링하지 않고 URL 구조에서 플랫폼, 핸들, 대상 유형을 우선 추출합니다.
- 실제 이름, 회사, 직책을 더 정밀하게 채우려면 이후 SNS 공개 프로필 분석 또는 검색 기반 보강 단계를 추가합니다.

보강된 LinkedIn 처리:
- `/api/extract/sns`는 SNS URL 구조 분석 후 Tavily 검색과 Gemini 정리를 사용해 이름, 회사, 직무, 직위, 요약, 영업 브리핑을 보강합니다.
- 프론트 캐시 문제로 SNS 링크가 `/api/chat`으로 들어와도 서버가 다시 SNS 링크를 감지해 고객 등록 fallback을 수행합니다.
- `/` HTML 응답은 `script.js?v=<파일수정시간>` 형태로 내려가므로 최신 SNS 분기 로직이 브라우저에 반영되기 쉽습니다.
- `script.js`와 `styles.css`는 `Cache-Control: no-cache`를 사용합니다.
