# FingerSalesAI 인수인계 및 협업 워크플로우

이 문서는 Windows 데스크탑, MacBook, 다른 팀원, 다른 Codex 세션이 작업을 이어받을 때 흐름이 끊기지 않도록 하는 운영 규칙입니다.

## 1. 핵심 원칙

1. 작업 전 문서를 읽습니다.
2. 작업 후 문서를 갱신합니다.
3. `.env` 값은 공유하지 않습니다.
4. DB 스키마 변경은 반드시 기록합니다.
5. 인증/테넌트/사용자 범위는 모든 API에서 확인합니다.
6. 다른 사람이 만든 변경을 임의로 되돌리지 않습니다.

## 2. 작업 시작 체크리스트

작업자는 아래 순서로 확인합니다.

```text
1. README.md 읽기
2. docs/PROJECT_GUIDE.md 읽기
3. docs/HANDOFF_WORKFLOW.md 읽기
4. 현재 요청 내용 확인
5. 관련 파일 열람
6. 작업 범위 결정
7. 구현
8. 검증
9. README.md 변경 이력 갱신
10. 필요한 docs 갱신
```

## 3. Windows와 MacBook 간 작업 이동

### 3.1 Git 기준

권장:

- 모든 코드는 Git 원격 저장소 기준으로 동기화
- 작업 전 pull
- 작업 후 commit/push
- 장비 이동 전 README 변경 이력 업데이트

주의:

- `.env`는 commit하지 않습니다.
- `.venv`, `.uv-cache`, `.uv-python`, `__pycache__`는 공유 대상이 아닙니다.
- `uv.lock`은 공유 대상입니다.

### 3.2 장비별 준비

공통 설치 필요:

- Python 또는 uv가 사용할 수 있는 Python
- uv
- Node.js
- MySQL 접근 가능 환경

공통 명령:

```bash
uv run main.py
```

검증:

```bash
node --check script.js
uv run python -m py_compile main.py database.py graph.py
uv run python -c "import main; print('app import ok')"
```

### 3.3 환경 변수 이동

장비마다 `.env`를 따로 만듭니다.

기준 파일:

```text
.env.example
```

민감 값:

- Google/Gemini API key
- Tavily API key
- DB password
- APP_SESSION_SECRET

이 값들은 문서, 채팅, 커밋 메시지에 쓰지 않습니다.

## 4. 다른 Codex 세션에서 이어받기

새 Codex는 반드시 아래 규칙을 따릅니다.

### 4.1 먼저 읽을 파일

```text
README.md
docs/PROJECT_GUIDE.md
docs/HANDOFF_WORKFLOW.md
```

### 4.2 먼저 확인할 코드

요청이 인증/로그인 관련이면:

```text
main.py
login.html
script.js
styles.css
database.py
```

요청이 고객/DB 관련이면:

```text
main.py
database.py
script.js
README.md
docs/PROJECT_GUIDE.md
```

요청이 명함/AI 관련이면:

```text
graph.py
main.py
script.js
docs/PROJECT_GUIDE.md
```

### 4.3 Codex 응답 원칙

새 Codex는 아래 내용을 유지합니다.

- 작업 전 현재 구조를 확인합니다.
- 사용자 요청이 구현 요청이면 직접 수정합니다.
- 수정 후 검증합니다.
- README 변경 이력을 갱신합니다.
- 관련 docs도 갱신합니다.

## 5. 팀원별 작업 분리 기준

### 5.1 Backend 담당

주요 파일:

- `main.py`
- `database.py`
- `graph.py`
- `pyproject.toml`
- `requirements.txt`

책임:

- API 설계
- DB 접근
- 인증/권한
- AI workflow
- 서버 검증

주의:

- 고객 API는 `tenant_id`와 `owner_user_id` 기준을 확인합니다.
- 인증 API는 세션 쿠키 정책을 유지합니다.
- DB 스키마 변경은 문서화합니다.

### 5.2 Frontend 담당

주요 파일:

- `index.html`
- `login.html`
- `script.js`
- `styles.css`

책임:

- 화면 구조
- 고객 그리드
- 상세 패널
- 채팅 UX
- 로그인/회원가입 UX

주의:

- 보호 API 호출은 `apiFetch`를 사용합니다.
- 선택 고객은 `memory.selectedCustomer`에 저장합니다.
- 상단 사용자 표시는 세션 정보를 사용합니다.

### 5.3 DB 담당

책임:

- MySQL schema 관리
- 테이블 주석 관리
- migration 또는 schema export 준비
- seed data 관리

현재 필요 작업:

- 현재 DB schema를 파일로 저장
- migration 도구 선정
- 초기 tenant/user 생성 절차 문서화

### 5.4 AI/Agent 담당

주요 파일:

- `graph.py`
- `main.py`

책임:

- 명함 인식 정확도
- 회사 리서치
- 선택 고객 컨텍스트 우선순위
- 검색 결과 출처 처리

주의:

- 사용자가 선택한 고객이 있으면 그 고객이 최우선입니다.
- 최신 명함 정보는 선택 고객이 없을 때 우선합니다.

## 6. 공통 검증 기준

최소 검증:

```bash
node --check script.js
uv run python -m py_compile main.py database.py graph.py
uv run python -c "import main; print('app import ok')"
```

수동 검증:

1. `/login.html` 접속
2. 로그인
3. 상단 사용자 정보 확인
4. 고객 목록 조회 확인
5. 고객 행 선택
6. 선택 고객 기반 채팅 질문
7. 로그아웃
8. 다시 로그인 페이지로 이동 확인

## 7. 변경 이력 작성 템플릿

README에 아래 형식으로 추가합니다.

```markdown
### YYYY-MM-DD: 작업 제목

변경 파일:
- `file1`
- `file2`

작업 내용:
- 변경한 내용
- API/DB/UI 영향
- 보안/권한 영향

검증:
- `command` 통과

남은 이슈:
- 필요 시 작성
```

## 8. 브랜치/커밋 권장 흐름

권장 브랜치 예시:

```text
codex/auth-session-fix
codex/customer-panel-context
codex/db-schema-docs
codex/ui-login-register
```

커밋 메시지 예시:

```text
docs: add project guide and handoff workflow
feat: add tenant-aware registration
fix: scope customers by owner user
fix: prioritize selected customer in chat context
```

## 9. 앞으로 꼭 정리해야 할 작업

우선순위 높은 문서/구조 작업:

1. DB schema export 파일 추가
2. seed script 추가
3. migration 정책 결정
4. API reference 문서 추가
5. 테스트 전략 문서 추가
6. 역할별 권한 정책 세분화
7. Docker Compose 개발 환경 검토
8. Windows/Mac 초기 세팅 문서 추가
