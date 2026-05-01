from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable


Matcher = Callable[[str], bool]


@dataclass(frozen=True)
class AgentCommandCase:
    """A source-controlled command case handled from the agent chat box."""

    case_id: str
    title: str
    category: str
    priority: int
    handler_name: str
    description: str
    matcher: Matcher
    requires_customer_preflight: bool
    audit_action: str
    audit_entity_type: str
    flow_steps: tuple[str, ...]
    test_points: tuple[str, ...]


@dataclass(frozen=True)
class AgentCommandRoute:
    case_id: str
    title: str
    handler_name: str
    category: str
    priority: int
    matched: bool
    requires_customer_preflight: bool


SOCIAL_URL_RE = re.compile(
    r"https?://[^\s<>'\"]*"
    r"(linkedin\.com|facebook\.com|instagram\.com|twitter\.com|x\.com|youtube\.com|blog\.naver\.com|naver\.me)"
    r"[^\s<>'\"]*",
    re.IGNORECASE,
)

SALES_ACTIVITY_INTENT_RE = re.compile(r"(일정|영업활동|활동|미팅|회의|방문|전화|통화|콜|메일|데모|시연)")
SALES_ACTIVITY_ACTION_RE = re.compile(
    r"(등록|추가|잡아|생성|예약|만들|넣어|기록|취소|삭제|변경|수정|미뤄|앞당겨|조정|반복|정기|매일|매주|매월|조회|확인|목록|보여)"
)


def matches_social_profile(message: str) -> bool:
    return bool(SOCIAL_URL_RE.search(message or ""))


def matches_sales_activity(message: str) -> bool:
    text = message or ""
    return bool(SALES_ACTIVITY_INTENT_RE.search(text) and SALES_ACTIVITY_ACTION_RE.search(text))


def always_matches(_message: str) -> bool:
    return True


AGENT_COMMAND_CASES: tuple[AgentCommandCase, ...] = (
    AgentCommandCase(
        case_id="sns_profile_research",
        title="SNS 링크 프로필 리서치",
        category="research",
        priority=20,
        handler_name="handle_sns_profile_research",
        description="LinkedIn, Facebook, Instagram 등 SNS 링크를 판별하고 공개 프로필 메타 정보를 확인한다.",
        matcher=matches_social_profile,
        requires_customer_preflight=True,
        audit_action="inspect",
        audit_entity_type="sns",
        flow_steps=(
            "메시지에서 지원 SNS 링크를 추출한다.",
            "요청당 링크 수 제한을 확인한다.",
            "플랫폼과 프로필 유형을 분류한다.",
            "공개 메타데이터를 조회하고 이름 후보와 신뢰도를 계산한다.",
            "저장은 확정 가능한 정보에 한정하고, 불확실한 정보는 사용자 확인 대상으로 돌려준다.",
        ),
        test_points=(
            "지원 SNS 도메인이 command case로 라우팅되는지 확인한다.",
            "링크 수 제한과 외부 조회 실패가 공통 에러 응답을 사용하는지 확인한다.",
            "불확실한 프로필 이름은 저장되지 않고 확인 요청으로 남는지 확인한다.",
        ),
    ),
    AgentCommandCase(
        case_id="sales_activity_schedule",
        title="영업활동 일정 관리",
        category="sales_activity",
        priority=30,
        handler_name="handle_sales_activity_schedule",
        description="고객 언급이 포함된 일정 등록, 취소, 날짜 변경, 반복 일정, 일정 조회 요청을 처리한다.",
        matcher=matches_sales_activity,
        requires_customer_preflight=True,
        audit_action="manage",
        audit_entity_type="sales_activity",
        flow_steps=(
            "회사명 또는 고객명 언급 여부를 확인하고 고객 후보를 먼저 조회한다.",
            "후보가 여러 건이면 사용자 선택을 요청하고 명령 실행을 보류한다.",
            "후보가 한 건이면 선택 고객 컨텍스트를 주입한다.",
            "등록, 취소, 변경, 반복, 조회 의도를 판별한다.",
            "영업활동 DB에 반영하고 캘린더 화면에서 확인 가능한 응답을 반환한다.",
        ),
        test_points=(
            "고객 후보가 여러 건일 때 명령 실행 전 선택 요청으로 멈추는지 확인한다.",
            "단일 후보는 자동 선택되어 일정 처리로 이어지는지 확인한다.",
            "반복 일정 개수 제한과 날짜 변경 파싱이 유지되는지 확인한다.",
        ),
    ),
    AgentCommandCase(
        case_id="general_sales_agent",
        title="일반 세일즈 에이전트 대화",
        category="llm",
        priority=1000,
        handler_name="handle_general_sales_agent",
        description="명시적인 업무 명령으로 분류되지 않은 질문을 LLM과 검색 기반 답변으로 처리한다.",
        matcher=always_matches,
        requires_customer_preflight=True,
        audit_action="ask",
        audit_entity_type="agent",
        flow_steps=(
            "현재 세션과 선택 고객 컨텍스트를 정리한다.",
            "필요하면 검색 도구로 최신 정보를 보강한다.",
            "영업 관점의 실행 가능한 답변을 한국어로 생성한다.",
        ),
        test_points=(
            "앞선 command case에 매칭되지 않은 메시지가 fallback으로 라우팅되는지 확인한다.",
            "선택 고객 컨텍스트가 최신 고객보다 우선되는지 확인한다.",
        ),
    ),
)


def route_agent_command(message: str) -> AgentCommandRoute:
    for command_case in sorted(AGENT_COMMAND_CASES, key=lambda item: item.priority):
        if command_case.matcher(message):
            return AgentCommandRoute(
                case_id=command_case.case_id,
                title=command_case.title,
                handler_name=command_case.handler_name,
                category=command_case.category,
                priority=command_case.priority,
                matched=command_case.case_id != "general_sales_agent",
                requires_customer_preflight=command_case.requires_customer_preflight,
            )
    raise RuntimeError("Agent command registry must include a fallback command case.")


def command_case_by_id(case_id: str) -> AgentCommandCase:
    for command_case in AGENT_COMMAND_CASES:
        if command_case.case_id == case_id:
            return command_case
    raise KeyError(case_id)


def command_cases_for_docs() -> list[dict[str, Any]]:
    return [
        {
            "case_id": command_case.case_id,
            "title": command_case.title,
            "category": command_case.category,
            "priority": command_case.priority,
            "handler_name": command_case.handler_name,
            "description": command_case.description,
            "requires_customer_preflight": command_case.requires_customer_preflight,
            "audit_action": command_case.audit_action,
            "audit_entity_type": command_case.audit_entity_type,
            "flow_steps": list(command_case.flow_steps),
            "test_points": list(command_case.test_points),
        }
        for command_case in sorted(AGENT_COMMAND_CASES, key=lambda item: item.priority)
    ]
