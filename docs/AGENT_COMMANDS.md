# FingerSalesAI Agent Command Registry

이 문서는 에이전트 대화창에서 처리되는 업무 명령을 소스 코드와 함께 관리하기 위한 기준입니다.

FingerSalesAI의 핵심 방향은 화면에서 데이터를 직접 입력하는 CRM이 아니라, 사용자가 대화창에 말하면 AI와 백엔드가 고객, 활동, 일정, 견적, 계약, 리서치, 파일 분석을 이어서 처리하는 구조입니다. 따라서 대화 명령은 기능이 늘어나도 충돌하지 않도록 command case 단위로 등록, 라우팅, 테스트, 문서화합니다.

## 소스 구조

```text
agent_commands.py
```

- 에이전트 명령 케이스의 단일 레지스트리입니다.
- 각 케이스는 `case_id`, `priority`, `handler_name`, `matcher`, `requires_customer_preflight`, `flow_steps`, `test_points`를 가집니다.
- `/api/chat`은 먼저 `route_agent_command(message)`로 command case를 결정한 뒤 기존 처리 함수로 위임합니다.
- `/api/agent/command-cases`는 현재 등록된 command case와 처리 플로우를 JSON으로 반환합니다.

```text
main.py
```

- 인증, 고객 선확인, DB 저장, 감사 로그, 실제 업무 처리 함수가 있습니다.
- 대화 명령을 추가할 때 `/api/chat`에 임의 조건문을 계속 늘리지 않고, 먼저 `agent_commands.py`에 케이스를 등록합니다.

## 현재 Command Case

| case_id | 우선순위 | 핸들러 | 고객 선확인 | 목적 |
| --- | ---: | --- | --- | --- |
| `sns_profile_research` | 20 | `handle_sns_profile_research` | 예 | SNS 링크를 판별하고 공개 프로필 정보를 확인 |
| `sales_activity_schedule` | 30 | `handle_sales_activity_schedule` | 예 | 영업활동 일정 등록, 취소, 변경, 반복, 조회 |
| `general_sales_agent` | 1000 | `handle_general_sales_agent` | 예 | 분류되지 않은 일반 세일즈 대화, 검색, LLM 추론 |

현재 `handler_name`은 관리용 이름이며, 실제 실행은 `/api/chat` 내부의 기존 SNS/일정/LLM 처리 블록으로 연결되어 있습니다. 다음 단계에서 핸들러 함수를 별도 모듈로 더 분리할 수 있습니다.

## 라우팅 규칙

1. `priority`가 낮은 케이스부터 검사합니다.
2. 첫 번째로 `matcher(message)`가 참인 케이스가 선택됩니다.
3. 어떤 케이스도 맞지 않으면 항상 `general_sales_agent` fallback으로 처리합니다.
4. 선택된 케이스가 `requires_customer_preflight=true`이면 LLM이나 업무 처리 전에 고객 후보를 먼저 조회합니다.
5. 고객 후보가 여러 건이면 명령 실행을 멈추고 사용자에게 선택을 요청합니다.
6. 고객 후보가 한 건이면 선택 고객 컨텍스트를 주입하고 같은 명령을 계속 처리합니다.
7. 라우팅 결과는 `audit_logs`에 `route / agent_command`로 남깁니다.

## 새 대화 명령 추가 절차

1. `agent_commands.py`에 `AgentCommandCase`를 추가합니다.
2. `case_id`는 변경하지 않을 안정적인 snake_case로 정합니다.
3. `priority`는 더 구체적인 명령일수록 낮게 둡니다.
4. `matcher`는 단순하고 예측 가능하게 작성합니다. LLM 판별은 최후 보조 수단으로만 사용합니다.
5. 고객/회사 대상 업무라면 `requires_customer_preflight=True`로 설정합니다.
6. `flow_steps`에 실제 처리 순서를 적습니다.
7. `test_points`에 충돌 방지와 회귀 검증 기준을 적습니다.
8. `/api/chat`에 해당 `case_id` 처리 블록 또는 별도 핸들러 호출을 연결합니다.
9. `tests/`에 라우팅 테스트와 핵심 업무 테스트를 추가합니다.
10. 이 문서와 `README.md` 변경 이력에 작업 내용을 기록합니다.

## 충돌 방지 기준

- SNS 링크처럼 명확한 입력 채널이 있는 명령은 일반 LLM보다 높은 우선순위를 둡니다.
- 일정, 견적, 계약처럼 DB를 변경하는 명령은 사용자/테넌트 범위를 먼저 확정합니다.
- DB 변경 명령은 soft delete, audit log, 공통 에러 응답 정책을 따라야 합니다.
- 한 메시지에 여러 의도가 섞일 수 있으므로, 파괴적이거나 저장이 발생하는 명령은 사용자 확인 단계를 둘 수 있어야 합니다.
- `general_sales_agent`는 항상 마지막 fallback이어야 합니다.

## 테스트 체크리스트

- 새 command case가 예상 메시지를 정확히 라우팅하는가
- 기존 command case의 메시지를 빼앗지 않는가
- 고객 선확인이 필요한 명령에서 후보가 여러 건이면 실행이 멈추는가
- 단일 후보는 자동 선택되어 원래 명령으로 이어지는가
- DB 오류가 공통 `error_code`와 `request_id`를 포함하는가
- 감사 로그에 `ask / agent`와 `route / agent_command`가 남는가

## 운영 관찰 포인트

- `audit_logs.action = 'route'`
- `audit_logs.entity_type = 'agent_command'`
- `after_json.case_id`
- `after_json.handler_name`
- `after_json.requires_customer_preflight`

이 로그를 보면 실제 사용자가 어떤 종류의 대화 명령을 많이 쓰는지, 어떤 케이스가 fallback으로 빠지는지, 새 command case가 필요한 지점을 찾을 수 있습니다.
