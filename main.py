from pathlib import Path
import base64
from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
import hmac
import html as html_lib
import io
import os
import json
import re
import secrets
import time
from typing import Any
from urllib.parse import unquote, urlparse, urlunparse
from urllib.request import Request as UrlRequest, urlopen
from xml.etree import ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import mysql.connector
from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent_commands import command_cases_for_docs, route_agent_command
from database import contact_row_to_customer, db_connection, init_db, none_if_blank, resolve_tenant_id


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
extra_env_path = os.getenv("FSAI_EXTRA_ENV_PATH")
if extra_env_path:
    load_dotenv(Path(extra_env_path))

if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from graph import app_graph, content_to_text, create_gemini_model

app = FastAPI(title="FingerSalesAI")

ERROR_MESSAGES = {
    "FSI-VALIDATION": "입력값을 확인해 주세요.",
    "FSI-AUTH-REQUIRED": "로그인이 필요합니다.",
    "FSI-AUTH-FORBIDDEN": "권한이 부족합니다.",
    "FSI-NOT-FOUND": "요청한 데이터를 찾지 못했습니다.",
    "FSI-DB-DUPLICATE": "이미 등록된 데이터와 중복됩니다.",
    "FSI-DB-RELATION": "연결된 데이터가 없거나 참조 관계가 올바르지 않습니다.",
    "FSI-DB-CONNECTION": "데이터베이스 연결에 실패했습니다.",
    "FSI-DB-TIMEOUT": "데이터베이스 응답이 지연되거나 잠금이 발생했습니다.",
    "FSI-DB-ERROR": "데이터베이스 처리 중 오류가 발생했습니다.",
    "FSI-SYSTEM-ERROR": "시스템 처리 중 오류가 발생했습니다.",
}

MYSQL_ERROR_MAP = {
    1062: ("FSI-DB-DUPLICATE", 409, "중복 키 오류입니다. 같은 코드, 이메일, 문서번호, 이름 등이 이미 등록되어 있는지 확인해 주세요."),
    1451: ("FSI-DB-RELATION", 409, "다른 데이터가 이 항목을 참조하고 있어 처리할 수 없습니다. 삭제 대신 비활성/소프트 삭제가 필요한지 확인해 주세요."),
    1452: ("FSI-DB-RELATION", 400, "연결하려는 고객, 사용자, 영업기회, 견적 등 참조 데이터가 존재하지 않습니다."),
    1045: ("FSI-DB-CONNECTION", 503, "DB 계정 인증에 실패했습니다. MYSQL_USER/MYSQL_PASSWORD 설정을 확인해 주세요."),
    1049: ("FSI-DB-CONNECTION", 503, "DB 스키마를 찾을 수 없습니다. MYSQL_DATABASE 설정과 MySQL 생성 상태를 확인해 주세요."),
    1205: ("FSI-DB-TIMEOUT", 503, "DB 잠금 대기 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."),
    1213: ("FSI-DB-TIMEOUT", 503, "DB 데드락이 감지되었습니다. 트랜잭션은 롤백되었으니 다시 시도해 주세요."),
    2002: ("FSI-DB-CONNECTION", 503, "DB 서버에 연결할 수 없습니다. MySQL 서비스와 호스트/포트를 확인해 주세요."),
    2003: ("FSI-DB-CONNECTION", 503, "DB 서버에 연결할 수 없습니다. MySQL 서비스와 호스트/포트를 확인해 주세요."),
    2006: ("FSI-DB-CONNECTION", 503, "DB 연결이 끊어졌습니다. 잠시 후 다시 시도해 주세요."),
    2013: ("FSI-DB-CONNECTION", 503, "DB 응답 중 연결이 끊어졌습니다. 잠시 후 다시 시도해 주세요."),
}

APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}
SESSION_COOKIE_NAME = "fsai_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12
SESSION_SECRET = os.getenv("APP_SESSION_SECRET", "")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true" if IS_PRODUCTION else "false").lower() == "true"
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax")
MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))
AUTH_RATE_LIMIT_MAX = int(os.getenv("AUTH_RATE_LIMIT_MAX", "10"))
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60"))
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"
ALLOW_EXISTING_TENANT_SELF_JOIN = os.getenv("ALLOW_EXISTING_TENANT_SELF_JOIN", "false").lower() == "true"
TENANT_JOIN_CODE = os.getenv("TENANT_JOIN_CODE", "")
TENANT_SELF_JOIN_ROLES = {"sales", "viewer"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
MAX_SNS_LINKS_PER_REQUEST = int(os.getenv("MAX_SNS_LINKS_PER_REQUEST", "3"))
SOCIAL_FETCH_TIMEOUT_SECONDS = float(os.getenv("SOCIAL_FETCH_TIMEOUT_SECONDS", "3"))
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Seoul")
MAX_RECURRING_ACTIVITY_COUNT = int(os.getenv("MAX_RECURRING_ACTIVITY_COUNT", "24"))
DOCUMENT_UPLOAD_DIR = Path(os.getenv("DOCUMENT_UPLOAD_DIR", str(BASE_DIR / "uploads" / "documents")))
MAX_DOCUMENT_TEXT_CHARS = int(os.getenv("MAX_DOCUMENT_TEXT_CHARS", "60000"))
_auth_attempts: dict[str, list[float]] = {}
ADMIN_ROLES = {"owner", "admin"}
USER_STATUS_VALUES = {"active", "invited", "locked", "disabled"}
TENANT_STATUS_VALUES = {"active", "trial", "suspended", "closed"}
PIPELINE_STAGE_CODES = {"lead", "prospect", "opportunity", "proposal", "contract", "success"}
CUSTOM_CODES_SETTING_KEY = "custom_codes"
TEAM_LEADERS_SETTING_KEY = "team_leaders"
DEFAULT_PIPELINE_STAGES = [
    {"stage_code": "lead", "name": "잠재고객", "description": "초기 유입 또는 관심이 확인된 고객", "probability_percent": 5, "sort_order": 10},
    {"stage_code": "prospect", "name": "가망고객", "description": "영업 대상성과 접근 가능성이 확인된 고객", "probability_percent": 15, "sort_order": 20},
    {"stage_code": "opportunity", "name": "기회인지", "description": "구체적인 니즈와 영업 기회가 식별된 단계", "probability_percent": 35, "sort_order": 30},
    {"stage_code": "proposal", "name": "제안/견적", "description": "제안서 또는 견적이 준비되거나 전달된 단계", "probability_percent": 60, "sort_order": 40},
    {"stage_code": "contract", "name": "계약/실행", "description": "계약 협의, 체결, 실행 준비 단계", "probability_percent": 85, "sort_order": 50},
    {"stage_code": "success", "name": "사후관리", "description": "계약 이후 고객 성공과 후속 영업 관리 단계", "probability_percent": 100, "sort_order": 60},
]
ADMIN_ENTITY_SELECTS = {
    "users": "id, tenant_id, team_id, email, name, phone, role, status, last_login_at, created_at, updated_at, deleted_at",
    "teams": "id, tenant_id, parent_team_id, name, description, sort_order, created_at, updated_at, deleted_at",
    "pipeline_stages": "id, tenant_id, stage_code, name, description, probability_percent, sort_order, is_active, created_at, updated_at, deleted_at",
}

if IS_PRODUCTION and len(SESSION_SECRET) < 32:
    raise RuntimeError("APP_SESSION_SECRET must be set to at least 32 characters in production.")
if not SESSION_SECRET:
    SESSION_SECRET = "dev-only-change-me"

allowed_hosts = [host.strip() for host in os.getenv("APP_ALLOWED_HOSTS", "").split(",") if host.strip()]
if allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

USER_ROLES = {
    "owner": "소유자",
    "admin": "관리자",
    "manager": "매니저",
    "sales": "영업",
    "viewer": "조회",
}

CARD_BASE_KEYS = {
    "회사명": "company_name",
    "이름": "contact_name",
    "직무": "job_title",
    "직위": "job_position",
    "휴대전화": "mobile_phone",
    "이메일": "email",
    "홈페이지": "homepage",
}

SOCIAL_PLATFORM_HOSTS = {
    "linkedin.com": "LinkedIn",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "instagram.com": "Instagram",
    "x.com": "X",
    "twitter.com": "X",
    "threads.net": "Threads",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "tiktok.com": "TikTok",
    "github.com": "GitHub",
    "blog.naver.com": "Naver Blog",
    "medium.com": "Medium",
}

SOCIAL_URL_RE = re.compile(
    r"(?:https?://)?(?:[a-z0-9-]+\.)*"
    r"(?:linkedin\.com|facebook\.com|fb\.com|instagram\.com|x\.com|twitter\.com|threads\.net|"
    r"youtube\.com|youtu\.be|tiktok\.com|github\.com|naver\.com|medium\.com)"
    r"/[^\s<>()\"']*",
    re.IGNORECASE,
)


class ChatRequest(BaseModel):
    message: str
    context: dict[str, Any] | None = None


class SnsLinksRequest(BaseModel):
    message: str
    context: dict[str, Any] | None = None


class SocialProfileScreenshotInfo(BaseModel):
    is_social_profile: bool = Field(description="True only if the image is a social network profile screen.")
    platform: str = Field(default="", description="Visible SNS platform name such as Facebook, LinkedIn, Instagram, X.")
    display_name: str = Field(default="", description="Exact visible main profile person name. Empty if not visible.")
    headline: str = Field(default="", description="Visible role, headline, or short intro. Empty if not visible.")
    company_name: str = Field(default="", description="Visible current company or organization. Empty if not visible.")
    profile_url: str = Field(default="", description="Visible profile URL if shown in the screenshot. Empty if not visible.")
    summary: str = Field(default="", description="Short Korean summary of only visible profile facts.")


class SalesDocumentInfo(BaseModel):
    document_type: str = Field(
        default="unknown",
        description="One of quote, contract, unknown. quote means quotation/estimate/proposal price document. contract means signed/agreement contract document.",
    )
    document_no: str = Field(default="", description="Quote number or contract number. Empty if missing.")
    title: str = Field(default="", description="Short title of the quote or contract.")
    company_name: str = Field(default="", description="Customer company name.")
    contact_name: str = Field(default="", description="Customer contact person name. Empty if missing.")
    currency: str = Field(default="KRW", description="ISO currency code such as KRW or USD.")
    subtotal_amount: float = Field(default=0, description="Subtotal amount for quote. 0 if missing.")
    discount_amount: float = Field(default=0, description="Discount amount for quote. 0 if missing.")
    tax_amount: float = Field(default=0, description="Tax/VAT amount. 0 if missing.")
    total_amount: float = Field(default=0, description="Total quote or contract amount. 0 if missing.")
    valid_until: str = Field(default="", description="Quote valid until date in YYYY-MM-DD. Empty if missing.")
    sent_at: str = Field(default="", description="Quote sent date/datetime in ISO format. Empty if missing.")
    start_date: str = Field(default="", description="Contract start date in YYYY-MM-DD. Empty if missing.")
    end_date: str = Field(default="", description="Contract end date in YYYY-MM-DD. Empty if missing.")
    signed_at: str = Field(default="", description="Contract signed date/datetime in ISO format. Empty if missing.")
    summary: str = Field(default="", description="Short Korean summary of extracted evidence.")


class LoginRequest(BaseModel):
    tenant_code: str
    email: str
    password: str


class RegisterRequest(BaseModel):
    tenant_code: str
    tenant_name: str = ""
    name: str
    email: str
    password: str
    role: str = "sales"
    join_code: str = ""


class CustomerPayload(BaseModel):
    tenant_id: int | None = None
    owner_user_id: int | None = None
    company_name: str = ""
    contact_name: str = ""
    job_title: str = ""
    job_position: str = ""
    mobile_phone: str = ""
    phone: str = ""
    email: str = ""
    homepage: str = ""
    industry: str = ""
    business_no: str = ""
    address: str = ""
    is_primary: bool = False
    extra_info: dict[str, Any] | None = None
    card_data: dict[str, Any] | None = None
    briefing: str = ""
    source_file: str = ""


class AdminCompanyPayload(BaseModel):
    name: str = ""
    business_no: str = ""
    plan_code: str = ""
    timezone: str = "Asia/Seoul"
    locale: str = "ko-KR"


class AdminUserPayload(BaseModel):
    name: str = ""
    phone: str = ""
    role: str = "sales"
    status: str = "active"
    team_id: int | None = None


class AdminInviteUserPayload(BaseModel):
    email: str
    name: str
    phone: str = ""
    role: str = "sales"
    team_id: int | None = None


class AdminTeamPayload(BaseModel):
    name: str = ""
    description: str = ""
    parent_team_id: int | None = None
    leader_user_id: int | None = None
    member_user_ids: list[int] = Field(default_factory=list)
    sort_order: int = 0


class AdminPipelineStagePayload(BaseModel):
    stage_code: str = "lead"
    name: str = ""
    description: str = ""
    probability_percent: float = 0
    sort_order: int = 0
    is_active: bool = True


class AdminCodeItemPayload(BaseModel):
    code: str = ""
    name: str = ""
    description: str = ""
    sort_order: int = 0
    is_active: bool = True


class AdminCodeGroupPayload(BaseModel):
    group_code: str = ""
    name: str = ""
    description: str = ""
    sort_order: int = 0
    is_active: bool = True
    items: list[AdminCodeItemPayload] = Field(default_factory=list)


class AdminCodesPayload(BaseModel):
    groups: list[AdminCodeGroupPayload] = Field(default_factory=list)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or secrets.token_hex(12)
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        raise
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if IS_PRODUCTION:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "요청을 처리할 수 없습니다."
    if exc.status_code == 401:
        error_code = "FSI-AUTH-REQUIRED"
    elif exc.status_code == 403:
        error_code = "FSI-AUTH-FORBIDDEN"
    elif exc.status_code == 404:
        error_code = "FSI-NOT-FOUND"
    elif exc.status_code in {400, 409, 413, 422, 429}:
        error_code = "FSI-VALIDATION"
    else:
        error_code = "FSI-SYSTEM-ERROR"
    return error_response(detail, exc.status_code, error_code, request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = [
        {
            "field": ".".join(str(part) for part in error.get("loc", []) if part != "body"),
            "message": error.get("msg", ""),
            "type": error.get("type", ""),
        }
        for error in exc.errors()
    ]
    return error_response(ERROR_MESSAGES["FSI-VALIDATION"], 422, "FSI-VALIDATION", request, details)


@app.exception_handler(mysql.connector.Error)
async def mysql_exception_handler(request: Request, exc: mysql.connector.Error):
    return database_error_response(exc, request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled error request_id={request_id_from(request)}: {exc}")
    return error_response(ERROR_MESSAGES["FSI-SYSTEM-ERROR"], 500, "FSI-SYSTEM-ERROR", request)


def client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if TRUST_PROXY_HEADERS and forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_auth_rate_limit(request: Request, bucket: str) -> None:
    now = time.time()
    key = f"{bucket}:{client_ip(request)}"
    attempts = [timestamp for timestamp in _auth_attempts.get(key, []) if now - timestamp < AUTH_RATE_LIMIT_WINDOW_SECONDS]
    if len(attempts) >= AUTH_RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="잠시 후 다시 시도해 주세요.")
    attempts.append(now)
    _auth_attempts[key] = attempts


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_session_token(session: dict[str, Any]) -> str:
    payload = {
        **session,
        "exp": int(time.time()) + SESSION_MAX_AGE_SECONDS,
    }
    payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload_part = b64url_encode(payload_bytes)
    signature = hmac.new(SESSION_SECRET.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_part}.{b64url_encode(signature)}"


def read_session_token(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    payload_part, signature_part = token.split(".", 1)
    expected = hmac.new(SESSION_SECRET.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    try:
        received = b64url_decode(signature_part)
        if not hmac.compare_digest(expected, received):
            return None
        payload = json.loads(b64url_decode(payload_part).decode("utf-8"))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def active_session_from_db(session: dict[str, Any] | None) -> dict[str, Any] | None:
    if not session:
        return None
    try:
        tenant_id = int(session.get("tenant_id"))
        user_id = int(session.get("user_id"))
    except Exception:
        return None

    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id AS user_id,
                u.tenant_id,
                u.email,
                u.name AS user_name,
                u.role,
                u.status AS user_status,
                t.tenant_code,
                t.name AS tenant_name,
                t.status AS tenant_status
            FROM users u
            JOIN tenants t
              ON t.id = u.tenant_id
             AND t.deleted_at IS NULL
            WHERE u.id = %s
              AND u.tenant_id = %s
              AND u.deleted_at IS NULL
            LIMIT 1
            """,
            (user_id, tenant_id),
        )
        row = cursor.fetchone()

    if not row or row["user_status"] != "active" or row["tenant_status"] not in ("active", "trial"):
        return None
    return public_session(row)


def get_session(request: Request) -> dict[str, Any] | None:
    token_session = read_session_token(request.cookies.get(SESSION_COOKIE_NAME))
    return active_session_from_db(token_session)


def require_session(request: Request) -> dict[str, Any]:
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Login required")
    return session


def require_admin_session(request: Request) -> dict[str, Any]:
    session = require_session(request)
    if session.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return session


def admin_json_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def admin_json_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: admin_json_value(value) for key, value in row.items()}


def admin_json_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [admin_json_row(row) for row in rows]


def ensure_admin_target_belongs(cursor, table: str, entity_id: int, tenant_id: int) -> dict[str, Any]:
    columns = ADMIN_ENTITY_SELECTS.get(table)
    if not columns:
        raise HTTPException(status_code=500, detail="관리자 대상 테이블 정의가 없습니다.")
    cursor.execute(
        f"""
        SELECT {columns}
        FROM {table}
        WHERE id = %s
          AND tenant_id = %s
          AND deleted_at IS NULL
        LIMIT 1
        """,
        (entity_id, tenant_id),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="대상을 찾지 못했습니다.")
    return row


def write_audit_log(
    cursor,
    session: dict[str, Any],
    action: str,
    entity_type: str,
    entity_id: int | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    request: Request | None = None,
) -> None:
    user_agent = request.headers.get("user-agent", "")[:255] if request else ""
    ip_address = client_ip(request)[:45] if request else ""
    cursor.execute(
        """
        INSERT INTO audit_logs (
            tenant_id, actor_user_id, action, entity_type, entity_id,
            request_id, ip_address, user_agent, before_json, after_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            session["tenant_id"],
            session["user_id"],
            action,
            entity_type,
            entity_id,
            request_id_from(request),
            ip_address,
            user_agent,
            json.dumps(admin_json_row(before or {}), ensure_ascii=False),
            json.dumps(admin_json_row(after or {}), ensure_ascii=False),
        ),
    )


def record_audit_event(
    session: dict[str, Any] | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    if not session:
        return
    try:
        with db_connection() as connection:
            cursor = connection.cursor()
            write_audit_log(cursor, session, action, entity_type, entity_id, before, after, request)
    except Exception as error:
        print("Audit log write failed:", error)


def parse_custom_codes_setting(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {"groups": []}
    if isinstance(value, dict):
        source = value
    else:
        try:
            source = json.loads(value)
        except Exception:
            source = {}
    groups = source.get("groups") if isinstance(source, dict) else []
    return {"groups": groups if isinstance(groups, list) else []}


def normalize_code_token(value: str, label: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_-]+", "_", (value or "").strip()).strip("_").lower()
    if not token:
        raise HTTPException(status_code=400, detail=f"{label} 코드를 입력해 주세요.")
    if len(token) > 80:
        raise HTTPException(status_code=400, detail=f"{label} 코드는 80자 이하로 입력해 주세요.")
    return token


def normalized_custom_codes(payload: AdminCodesPayload) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    seen_groups: set[str] = set()
    for group in payload.groups:
        group_code = normalize_code_token(group.group_code, "그룹")
        if group_code in seen_groups:
            raise HTTPException(status_code=400, detail=f"중복된 코드 그룹입니다: {group_code}")
        seen_groups.add(group_code)
        if not group.name.strip():
            raise HTTPException(status_code=400, detail="코드 그룹 이름을 입력해 주세요.")

        items: list[dict[str, Any]] = []
        seen_items: set[str] = set()
        for item in group.items:
            item_code = normalize_code_token(item.code, "항목")
            if item_code in seen_items:
                raise HTTPException(status_code=400, detail=f"{group_code} 그룹에 중복된 코드 항목이 있습니다: {item_code}")
            seen_items.add(item_code)
            if not item.name.strip():
                raise HTTPException(status_code=400, detail="코드 항목 이름을 입력해 주세요.")
            items.append(
                {
                    "code": item_code,
                    "name": item.name.strip(),
                    "description": item.description.strip(),
                    "sort_order": item.sort_order,
                    "is_active": bool(item.is_active),
                }
            )

        groups.append(
            {
                "group_code": group_code,
                "name": group.name.strip(),
                "description": group.description.strip(),
                "sort_order": group.sort_order,
                "is_active": bool(group.is_active),
                "items": sorted(items, key=lambda row: (row["sort_order"], row["code"])),
            }
        )

    return {"groups": sorted(groups, key=lambda row: (row["sort_order"], row["group_code"]))}


def fetch_custom_codes(cursor, tenant_id: int) -> tuple[int | None, dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, setting_value
        FROM tenant_settings
        WHERE tenant_id = %s
          AND setting_key = %s
        LIMIT 1
        """,
        (tenant_id, CUSTOM_CODES_SETTING_KEY),
    )
    row = cursor.fetchone()
    if not row:
        return None, {"groups": []}
    return row["id"], parse_custom_codes_setting(row.get("setting_value"))


def parse_team_leaders_setting(value: Any) -> dict[str, int]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        source = value
    else:
        try:
            source = json.loads(value)
        except Exception:
            source = {}
    leaders = source.get("leaders") if isinstance(source, dict) else {}
    if not isinstance(leaders, dict):
        return {}
    result: dict[str, int] = {}
    for team_id, user_id in leaders.items():
        try:
            result[str(int(team_id))] = int(user_id)
        except Exception:
            continue
    return result


def fetch_team_leaders(cursor, tenant_id: int) -> tuple[int | None, dict[str, int]]:
    cursor.execute(
        """
        SELECT id, setting_value
        FROM tenant_settings
        WHERE tenant_id = %s
          AND setting_key = %s
        LIMIT 1
        """,
        (tenant_id, TEAM_LEADERS_SETTING_KEY),
    )
    row = cursor.fetchone()
    if not row:
        return None, {}
    return row["id"], parse_team_leaders_setting(row.get("setting_value"))


def save_team_leaders(cursor, tenant_id: int, leaders: dict[str, int]) -> int:
    normalized = {str(int(team_id)): int(user_id) for team_id, user_id in leaders.items() if user_id}
    setting_value = json.dumps({"leaders": normalized}, ensure_ascii=False)
    cursor.execute(
        """
        SELECT id
        FROM tenant_settings
        WHERE tenant_id = %s
          AND setting_key = %s
        LIMIT 1
        """,
        (tenant_id, TEAM_LEADERS_SETTING_KEY),
    )
    row = cursor.fetchone()
    if row:
        cursor.execute(
            """
            UPDATE tenant_settings
            SET setting_value = %s,
                description = %s
            WHERE id = %s
              AND tenant_id = %s
            """,
            (setting_value, "관리자 팀장 지정 정보", row["id"], tenant_id),
        )
        return row["id"]
    cursor.execute(
        """
        INSERT INTO tenant_settings (tenant_id, setting_key, setting_value, description)
        VALUES (%s, %s, %s, %s)
        """,
        (tenant_id, TEAM_LEADERS_SETTING_KEY, setting_value, "관리자 팀장 지정 정보"),
    )
    return cursor.lastrowid


def ensure_admin_user_belongs(cursor, user_id: int, tenant_id: int) -> dict[str, Any]:
    return ensure_admin_target_belongs(cursor, "users", user_id, tenant_id)


def validate_team_members(cursor, user_ids: list[int], tenant_id: int) -> list[int]:
    unique_ids = sorted({int(user_id) for user_id in user_ids if user_id})
    if not unique_ids:
        return []
    placeholders = ",".join(["%s"] * len(unique_ids))
    cursor.execute(
        f"""
        SELECT id
        FROM users
        WHERE tenant_id = %s
          AND deleted_at IS NULL
          AND id IN ({placeholders})
        """,
        (tenant_id, *unique_ids),
    )
    found = {row["id"] for row in cursor.fetchall()}
    missing = set(unique_ids) - found
    if missing:
        raise HTTPException(status_code=400, detail="팀원으로 배정할 수 없는 사용자가 포함되어 있습니다.")
    return unique_ids


def temporary_invite_password() -> str:
    return secrets.token_urlsafe(12)


def request_id_from(request: Request | None) -> str:
    if not request:
        return ""
    return str(getattr(request.state, "request_id", "") or request.headers.get("x-request-id") or "")


def error_response(
    message: str,
    status_code: int = 500,
    error_code: str = "FSI-SYSTEM-ERROR",
    request: Request | None = None,
    details: dict[str, Any] | list[Any] | None = None,
) -> JSONResponse:
    request_id = request_id_from(request)
    display_parts = [message]
    if error_code:
        display_parts.append(f"에러코드: {error_code}")
    if request_id:
        display_parts.append(f"요청ID: {request_id}")
    content: dict[str, Any] = {
        "success": False,
        "message": message,
        "error": " / ".join(display_parts),
        "error_code": error_code,
        "request_id": request_id,
    }
    if details is not None:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content)


def internal_error_response(
    message: str = "요청 처리 중 오류가 발생했습니다.",
    status_code: int = 500,
    error_code: str = "FSI-SYSTEM-ERROR",
    request: Request | None = None,
    details: dict[str, Any] | list[Any] | None = None,
) -> JSONResponse:
    return error_response(message, status_code, error_code, request, details)


def classify_mysql_error(error: mysql.connector.Error) -> tuple[str, int, str, dict[str, Any]]:
    errno = int(getattr(error, "errno", 0) or 0)
    sqlstate = getattr(error, "sqlstate", "") or ""
    error_code, status_code, situation = MYSQL_ERROR_MAP.get(errno, ("FSI-DB-ERROR", 500, ERROR_MESSAGES["FSI-DB-ERROR"]))
    details: dict[str, Any] = {
        "db_errno": errno,
        "sqlstate": sqlstate,
        "situation": situation,
        "retriable": error_code in {"FSI-DB-CONNECTION", "FSI-DB-TIMEOUT"},
    }
    if not IS_PRODUCTION:
        details["db_message"] = str(error)[:500]
    return error_code, status_code, situation, details


def database_error_response(error: mysql.connector.Error, request: Request | None = None) -> JSONResponse:
    error_code, status_code, situation, details = classify_mysql_error(error)
    print(f"DB error {error_code} request_id={request_id_from(request)} errno={details.get('db_errno')} sqlstate={details.get('sqlstate')}: {error}")
    return error_response(situation, status_code, error_code, request, details)


def enforce_content_length(request: Request, max_bytes: int) -> None:
    content_length = request.headers.get("content-length")
    if not content_length:
        return
    try:
        if int(content_length) > max_bytes:
            raise HTTPException(status_code=413, detail=f"업로드 파일은 {max_bytes // (1024 * 1024)}MB 이하만 허용됩니다.")
    except ValueError:
        raise HTTPException(status_code=400, detail="Content-Length 헤더가 올바르지 않습니다.")


async def read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail=f"업로드 파일은 {max_bytes // (1024 * 1024)}MB 이하만 허용됩니다.")
    return contents


DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"}
DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    "application/csv",
}


def safe_original_filename(filename: str | None) -> str:
    name = Path(filename or "uploaded-document").name.strip()
    return re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "_", name)[:180] or "uploaded-document"


def upload_extension(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


def is_supported_document_upload(file: UploadFile) -> bool:
    extension = upload_extension(file.filename)
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    return extension in DOCUMENT_EXTENSIONS or content_type in DOCUMENT_CONTENT_TYPES


def zip_xml_text(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return ""
    parts = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] in {"t", "instrText"} and node.text:
            parts.append(node.text)
        elif node.tag.rsplit("}", 1)[-1] in {"p", "tr"}:
            parts.append("\n")
    return " ".join(part.strip() for part in parts if part and part.strip())


def extract_docx_text(contents: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            chunks = []
            for name in archive.namelist():
                if name == "word/document.xml" or name.startswith("word/header") or name.startswith("word/footer"):
                    chunks.append(zip_xml_text(archive.read(name)))
            return "\n".join(chunk for chunk in chunks if chunk)
    except Exception:
        return ""


def extract_xlsx_text(contents: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                for item in root.iter():
                    if item.tag.rsplit("}", 1)[-1] == "si":
                        text = " ".join(
                            node.text.strip()
                            for node in item.iter()
                            if node.tag.rsplit("}", 1)[-1] == "t" and node.text
                        )
                        shared_strings.append(text)

            rows = []
            sheet_names = sorted(name for name in archive.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", name))
            for sheet_name in sheet_names[:10]:
                root = ET.fromstring(archive.read(sheet_name))
                for row in root.iter():
                    if row.tag.rsplit("}", 1)[-1] != "row":
                        continue
                    values = []
                    for cell in row:
                        if cell.tag.rsplit("}", 1)[-1] != "c":
                            continue
                        cell_type = cell.attrib.get("t")
                        value = ""
                        for child in cell:
                            if child.tag.rsplit("}", 1)[-1] == "v" and child.text:
                                value = child.text
                                break
                            if child.tag.rsplit("}", 1)[-1] == "is":
                                value = " ".join(
                                    node.text.strip()
                                    for node in child.iter()
                                    if node.tag.rsplit("}", 1)[-1] == "t" and node.text
                                )
                        if cell_type == "s" and value.isdigit():
                            index = int(value)
                            value = shared_strings[index] if 0 <= index < len(shared_strings) else value
                        if value:
                            values.append(value)
                    if values:
                        rows.append(" | ".join(values))
            return "\n".join(rows)
    except Exception:
        return ""


def extract_pdf_text(contents: bytes) -> str:
    # Dependency-free fallback for simple text PDFs. Scanned PDFs are handled by Gemini media input when available.
    raw = contents.decode("latin-1", errors="ignore")
    literals = re.findall(r"\((.{1,500}?)\)\s*T[Jj]", raw, flags=re.DOTALL)
    cleaned = []
    for literal in literals:
        text = literal.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
        text = re.sub(r"\\[nrtbf]", " ", text)
        if re.search(r"[A-Za-z가-힣0-9]", text):
            cleaned.append(text)
    if cleaned:
        return "\n".join(cleaned)
    visible = re.sub(r"[^A-Za-z0-9가-힣.,:;/%()\\-+₩$\\s]", " ", raw)
    return re.sub(r"\s+", " ", visible)[:12000]


def extract_document_text(contents: bytes, filename: str, content_type: str | None) -> str:
    extension = upload_extension(filename)
    if extension == ".docx":
        return extract_docx_text(contents)
    if extension == ".xlsx":
        return extract_xlsx_text(contents)
    if extension == ".pdf":
        return extract_pdf_text(contents)
    if extension in {".doc", ".xls"}:
        return re.sub(r"\s+", " ", contents.decode("latin-1", errors="ignore"))
    if extension in {".txt", ".csv"} or (content_type or "").startswith("text/"):
        for encoding in ("utf-8-sig", "utf-8", "cp949", "latin-1"):
            try:
                return contents.decode(encoding)
            except Exception:
                continue
    return contents.decode("utf-8", errors="ignore")


def normalize_currency(value: str | None) -> str:
    text = str(value or "").upper().strip()
    if "USD" in text or "$" in text:
        return "USD"
    if "EUR" in text:
        return "EUR"
    if "JPY" in text:
        return "JPY"
    return "KRW"


def decimal_amount(value: Any) -> Decimal:
    try:
        if value is None:
            return Decimal("0")
        text = str(value).replace(",", "").replace("₩", "").replace("$", "").strip()
        return Decimal(text or "0").quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def parse_iso_date(value: str | None) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10].replace("/", "-").replace(".", "-"), "%Y-%m-%d").date()
        except Exception:
            continue
    match = re.search(r"(20\d{2})\D{1,3}(\d{1,2})\D{1,3}(\d{1,2})", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except Exception:
            return None
    return None


def parse_iso_datetime(value: str | None) -> datetime | None:
    parsed_date = parse_iso_date(value)
    return datetime.combine(parsed_date, datetime.min.time()) if parsed_date else None


def heuristic_sales_document_info(text: str, filename: str) -> SalesDocumentInfo:
    combined = f"{filename}\n{text[:12000]}"
    lowered = combined.lower()
    document_type = "unknown"
    if re.search(r"(견적|quotation|quote|estimate|proposal)", lowered, re.IGNORECASE):
        document_type = "quote"
    if re.search(r"(계약|contract|agreement|협약|주문서)", lowered, re.IGNORECASE):
        document_type = "contract"
    amount_matches = re.findall(r"(?:₩|KRW|USD|\$)?\s*([0-9][0-9,]{3,}(?:\.\d{1,2})?)", combined, re.IGNORECASE)
    amount = max((decimal_amount(item) for item in amount_matches), default=Decimal("0"))
    company_match = re.search(r"(?:고객사|거래처|수신|발주처|계약상대방|회사명)\s*[:：]?\s*([^\n\r]{2,80})", combined)
    title = Path(filename).stem[:120]
    return SalesDocumentInfo(
        document_type=document_type,
        title=title,
        company_name=(company_match.group(1).strip() if company_match else ""),
        currency=normalize_currency(combined),
        total_amount=float(amount),
        summary="문서 텍스트 기반 휴리스틱으로 추출했습니다.",
    )


def extract_sales_document_info(contents: bytes, filename: str, content_type: str | None, extracted_text: str) -> SalesDocumentInfo:
    prompt = f"""
    You extract CRM data from uploaded sales documents.
    Classify the document as:
    - quote: quotation, estimate, proposal with price, 견적서
    - contract: contract, agreement, signed order, 계약서
    - unknown: not enough evidence

    Extract only facts present in the document. Do not guess.
    Dates must be YYYY-MM-DD when possible. Currency must be ISO code.
    If a value is missing, return empty string or 0.

    Filename: {filename}

    Extracted text:
    {extracted_text[:MAX_DOCUMENT_TEXT_CHARS]}
    """
    try:
        model = create_gemini_model(temperature=0)
        structured_model = model.with_structured_output(SalesDocumentInfo)
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if upload_extension(filename) == ".pdf":
            content.append(
                {
                    "type": "media",
                    "mime_type": content_type or "application/pdf",
                    "data": base64.b64encode(contents).decode("utf-8"),
                }
            )
        response: SalesDocumentInfo = structured_model.invoke([HumanMessage(content=content)])
        data = response.model_dump()
        if data.get("document_type") not in {"quote", "contract", "unknown"}:
            data["document_type"] = "unknown"
        return SalesDocumentInfo(**data)
    except Exception as error:
        print("Sales document AI extraction failed:", error)
        return heuristic_sales_document_info(extracted_text, filename)


def ensure_pipeline_stage(cursor, tenant_id: int, stage_code: str) -> int:
    cursor.execute(
        """
        SELECT id
        FROM pipeline_stages
        WHERE tenant_id = %s
          AND stage_code = %s
          AND deleted_at IS NULL
        ORDER BY sort_order, id
        LIMIT 1
        """,
        (tenant_id, stage_code),
    )
    row = cursor.fetchone()
    if row:
        return row["id"]
    stage = next((item for item in DEFAULT_PIPELINE_STAGES if item["stage_code"] == stage_code), DEFAULT_PIPELINE_STAGES[0])
    cursor.execute(
        """
        INSERT INTO pipeline_stages (
            tenant_id, stage_code, name, description, probability_percent, sort_order, is_active
        )
        VALUES (%s, %s, %s, %s, %s, %s, 1)
        """,
        (
            tenant_id,
            stage["stage_code"],
            stage["name"],
            stage["description"],
            stage["probability_percent"],
            stage["sort_order"],
        ),
    )
    return cursor.lastrowid


def ensure_document_account(cursor, session: dict[str, Any], info: SalesDocumentInfo, request: Request | None = None) -> int:
    company_name = (info.company_name or "").strip() or "문서 미확인 고객사"
    payload = CustomerPayload(
        tenant_id=session["tenant_id"],
        owner_user_id=session["user_id"],
        company_name=company_name,
    )
    account_id = upsert_account(cursor, payload, session["tenant_id"], session, request)
    if not account_id:
        raise HTTPException(status_code=400, detail="문서에서 고객사 정보를 확인하지 못했습니다.")
    return account_id


def find_document_contact(cursor, session: dict[str, Any], account_id: int, contact_name: str | None) -> int | None:
    name = (contact_name or "").strip()
    if not name:
        return None
    cursor.execute(
        """
        SELECT id
        FROM contacts
        WHERE tenant_id = %s
          AND owner_user_id = %s
          AND account_id = %s
          AND name = %s
          AND deleted_at IS NULL
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (session["tenant_id"], session["user_id"], account_id, name),
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def ensure_document_opportunity(
    cursor,
    session: dict[str, Any],
    info: SalesDocumentInfo,
    account_id: int,
    contact_id: int | None,
    stage_code: str,
    amount: Decimal,
) -> int:
    title = (info.title or info.document_no or "문서 기반 영업기회").strip()[:180]
    stage_id = ensure_pipeline_stage(cursor, session["tenant_id"], stage_code)
    cursor.execute(
        """
        SELECT id
        FROM opportunities
        WHERE tenant_id = %s
          AND owner_user_id = %s
          AND account_id = %s
          AND name = %s
          AND deleted_at IS NULL
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (session["tenant_id"], session["user_id"], account_id, title),
    )
    row = cursor.fetchone()
    if row:
        cursor.execute(
            """
            UPDATE opportunities
            SET contact_id = COALESCE(%s, contact_id),
                pipeline_stage_id = %s,
                amount = GREATEST(amount, %s),
                currency = %s,
                updated_at = NOW(6)
            WHERE id = %s
              AND tenant_id = %s
            """,
            (contact_id, stage_id, amount, normalize_currency(info.currency), row["id"], session["tenant_id"]),
        )
        return row["id"]
    cursor.execute(
        """
        INSERT INTO opportunities (
            tenant_id, owner_user_id, account_id, contact_id, pipeline_stage_id,
            name, amount, currency, probability_percent, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'open')
        """,
        (
            session["tenant_id"],
            session["user_id"],
            account_id,
            contact_id,
            stage_id,
            title,
            amount,
            normalize_currency(info.currency),
            60 if stage_code == "proposal" else 85,
        ),
    )
    return cursor.lastrowid


def generated_document_no(prefix: str) -> str:
    return f"{prefix}-{app_now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3).upper()}"


def stored_document_path(session: dict[str, Any], original_filename: str) -> tuple[Path, str]:
    extension = upload_extension(original_filename)
    stored_filename = f"{session['tenant_id']}_{session['user_id']}_{app_now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(8)}{extension}"
    target_dir = DOCUMENT_UPLOAD_DIR / str(session["tenant_id"]) / str(session["user_id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / stored_filename, stored_filename


def insert_uploaded_document(
    cursor,
    session: dict[str, Any],
    entity_type: str,
    entity_id: int,
    original_filename: str,
    stored_filename: str,
    storage_path: Path,
    content_type: str | None,
    contents: bytes,
    extracted_text: str,
    extracted_info: dict[str, Any],
) -> dict[str, Any]:
    cursor.execute(
        """
        INSERT INTO uploaded_documents (
            tenant_id, owner_user_id, entity_type, entity_id,
            original_filename, stored_filename, storage_path, content_type,
            size_bytes, sha256, extracted_text, extracted_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            session["tenant_id"],
            session["user_id"],
            entity_type,
            entity_id,
            original_filename,
            stored_filename,
            str(storage_path),
            content_type,
            len(contents),
            hashlib.sha256(contents).hexdigest(),
            extracted_text[:MAX_DOCUMENT_TEXT_CHARS],
            json.dumps(extracted_info, ensure_ascii=False),
        ),
    )
    document_id = cursor.lastrowid
    return {
        "id": document_id,
        "original_filename": original_filename,
        "download_url": f"/api/documents/{document_id}/download",
    }


def fetch_quote_row(cursor, quote_id: int, session: dict[str, Any]) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT q.id, q.quote_no, q.title, q.status, q.currency, q.subtotal_amount,
               q.discount_amount, q.tax_amount, q.total_amount, q.valid_until, q.sent_at,
               q.created_at, q.updated_at, a.name AS company_name, c.name AS contact_name,
               o.name AS opportunity_name
        FROM quotes q
        LEFT JOIN accounts a ON a.id = q.account_id AND a.tenant_id = q.tenant_id AND a.deleted_at IS NULL
        LEFT JOIN contacts c ON c.id = q.contact_id AND c.tenant_id = q.tenant_id AND c.deleted_at IS NULL
        LEFT JOIN opportunities o ON o.id = q.opportunity_id AND o.tenant_id = q.tenant_id AND o.deleted_at IS NULL
        WHERE q.id = %s AND q.tenant_id = %s AND q.owner_user_id = %s AND q.deleted_at IS NULL
        """,
        (quote_id, session["tenant_id"], session["user_id"]),
    )
    return cursor.fetchone()


def fetch_contract_row(cursor, contract_id: int, session: dict[str, Any]) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT ct.id, ct.contract_no, ct.title, ct.status, ct.currency, ct.contract_amount,
               ct.start_date, ct.end_date, ct.signed_at, ct.created_at, ct.updated_at,
               a.name AS company_name, c.name AS contact_name, q.quote_no, o.name AS opportunity_name
        FROM contracts ct
        LEFT JOIN accounts a ON a.id = ct.account_id AND a.tenant_id = ct.tenant_id AND a.deleted_at IS NULL
        LEFT JOIN contacts c ON c.id = ct.contact_id AND c.tenant_id = ct.tenant_id AND c.deleted_at IS NULL
        LEFT JOIN quotes q ON q.id = ct.quote_id AND q.tenant_id = ct.tenant_id AND q.deleted_at IS NULL
        LEFT JOIN opportunities o ON o.id = ct.opportunity_id AND o.tenant_id = ct.tenant_id AND o.deleted_at IS NULL
        WHERE ct.id = %s AND ct.tenant_id = %s AND ct.owner_user_id = %s AND ct.deleted_at IS NULL
        """,
        (contract_id, session["tenant_id"], session["user_id"]),
    )
    return cursor.fetchone()


def save_quote_from_document(
    cursor,
    session: dict[str, Any],
    info: SalesDocumentInfo,
    request: Request,
) -> dict[str, Any]:
    account_id = ensure_document_account(cursor, session, info, request)
    contact_id = find_document_contact(cursor, session, account_id, info.contact_name)
    total_amount = decimal_amount(info.total_amount)
    opportunity_id = ensure_document_opportunity(cursor, session, info, account_id, contact_id, "proposal", total_amount)
    quote_no = (info.document_no or "").strip()[:80] or generated_document_no("Q")
    title = (info.title or quote_no or "문서 기반 견적").strip()[:200]
    cursor.execute(
        """
        INSERT INTO quotes (
            tenant_id, opportunity_id, account_id, contact_id, owner_user_id,
            quote_no, title, status, currency, subtotal_amount, discount_amount,
            tax_amount, total_amount, valid_until, sent_at, notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            session["tenant_id"],
            opportunity_id,
            account_id,
            contact_id,
            session["user_id"],
            quote_no,
            title,
            normalize_currency(info.currency),
            decimal_amount(info.subtotal_amount) or total_amount,
            decimal_amount(info.discount_amount),
            decimal_amount(info.tax_amount),
            total_amount,
            parse_iso_date(info.valid_until),
            parse_iso_datetime(info.sent_at),
            info.summary[:1000] if info.summary else None,
        ),
    )
    quote_id = cursor.lastrowid
    after = fetch_quote_row(cursor, quote_id, session)
    write_audit_log(cursor, session, "create", "quote", quote_id, None, after, request)
    return admin_json_row(after or {"id": quote_id})


def save_contract_from_document(
    cursor,
    session: dict[str, Any],
    info: SalesDocumentInfo,
    request: Request,
) -> dict[str, Any]:
    account_id = ensure_document_account(cursor, session, info, request)
    contact_id = find_document_contact(cursor, session, account_id, info.contact_name)
    contract_amount = decimal_amount(info.total_amount)
    opportunity_id = ensure_document_opportunity(cursor, session, info, account_id, contact_id, "contract", contract_amount)
    contract_no = (info.document_no or "").strip()[:80] or generated_document_no("C")
    title = (info.title or contract_no or "문서 기반 계약").strip()[:200]
    cursor.execute(
        """
        INSERT INTO contracts (
            tenant_id, opportunity_id, quote_id, account_id, contact_id, owner_user_id,
            contract_no, title, status, currency, contract_amount,
            start_date, end_date, signed_at, notes
        )
        VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, 'draft', %s, %s, %s, %s, %s, %s)
        """,
        (
            session["tenant_id"],
            opportunity_id,
            account_id,
            contact_id,
            session["user_id"],
            contract_no,
            title,
            normalize_currency(info.currency),
            contract_amount,
            parse_iso_date(info.start_date),
            parse_iso_date(info.end_date),
            parse_iso_datetime(info.signed_at),
            info.summary[:1000] if info.summary else None,
        ),
    )
    contract_id = cursor.lastrowid
    after = fetch_contract_row(cursor, contract_id, session)
    write_audit_log(cursor, session, "create", "contract", contract_id, None, after, request)
    return admin_json_row(after or {"id": contract_id})


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    stored = password_hash.strip()

    if stored.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            import bcrypt

            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False

    if stored.startswith("pbkdf2_sha256$"):
        try:
            _algorithm, iterations, salt, digest = stored.split("$", 3)
            computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
            return (
                hmac.compare_digest(base64.b64encode(computed).decode("ascii"), digest)
                or hmac.compare_digest(b64url_encode(computed), digest)
                or hmac.compare_digest(computed.hex(), digest)
            )
        except Exception:
            return False

    if len(stored) == 64 and all(char in "0123456789abcdefABCDEF" for char in stored):
        return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), stored.lower())

    return False


def hash_password(password: str) -> str:
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def public_session(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "tenant_id": row["tenant_id"],
        "tenant_code": row["tenant_code"],
        "tenant_name": row["tenant_name"],
        "tenant_status": row["tenant_status"],
        "user_id": row["user_id"],
        "user_name": row["user_name"],
        "email": row["email"],
        "role": row["role"],
    }


def role_label(role: str) -> str:
    return USER_ROLES.get(role, role)


def set_session_cookie(response: Response, session: dict[str, Any]) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(session),
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", samesite=SESSION_COOKIE_SAMESITE)
    secure_attr = "; Secure" if SESSION_COOKIE_SECURE else ""
    response.headers.append(
        "set-cookie",
        f"{SESSION_COOKIE_NAME}=; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/; SameSite={SESSION_COOKIE_SAMESITE.capitalize()}; HttpOnly{secure_attr}",
    )
    response.headers.append(
        "set-cookie",
        f"{SESSION_COOKIE_NAME}=; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite={SESSION_COOKIE_SAMESITE.capitalize()}; HttpOnly{secure_attr}",
    )


def first_extra_value(source: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def normalize_card_data(data: dict[str, Any] | None) -> dict[str, Any]:
    source = data or {}
    normalized = {
        "company_name": str(source.get("회사명") or "").strip(),
        "contact_name": str(source.get("이름") or "").strip(),
        "job_title": str(source.get("직무") or "").strip(),
        "job_position": str(source.get("직위") or "").strip(),
        "mobile_phone": str(source.get("휴대전화") or "").strip(),
        "email": str(source.get("이메일") or "").strip(),
        "homepage": str(source.get("홈페이지") or "").strip(),
        "phone": first_extra_value(source, ("전화", "전화번호", "대표전화", "회사전화", "Office", "Tel")),
        "address": first_extra_value(source, ("주소", "회사주소", "소재지", "Address")),
        "business_no": first_extra_value(source, ("사업자등록번호", "사업자번호", "등록번호")),
        "industry": first_extra_value(source, ("산업군", "업종")),
    }
    normalized["extra_info"] = {
        key: value
        for key, value in source.items()
        if key not in CARD_BASE_KEYS and value not in (None, "")
    }
    normalized["card_data"] = source
    return normalized


def clean_url(value: str) -> str:
    return value.strip().rstrip(".,;:!?)]}>\u3002\uff0c\uff1b\uff1a")


def social_platform_for_host(host: str) -> str | None:
    normalized_host = host.lower().removeprefix("www.").removeprefix("m.")
    for domain, platform in SOCIAL_PLATFORM_HOSTS.items():
        if normalized_host == domain or normalized_host.endswith(f".{domain}"):
            return platform
    return None


def normalize_social_url(value: str) -> str:
    cleaned = clean_url(value)
    if not re.match(r"https?://", cleaned, re.IGNORECASE):
        cleaned = f"https://{cleaned}"
    parsed = urlparse(cleaned)
    path = parsed.path.rstrip("/") or "/"
    host = parsed.netloc.lower().removeprefix("www.").removeprefix("m.")
    return urlunparse((parsed.scheme.lower(), host, path, "", parsed.query, ""))


def extract_social_links(text: str) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in SOCIAL_URL_RE.findall(text or ""):
        url = normalize_social_url(match)
        parsed = urlparse(url)
        platform = social_platform_for_host(parsed.netloc)
        if not platform or url in seen:
            continue
        seen.add(url)
        links.append(classify_social_link(url, platform))
    return links


def readable_handle(value: str) -> str:
    text = unquote(value or "").strip().strip("@")
    text = re.sub(r"[-_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or "SNS 프로필"


def social_name_candidate_from_slug(platform: str, entity_type: str, handle: str) -> str:
    if platform != "LinkedIn" or entity_type != "person" or not handle:
        return ""

    decoded = handle.strip("@")
    for _ in range(2):
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded

    tokens = [
        token.strip()
        for token in re.split(r"[-_\s.]+", decoded)
        if token.strip()
    ]
    ignored = {"in", "pub", "profile", "linkedin", "www", "m", "kr"}
    name_tokens = []
    for token in tokens:
        lowered = token.lower()
        if lowered in ignored:
            continue
        if "%" in token or "\ufffd" in token:
            continue
        if any(char.isdigit() for char in token):
            continue
        if re.fullmatch(r"[a-f0-9]{6,}", lowered):
            continue
        if re.search(r"[가-힣A-Za-z]", token):
            name_tokens.append(token)

    if len(name_tokens) < 2:
        return ""

    has_hangul = any(re.search(r"[가-힣]", token) for token in name_tokens)
    if has_hangul:
        return " ".join(name_tokens[:3])

    if all(re.fullmatch(r"[A-Za-z]{2,}", token) for token in name_tokens[:3]):
        return " ".join(token[:1].upper() + token[1:].lower() for token in name_tokens[:3])

    return ""


def classify_social_link(url: str, platform: str) -> dict[str, Any]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    entity_type = "profile"
    handle = ""

    if platform == "LinkedIn" and parts:
        if parts[0] in {"company", "school", "showcase"} and len(parts) > 1:
            entity_type = "company"
            handle = parts[1]
        elif parts[0] == "in" and len(parts) > 1:
            entity_type = "person"
            handle = parts[1]
    elif platform == "YouTube":
        entity_type = "channel"
        handle = parts[0] if parts else parsed.netloc
        if handle in {"channel", "c", "user"} and len(parts) > 1:
            handle = parts[1]
    elif platform == "Naver Blog":
        entity_type = "blog"
        handle = parts[0] if parts else parsed.netloc
    elif parts:
        handle = parts[0]
        if handle.lower() in {"share", "posts", "reel", "p", "status", "photo", "watch"} and len(parts) > 1:
            handle = parts[1]

    display_name = readable_handle(handle or parsed.netloc)
    name_candidate = social_name_candidate_from_slug(platform, entity_type, handle)
    return {
        "url": url,
        "platform": platform,
        "entity_type": entity_type,
        "handle": handle.strip("@"),
        "display_name": display_name,
        "name_candidate": name_candidate,
    }


def social_link_to_card_data(link: dict[str, Any]) -> dict[str, str]:
    platform = link["platform"]
    enriched = link.get("enriched") or {}
    display_name = enriched.get("contact_name") or link["display_name"]
    entity_type = link["entity_type"]
    is_company = entity_type in {"company", "channel", "blog"}
    company_name = enriched.get("company_name") or display_name
    contact_name = enriched.get("contact_name") or ("SNS 담당자 미확인" if is_company else display_name)
    profile_label = {
        "company": "회사 SNS 프로필",
        "channel": "SNS 채널",
        "blog": "블로그",
        "person": "개인 SNS 프로필",
        "profile": "SNS 프로필",
    }.get(entity_type, "SNS 프로필")

    return {
        "회사명": company_name,
        "이름": contact_name,
        "직무": enriched.get("job_title") or profile_label,
        "직위": enriched.get("job_position") or platform,
        "휴대전화": "",
        "이메일": enriched.get("email") or "",
        "홈페이지": link["url"],
        "SNS종류": platform,
        "SNS대상": entity_type,
        "SNS핸들": link.get("handle") or display_name,
        "SNS링크": link["url"],
        "SNS요약": enriched.get("summary") or "",
    }


def social_entity_label(entity_type: str) -> str:
    return {
        "company": "회사",
        "channel": "채널",
        "blog": "블로그",
        "person": "개인",
        "profile": "프로필",
    }.get(entity_type, entity_type or "프로필")


def best_social_description(metadata: dict[str, str]) -> str:
    return (
        metadata.get("og_description")
        or metadata.get("description")
        or metadata.get("title")
        or metadata.get("og_title")
        or ""
    )


def inspect_social_link(link: dict[str, Any]) -> dict[str, Any]:
    public_metadata = fetch_social_public_metadata(link)
    metadata_name = social_profile_name_from_metadata(public_metadata, link["platform"])
    slug_name = link.get("name_candidate") or social_name_candidate_from_slug(
        link.get("platform", ""),
        link.get("entity_type", ""),
        link.get("handle", ""),
    )
    profile_name = ""
    name_source = ""
    confidence = "none"

    if metadata_name and metadata_name_is_authoritative(link, metadata_name):
        profile_name = metadata_name
        name_source = "public_profile_metadata"
        confidence = "high"
    elif slug_name:
        profile_name = slug_name
        name_source = "profile_url_slug"
        confidence = "medium"

    fetched = any(public_metadata.get(key) for key in ("title", "og_title", "twitter_title", "description", "og_description"))
    status = "profile_name_found" if profile_name else "metadata_found" if fetched else "metadata_unavailable"

    return {
        "url": link["url"],
        "platform": link["platform"],
        "entity_type": link["entity_type"],
        "entity_label": social_entity_label(link["entity_type"]),
        "handle": link.get("handle") or "",
        "display_name": link.get("display_name") or "",
        "profile_name": profile_name,
        "name_source": name_source,
        "name_confidence": confidence,
        "name_candidate": slug_name,
        "metadata": public_metadata,
        "metadata_summary": best_social_description(public_metadata),
        "candidate_urls": social_metadata_candidate_urls(link),
        "status": status,
        "can_save_customer": bool(profile_name),
        "saved": False,
    }


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}


def clean_html_text(value: str) -> str:
    text = html_lib.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def html_metadata_value(document: str, *keys: str) -> str:
    wanted = {key.lower() for key in keys}
    for tag in re.findall(r"<meta\b[^>]*>", document or "", re.IGNORECASE | re.DOTALL):
        attrs: dict[str, str] = {}
        for match in re.finditer(r"([a-zA-Z_:.-]+)\s*=\s*(['\"])(.*?)\2", tag, re.DOTALL):
            attrs[match.group(1).lower()] = clean_html_text(match.group(3))
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key in wanted and attrs.get("content"):
            return attrs["content"]
    return ""


def social_metadata_candidate_urls(link: dict[str, Any]) -> list[str]:
    urls = [link["url"]]
    parsed = urlparse(link["url"])
    host = parsed.netloc.lower()
    if link["platform"] == "Facebook":
        path = parsed.path or "/"
        query = parsed.query
        for facebook_host in ("www.facebook.com", "m.facebook.com", "mbasic.facebook.com"):
            urls.append(urlunparse((parsed.scheme, facebook_host, path, "", query, "")))
    elif link["platform"] == "LinkedIn":
        path = parsed.path or "/"
        query = parsed.query
        for linkedin_host in ("www.linkedin.com", "kr.linkedin.com"):
            urls.append(urlunparse((parsed.scheme, linkedin_host, path, "", query, "")))

    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    return unique_urls


def fetch_social_public_metadata(link: dict[str, Any]) -> dict[str, str]:
    metadata = {"title": "", "og_title": "", "twitter_title": "", "description": "", "og_description": "", "fetch_error": ""}
    errors = []
    for url in social_metadata_candidate_urls(link):
        try:
            request = UrlRequest(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )
            with urlopen(request, timeout=SOCIAL_FETCH_TIMEOUT_SECONDS) as response:
                raw = response.read(300_000)
                charset = response.headers.get_content_charset() or "utf-8"
            try:
                document = raw.decode(charset, errors="replace")
            except LookupError:
                document = raw.decode("utf-8", errors="replace")
            title_match = re.search(r"<title[^>]*>(.*?)</title>", document, re.IGNORECASE | re.DOTALL)
            candidate = {
                "title": clean_html_text(title_match.group(1)) if title_match else "",
                "og_title": html_metadata_value(document, "og:title"),
                "twitter_title": html_metadata_value(document, "twitter:title"),
                "description": html_metadata_value(document, "description"),
                "og_description": html_metadata_value(document, "og:description"),
                "source_url": url,
            }
            if social_profile_name_from_metadata(candidate, link["platform"]):
                metadata.update(candidate)
                return metadata
            if not metadata.get("title") and any(candidate.values()):
                metadata.update(candidate)
        except Exception as error:
            errors.append(f"{url}: {error}")
    metadata["fetch_error"] = " | ".join(errors)
    return metadata


def strip_social_title_suffix(value: str, platform: str) -> str:
    text = clean_html_text(value)
    if not text:
        return ""

    low = text.lower()
    blocked_titles = (
        "facebook에 로그인",
        "log into facebook",
        "log in to facebook",
        "log in",
        "sign up",
        "login",
        "로그인",
        "가입",
        "browser not supported",
        "unsupported browser",
    )
    if any(blocked in low for blocked in blocked_titles):
        return ""

    labels = {
        "facebook",
        "linkedin",
        "instagram",
        "x",
        "twitter",
        "threads",
        "tiktok",
        "youtube",
        "github",
        "medium",
        "naver blog",
        "naver",
    }
    if platform:
        labels.add(platform.lower())
    label_pattern = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    text = re.sub(rf"\s*[\|\-–—·]\s*(?:{label_pattern})\s*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*\|\s*로그인.*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*-\s*프로필.*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in labels:
        return ""
    return text if len(text) <= 80 else ""


def normalized_person_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value or "").lower()


def social_profile_name_from_metadata(metadata: dict[str, str], platform: str) -> str:
    for key in ("og_title", "twitter_title", "title"):
        name = strip_social_title_suffix(metadata.get(key, ""), platform)
        if name:
            return name
    return ""


def metadata_name_is_authoritative(link: dict[str, Any], metadata_name: str) -> bool:
    if not metadata_name:
        return False
    handle_name = readable_handle(link.get("handle") or "")
    return normalized_person_name(metadata_name) != normalized_person_name(handle_name)


def extracted_name_conflicts(metadata_name: str, extracted_name: str) -> bool:
    left = normalized_person_name(metadata_name)
    right = normalized_person_name(extracted_name)
    if not left or not right:
        return False
    return left not in right and right not in left


def enrich_social_link(link: dict[str, Any]) -> dict[str, Any]:
    public_metadata = fetch_social_public_metadata(link)
    metadata_name = social_profile_name_from_metadata(public_metadata, link["platform"])
    slug_name = link.get("name_candidate") or social_name_candidate_from_slug(
        link.get("platform", ""),
        link.get("entity_type", ""),
        link.get("handle", ""),
    )
    query_parts = [
        f'"{link["url"]}"',
        link["platform"],
        link.get("handle") or "",
        link.get("display_name") or "",
        metadata_name,
        slug_name,
        public_metadata.get("og_title", ""),
        public_metadata.get("title", ""),
        "profile company career",
    ]
    query = " ".join(part for part in query_parts if part)
    try:
        search_tool = TavilySearchResults(max_results=5)
        search_results = search_tool.invoke({"query": query})
    except Exception as error:
        search_results = [{"error": str(error)}]

    try:
        model = create_gemini_model(temperature=0.1)
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You extract CRM fields from public SNS/search snippets. "
                        "Return only one JSON object. Do not wrap it in markdown. "
                        "Use Korean for briefing. Use empty strings for unknown fields. "
                        "JSON keys: contact_name, company_name, job_title, job_position, email, summary, briefing."
                    )
                ),
                HumanMessage(
                    content=(
                        f"SNS link metadata:\n{json.dumps(link, ensure_ascii=False)}\n\n"
                        f"Public page metadata:\n{json.dumps(public_metadata, ensure_ascii=False)}\n\n"
                        f"Search results:\n{json.dumps(search_results, ensure_ascii=False)}\n\n"
                        "If public page metadata contains a clear profile title such as '<person name> | Facebook', "
                        "use that person name as contact_name. "
                        "Do not replace a clear metadata-derived person name with a different search-result person. "
                        "Extract the most likely person/company CRM fields. "
                        "briefing must include sales-relevant details, career context, likely organization, and follow-up angle. "
                        "Do not invent unsupported emails or phone numbers."
                    )
                ),
            ]
        )
        extracted = extract_json_object(content_to_text(response.content))
    except Exception as error:
        extracted = {"briefing": f"SNS 상세 브리핑 생성 중 오류가 발생했습니다: {error}"}

    extracted_name = str(extracted.get("contact_name") or "").strip()
    authoritative_name = ""
    name_source = ""
    if metadata_name and metadata_name_is_authoritative(link, metadata_name):
        authoritative_name = metadata_name
        name_source = "public_profile_metadata"
    elif slug_name:
        authoritative_name = slug_name
        name_source = "linkedin_profile_url_slug"

    if authoritative_name:
        if extracted_name_conflicts(authoritative_name, extracted_name):
            extracted = {
                "contact_name": authoritative_name,
                "company_name": "",
                "job_title": "",
                "job_position": "",
                "email": "",
                "summary": f"{link['platform']} 프로필의 직접 근거에서 확인한 이름입니다.",
                "briefing": (
                    f"{link['platform']} 프로필 직접 근거에서 '{authoritative_name}' 이름을 확인했습니다. "
                    "검색 결과의 다른 인물 정보와 충돌해 회사, 직책, 연락처는 확정하지 않았습니다."
                ),
            }
        else:
            extracted["contact_name"] = authoritative_name

    name_verified = bool(authoritative_name)
    if link.get("entity_type") in {"person", "profile"} and not name_verified:
        extracted["contact_name"] = ""

    enriched = {
        "contact_name": str(extracted.get("contact_name") or "").strip(),
        "company_name": str(extracted.get("company_name") or "").strip(),
        "job_title": str(extracted.get("job_title") or "").strip(),
        "job_position": str(extracted.get("job_position") or "").strip(),
        "email": str(extracted.get("email") or "").strip(),
        "summary": str(extracted.get("summary") or "").strip(),
        "briefing": str(extracted.get("briefing") or "").strip(),
        "name_verified": name_verified,
        "name_source": name_source,
        "name_candidate": slug_name,
        "public_metadata": public_metadata,
        "search_results": search_results,
    }
    return {**link, "enriched": enriched}


def social_link_needs_name_confirmation(link: dict[str, Any], enriched: dict[str, Any]) -> bool:
    if link.get("entity_type") not in {"person", "profile"}:
        return False
    return not enriched.get("name_verified") or not str(enriched.get("contact_name") or "").strip()


def build_sns_confirmation_item(link: dict[str, Any], enriched_link: dict[str, Any]) -> dict[str, Any]:
    enriched = enriched_link.get("enriched", {})
    metadata = enriched.get("public_metadata") or {}
    name_candidate = enriched.get("name_candidate") or link.get("name_candidate") or ""
    reason = (
        f"{link['platform']} 링크에서 공개 프로필 이름을 확정하지 못했습니다. "
        "검색/AI 결과만으로는 다른 사람 정보가 섞일 수 있어 고객으로 저장하지 않았습니다. "
        "프로필 화면 캡처를 업로드하거나 이름을 직접 확인해 주세요."
    )
    return {
        "platform": link["platform"],
        "entity_type": link["entity_type"],
        "url": link["url"],
        "saved": False,
        "needs_confirmation": True,
        "reason": reason,
        "name_candidate": name_candidate,
        "data": {
            "회사명": "",
            "이름": name_candidate,
            "직무": "SNS 프로필 이름 확인 필요",
            "직위": link["platform"],
            "휴대전화": "",
            "이메일": "",
            "홈페이지": link["url"],
            "SNS종류": link["platform"],
            "SNS대상": link["entity_type"],
            "SNS핸들": link.get("handle") or link.get("display_name") or "",
            "SNS링크": link["url"],
            "SNS요약": reason,
        },
        "briefing": reason,
        "enriched": enriched,
        "public_metadata": metadata,
        "customer": None,
    }


def save_sns_customer(link: dict[str, Any], tenant_id: int, owner_user_id: int) -> dict[str, Any]:
    enriched_link = enrich_social_link(link)
    enriched = enriched_link.get("enriched", {})
    if social_link_needs_name_confirmation(link, enriched):
        return build_sns_confirmation_item(link, enriched_link)

    data = social_link_to_card_data(enriched_link)
    briefing = enriched_link.get("enriched", {}).get("briefing") or f"{link['platform']} 링크에서 생성한 SNS 기반 고객 후보입니다."
    customer = save_extracted_customer(
        data,
        briefing,
        f"SNS · {link['platform']}",
        tenant_id,
        owner_user_id,
    )
    return {
        "platform": link["platform"],
        "entity_type": link["entity_type"],
        "url": link["url"],
        "saved": True,
        "needs_confirmation": False,
        "data": data,
        "briefing": briefing,
        "enriched": enriched_link.get("enriched", {}),
        "customer": customer,
    }


def extract_social_profile_screenshot(contents: bytes) -> dict[str, Any]:
    model = create_gemini_model(temperature=0).with_structured_output(SocialProfileScreenshotInfo)
    image_b64 = base64.b64encode(contents).decode("utf-8")
    prompt = """
    You extract only visible facts from a screenshot of a social profile page.
    Decide whether the image is an SNS/social profile screen.
    If it is, extract the exact visible main profile person name as display_name.
    Do not infer a name from account handles, comments, search results, or surrounding UI.
    If the profile person's name is not clearly visible, return display_name as an empty string.
    Use Korean for summary and include only facts visible in the screenshot.
    """
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ]
    )
    response: SocialProfileScreenshotInfo = model.invoke([message])
    return response.model_dump()


def save_social_profile_screenshot_customer(
    info: dict[str, Any],
    source_file: str,
    tenant_id: int,
    owner_user_id: int,
    audit_session: dict[str, Any] | None = None,
    request: Request | None = None,
) -> dict[str, Any] | None:
    display_name = str(info.get("display_name") or "").strip()
    if not display_name:
        return None

    platform = str(info.get("platform") or "SNS").strip()
    company_name = str(info.get("company_name") or "").strip() or display_name
    headline = str(info.get("headline") or "").strip()
    profile_url = str(info.get("profile_url") or "").strip()
    summary = str(info.get("summary") or "").strip()
    data = {
        "회사명": company_name,
        "이름": display_name,
        "직무": headline or "SNS 프로필 화면 캡처",
        "직위": platform,
        "휴대전화": "",
        "이메일": "",
        "홈페이지": profile_url,
        "SNS종류": platform,
        "SNS대상": "profile_screenshot",
        "SNS핸들": "",
        "SNS링크": profile_url,
        "SNS요약": summary,
    }
    briefing = summary or f"{platform} 프로필 화면 캡처에서 '{display_name}' 이름을 확인했습니다."
    return save_extracted_customer(
        data,
        briefing,
        f"SNS 프로필 캡처 · {source_file}",
        tenant_id,
        owner_user_id,
        audit_session,
        request,
    )


def build_sns_import_reply(items: list[dict[str, Any]]) -> str:
    saved_items = [item for item in items if item.get("saved")]
    pending_items = [item for item in items if item.get("needs_confirmation")]
    if saved_items and pending_items:
        lines = ["SNS 링크를 분석해 이름이 확인된 항목은 저장했고, 이름을 확정하지 못한 항목은 저장하지 않았습니다."]
    elif saved_items:
        lines = ["SNS 링크를 분석해 고객 정보로 저장했습니다."]
    else:
        lines = ["SNS 링크에서 프로필 이름을 확정하지 못해 고객 정보로 저장하지 않았습니다."]

    for item in items:
        data = item.get("data") or {}
        name = data.get("이름") or "-"
        company = data.get("회사명") or "-"
        role = " / ".join(value for value in [data.get("직무"), data.get("직위")] if value) or "-"
        if item.get("saved"):
            lines.extend(
                [
                    "",
                    f"• 저장 완료: {company} / {name}",
                    f"• 역할: {role}",
                    f"• SNS: {item.get('platform')} ({item.get('url')})",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    f"• 확인 필요: {item.get('platform')} ({item.get('url')})",
                    f"• 사유: {item.get('reason') or '공개 프로필 이름을 확정하지 못했습니다.'}",
                ]
            )
        if item.get("saved") and item.get("briefing"):
            lines.extend(["", item["briefing"]])
    return "\n".join(lines)


def build_sns_inspect_reply(items: list[dict[str, Any]]) -> str:
    lines = ["SNS 링크를 확인해 플랫폼과 공개 프로필 정보를 정리했습니다. 아직 고객 정보로 저장하지 않았습니다."]
    for item in items:
        name = item.get("profile_name") or item.get("name_candidate") or "-"
        summary = item.get("metadata_summary") or "공개 메타데이터를 충분히 가져오지 못했습니다."
        lines.extend(
            [
                "",
                f"• SNS: {item.get('platform')} / {item.get('entity_label')}",
                f"• 이름 후보: {name}",
                f"• 신뢰도: {item.get('name_confidence') or 'none'}",
                f"• 링크: {item.get('url')}",
                f"• 확인 정보: {summary}",
            ]
        )
    return "\n".join(lines)


def fetch_contact(cursor, contact_id: int, tenant_id: int, owner_user_id: int | None = None) -> dict[str, Any] | None:
    owner_filter = "AND c.owner_user_id = %s" if owner_user_id is not None else ""
    cursor.execute(
        f"""
        SELECT
            c.id AS contact_id,
            c.tenant_id,
            c.account_id,
            c.owner_user_id,
            c.name AS contact_name,
            c.title,
            c.department,
            c.email,
            c.phone,
            c.mobile,
            c.is_primary,
            c.created_at,
            c.updated_at,
            a.name AS company_name,
            a.website,
            a.phone AS account_phone,
            a.address,
            a.business_no,
            a.industry
        FROM contacts c
        LEFT JOIN accounts a
               ON a.id = c.account_id
              AND a.tenant_id = c.tenant_id
              AND a.deleted_at IS NULL
        WHERE c.id = %s
          AND c.tenant_id = %s
          {owner_filter}
          AND c.deleted_at IS NULL
        """,
        (contact_id, tenant_id, owner_user_id) if owner_user_id is not None else (contact_id, tenant_id),
    )
    return cursor.fetchone()


def fetch_account_audit_row(cursor, account_id: int, tenant_id: int, owner_user_id: int | None) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, tenant_id, owner_user_id, name, account_type, industry, business_no, website, phone, address, status, created_at, updated_at, deleted_at
        FROM accounts
        WHERE id = %s
          AND tenant_id = %s
          AND owner_user_id = %s
        LIMIT 1
        """,
        (account_id, tenant_id, owner_user_id),
    )
    return cursor.fetchone()


def fetch_contact_audit_row(cursor, contact_id: int, tenant_id: int, owner_user_id: int | None) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, tenant_id, account_id, owner_user_id, name, title, department, email, phone, mobile, is_primary, created_at, updated_at, deleted_at
        FROM contacts
        WHERE id = %s
          AND tenant_id = %s
          AND owner_user_id = %s
        LIMIT 1
        """,
        (contact_id, tenant_id, owner_user_id),
    )
    return cursor.fetchone()


def upsert_account(
    cursor,
    payload: CustomerPayload,
    tenant_id: int,
    audit_session: dict[str, Any] | None = None,
    request: Request | None = None,
) -> int | None:
    company_name = payload.company_name.strip()
    if not company_name:
        return None

    cursor.execute(
        """
        SELECT id
        FROM accounts
        WHERE tenant_id = %s
          AND owner_user_id = %s
          AND name = %s
          AND deleted_at IS NULL
        ORDER BY id
        LIMIT 1
        """,
        (tenant_id, payload.owner_user_id, company_name),
    )
    account = cursor.fetchone()
    before = fetch_account_audit_row(cursor, account["id"], tenant_id, payload.owner_user_id) if account else None
    account_values = (
        none_if_blank(payload.homepage),
        none_if_blank(payload.phone),
        none_if_blank(payload.address),
        none_if_blank(payload.business_no),
        none_if_blank(payload.industry),
        payload.owner_user_id,
    )

    if account:
        cursor.execute(
            """
            UPDATE accounts
            SET website = COALESCE(%s, website),
                phone = COALESCE(%s, phone),
                address = COALESCE(%s, address),
                business_no = COALESCE(%s, business_no),
                industry = COALESCE(%s, industry),
                owner_user_id = COALESCE(%s, owner_user_id)
            WHERE id = %s
              AND tenant_id = %s
              AND owner_user_id = %s
            """,
            (*account_values, account["id"], tenant_id, payload.owner_user_id),
        )
        if audit_session:
            after = fetch_account_audit_row(cursor, account["id"], tenant_id, payload.owner_user_id)
            write_audit_log(cursor, audit_session, "update", "accounts", account["id"], before, after, request)
        return account["id"]

    cursor.execute(
        """
        INSERT INTO accounts (
            tenant_id, owner_user_id, name, account_type, industry,
            business_no, website, phone, address, status
        )
        VALUES (%s, %s, %s, 'customer', %s, %s, %s, %s, %s, 'active')
        """,
        (
            tenant_id,
            payload.owner_user_id,
            company_name,
            none_if_blank(payload.industry),
            none_if_blank(payload.business_no),
            none_if_blank(payload.homepage),
            none_if_blank(payload.phone),
            none_if_blank(payload.address),
        ),
    )
    account_id = cursor.lastrowid
    if audit_session:
        after = fetch_account_audit_row(cursor, account_id, tenant_id, payload.owner_user_id)
        write_audit_log(cursor, audit_session, "create", "accounts", account_id, None, after, request)
    return account_id


def insert_customer(
    payload: CustomerPayload,
    audit_session: dict[str, Any] | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(payload.tenant_id)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        account_id = upsert_account(cursor, payload, tenant_id, audit_session, request)
        cursor.execute(
            """
            INSERT INTO contacts (
                tenant_id, account_id, owner_user_id, name, title,
                department, email, phone, mobile, is_primary
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                account_id,
                payload.owner_user_id,
                payload.contact_name.strip() or "이름 미확인",
                none_if_blank(payload.job_position),
                none_if_blank(payload.job_title),
                none_if_blank(payload.email),
                none_if_blank(payload.phone),
                none_if_blank(payload.mobile_phone),
                1 if payload.is_primary else 0,
            ),
        )
        contact_id = cursor.lastrowid
        if audit_session:
            after = fetch_contact_audit_row(cursor, contact_id, tenant_id, payload.owner_user_id)
            write_audit_log(cursor, audit_session, "create", "contacts", contact_id, None, after, request)
        row = fetch_contact(cursor, contact_id, tenant_id, payload.owner_user_id)
        return contact_row_to_customer(row)


def update_customer_record(
    customer_id: int,
    payload: CustomerPayload,
    audit_session: dict[str, Any] | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(payload.tenant_id)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        current = fetch_contact(cursor, customer_id, tenant_id, payload.owner_user_id)
        if not current:
            raise HTTPException(status_code=404, detail="Customer not found")

        before = fetch_contact_audit_row(cursor, customer_id, tenant_id, payload.owner_user_id)
        account_id = upsert_account(cursor, payload, tenant_id, audit_session, request)
        cursor.execute(
            """
            UPDATE contacts
            SET account_id = %s,
                owner_user_id = %s,
                name = %s,
                title = %s,
                department = %s,
                email = %s,
                phone = %s,
                mobile = %s,
                is_primary = %s
            WHERE id = %s
              AND tenant_id = %s
              AND owner_user_id = %s
              AND deleted_at IS NULL
            """,
            (
                account_id,
                payload.owner_user_id,
                payload.contact_name.strip() or "이름 미확인",
                none_if_blank(payload.job_position),
                none_if_blank(payload.job_title),
                none_if_blank(payload.email),
                none_if_blank(payload.phone),
                none_if_blank(payload.mobile_phone),
                1 if payload.is_primary else 0,
                customer_id,
                tenant_id,
                payload.owner_user_id,
            ),
        )
        if audit_session:
            after = fetch_contact_audit_row(cursor, customer_id, tenant_id, payload.owner_user_id)
            write_audit_log(cursor, audit_session, "update", "contacts", customer_id, before, after, request)
        row = fetch_contact(cursor, customer_id, tenant_id, payload.owner_user_id)
        return contact_row_to_customer(row)


def save_extracted_customer(
    data: dict[str, Any],
    briefing: str,
    source_file: str,
    tenant_id: int | None = None,
    owner_user_id: int | None = None,
    audit_session: dict[str, Any] | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    normalized = normalize_card_data(data)
    payload = CustomerPayload(
        **normalized,
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        briefing=briefing or "",
        source_file=source_file or "",
    )
    return insert_customer(payload, audit_session, request)


SALES_ACTIVITY_INTENT_RE = re.compile(r"(일정|영업활동|활동|미팅|회의|방문|전화|통화|콜|메일|데모|시연)")
SALES_ACTIVITY_ACTION_RE = re.compile(r"(등록|추가|잡아|생성|저장|예약|만들|넣어|기록)")
SALES_ACTIVITY_CANCEL_RE = re.compile(r"(취소|삭제|지워|없애|캔슬)")
SALES_ACTIVITY_RESCHEDULE_RE = re.compile(r"(변경|수정|옮겨|미뤄|앞당겨|바꿔|조정)")
SALES_ACTIVITY_REPEAT_RE = re.compile(r"(반복|정기|매일|매주|매월)")
SALES_ACTIVITY_LIST_RE = re.compile(r"(조회|확인|목록|보여|알려)")
WEEKDAY_INDEXES = {
    "월": 0,
    "월요일": 0,
    "화": 1,
    "화요일": 1,
    "수": 2,
    "수요일": 2,
    "목": 3,
    "목요일": 3,
    "금": 4,
    "금요일": 4,
    "토": 5,
    "토요일": 5,
    "일": 6,
    "일요일": 6,
}


def app_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(APP_TIMEZONE))
    except Exception:
        return datetime.now()


def is_sales_activity_schedule_request(message: str) -> bool:
    text = message or ""
    action_patterns = (
        SALES_ACTIVITY_ACTION_RE,
        SALES_ACTIVITY_CANCEL_RE,
        SALES_ACTIVITY_RESCHEDULE_RE,
        SALES_ACTIVITY_REPEAT_RE,
        SALES_ACTIVITY_LIST_RE,
    )
    return bool(SALES_ACTIVITY_INTENT_RE.search(text) and any(pattern.search(text) for pattern in action_patterns))


def parse_sales_activity_type(message: str) -> str:
    text = message or ""
    if re.search(r"(전화|통화|콜)", text):
        return "call"
    if re.search(r"(메일|이메일)", text):
        return "email"
    if re.search(r"(방문|미팅|회의|만나|대면)", text):
        return "visit"
    if re.search(r"(데모|시연)", text):
        return "demo"
    return "task"


def parse_activity_time(message: str) -> tuple[int, int]:
    text = message or ""
    colon_match = re.search(r"(?<!\d)([01]?\d|2[0-3])\s*:\s*([0-5]\d)(?!\d)", text)
    if colon_match:
        return int(colon_match.group(1)), int(colon_match.group(2))

    korean_match = re.search(r"(오전|오후|아침|저녁|밤)?\s*([0-2]?\d)\s*시\s*(반|[0-5]?\d\s*분)?", text)
    if korean_match:
        marker = korean_match.group(1) or ""
        hour = int(korean_match.group(2))
        minute_text = (korean_match.group(3) or "").strip()
        minute = 30 if "반" in minute_text else int(re.sub(r"\D", "", minute_text) or 0)
        if marker in {"오후", "저녁", "밤"} and hour < 12:
            hour += 12
        if marker in {"오전", "아침"} and hour == 12:
            hour = 0
        return min(hour, 23), min(minute, 59)

    if "오전" in text or "아침" in text:
        return 9, 0
    if "점심" in text:
        return 12, 0
    if "오후" in text:
        return 14, 0
    if "저녁" in text:
        return 18, 0
    return 9, 0


def next_weekday(base_date: date, target_weekday: int, next_week: bool = False) -> date:
    days = (target_weekday - base_date.weekday()) % 7
    if next_week:
        days = days or 7
    return base_date + timedelta(days=days)


def combine_activity_datetime(target_date: date, message_part: str) -> datetime:
    hour, minute = parse_activity_time(message_part)
    return datetime(target_date.year, target_date.month, target_date.day, hour, minute)


def parse_sales_activity_due_at_candidates(message: str, now: datetime | None = None) -> list[datetime]:
    now = now or app_now()
    text = message or ""
    candidates: list[tuple[int, datetime]] = []

    for match in re.finditer(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", text):
        target_date = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        candidates.append((match.start(), combine_activity_datetime(target_date, text[match.start() :])))

    for match in re.finditer(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일", text):
        month = int(match.group(1))
        day = int(match.group(2))
        year = now.year + (1 if month < now.month else 0)
        target_date = date(year, month, day)
        candidates.append((match.start(), combine_activity_datetime(target_date, text[match.start() :])))

    for match in re.finditer(r"(오늘|내일|모레)", text):
        day_offset = {"오늘": 0, "내일": 1, "모레": 2}[match.group(1)]
        target_date = (now + timedelta(days=day_offset)).date()
        candidates.append((match.start(), combine_activity_datetime(target_date, text[match.start() :])))

    for match in re.finditer(r"(이번\s*주|다음\s*주|매주)?\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일|월|화|수|목|금|토|일)(?![가-힣])", text):
        target_date = next_weekday(
            now.date(),
            WEEKDAY_INDEXES[match.group(2)],
            next_week=bool(match.group(1) and "다음" in match.group(1)),
        )
        candidates.append((match.start(), combine_activity_datetime(target_date, text[match.start() :])))

    unique: list[datetime] = []
    seen = set()
    for _position, value in sorted(candidates, key=lambda item: item[0]):
        key = value.isoformat()
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique


def parse_sales_activity_due_at(message: str, now: datetime | None = None) -> datetime | None:
    candidates = parse_sales_activity_due_at_candidates(message, now)
    return candidates[0] if candidates else None


def parse_sales_activity_new_due_at(message: str, now: datetime | None = None) -> datetime | None:
    candidates = parse_sales_activity_due_at_candidates(message, now)
    return candidates[-1] if candidates else None


def add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return value.replace(year=year, month=month, day=day)


def parse_recurrence_rule(message: str, first_due_at: datetime) -> dict[str, Any] | None:
    text = message or ""
    if not SALES_ACTIVITY_REPEAT_RE.search(text):
        return None
    count_match = re.search(r"(\d{1,2})\s*(회|번)", text)
    count = int(count_match.group(1)) if count_match else 4
    count = max(1, min(count, MAX_RECURRING_ACTIVITY_COUNT))
    if "매월" in text:
        frequency = "monthly"
    elif "매일" in text:
        frequency = "daily"
    else:
        frequency = "weekly"
    return {"frequency": frequency, "count": count, "first_due_at": first_due_at}


def recurrence_due_at(rule: dict[str, Any], index: int) -> datetime:
    first_due_at = rule["first_due_at"]
    if rule["frequency"] == "daily":
        return first_due_at + timedelta(days=index)
    if rule["frequency"] == "monthly":
        return add_months(first_due_at, index)
    return first_due_at + timedelta(weeks=index)


def selected_customer_id_from_context(context: dict[str, Any] | None) -> int | None:
    if not isinstance(context, dict):
        return None
    selected = context.get("selectedCustomer")
    if not isinstance(selected, dict):
        return None
    for key in ("contactId", "id"):
        try:
            value = int(selected.get(key) or 0)
            if value:
                return value
        except Exception:
            continue
    return None


def normalize_customer_mention_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def score_customer_mention(message: str, row: dict[str, Any]) -> int:
    normalized_message = normalize_customer_mention_text(message)
    if not normalized_message:
        return 0

    score = 0
    company = normalize_customer_mention_text(row.get("company_name"))
    contact = normalize_customer_mention_text(row.get("contact_name"))
    if company and len(company) >= 2 and company in normalized_message:
        score += len(company) * 2
    if contact and len(contact) >= 2 and contact in normalized_message:
        score += len(contact) * 3
    return score


def selected_customer_context_from_row(
    row: dict[str, Any],
    source: str = "DB - command mention",
) -> dict[str, Any]:
    customer = contact_row_to_customer(row)
    return {
        "id": customer.get("id") or customer.get("contact_id"),
        "contactId": customer.get("contact_id") or customer.get("id"),
        "accountId": customer.get("account_id"),
        "tenantId": customer.get("tenant_id"),
        "ownerUserId": customer.get("owner_user_id"),
        "source": source,
        "data": customer.get("card_data") or {},
        "customer": customer,
        "selectedAt": app_now().isoformat(),
    }


def context_with_selected_customer(
    context: dict[str, Any] | None,
    row: dict[str, Any],
    source: str = "DB - command mention",
) -> dict[str, Any]:
    next_context = dict(context or {})
    next_context["selectedCustomer"] = selected_customer_context_from_row(row, source)
    return next_context


def build_customer_selection_candidates(scored_rows: list[tuple[int, dict[str, Any]]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[int] = set()
    for score, row in scored_rows:
        contact_id = int(row.get("contact_id") or 0)
        if not contact_id or contact_id in seen:
            continue
        seen.add(contact_id)
        customer = contact_row_to_customer(row)
        customer["match_score"] = score
        customer["match_fields"] = [
            field
            for field, token in (
                ("company_name", normalize_customer_mention_text(row.get("company_name"))),
                ("contact_name", normalize_customer_mention_text(row.get("contact_name"))),
            )
            if token
        ]
        candidates.append(customer)
        if len(candidates) >= 8:
            break
    return candidates


def resolve_command_customer_preflight(
    cursor,
    session: dict[str, Any],
    message: str,
    context: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any] | None]:
    rows = fetch_owned_customer_rows(cursor, session["tenant_id"], session["user_id"])
    selected_id = selected_customer_id_from_context(context)
    selected = next((row for row in rows if row.get("contact_id") == selected_id), None)
    scored = [(score_customer_mention(message, row), row) for row in rows]
    scored = [(score, row) for score, row in scored if score > 0]
    if not scored:
        return context, [], selected

    scored.sort(
        key=lambda item: (
            item[0],
            item[1].get("updated_at") or item[1].get("created_at") or "",
            item[1].get("contact_id") or 0,
        ),
        reverse=True,
    )
    candidate_ids = {row.get("contact_id") for _, row in scored}
    if selected and selected.get("contact_id") in candidate_ids:
        return context, [], selected

    candidates = build_customer_selection_candidates(scored)
    if len(candidates) == 1:
        row = scored[0][1]
        return context_with_selected_customer(context, row), [], row

    return context, candidates, None


def fetch_owned_customer_rows(cursor, tenant_id: int, owner_user_id: int) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT
            c.id AS contact_id,
            c.tenant_id,
            c.account_id,
            c.owner_user_id,
            c.name AS contact_name,
            c.title,
            c.department,
            c.email,
            c.phone,
            c.mobile,
            c.created_at,
            c.updated_at,
            a.name AS company_name,
            a.website,
            a.phone AS account_phone,
            a.address,
            a.business_no,
            a.industry
        FROM contacts c
        LEFT JOIN accounts a
               ON a.id = c.account_id
              AND a.tenant_id = c.tenant_id
              AND a.deleted_at IS NULL
        WHERE c.tenant_id = %s
          AND c.owner_user_id = %s
          AND c.deleted_at IS NULL
        ORDER BY c.updated_at DESC, c.id DESC
        LIMIT 500
        """,
        (tenant_id, owner_user_id),
    )
    return cursor.fetchall()


def resolve_sales_activity_customer(
    cursor,
    session: dict[str, Any],
    message: str,
    context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    selected_id = selected_customer_id_from_context(context)
    rows = fetch_owned_customer_rows(cursor, session["tenant_id"], session["user_id"])
    selected = next((row for row in rows if row.get("contact_id") == selected_id), None)
    normalized_message = re.sub(r"\s+", "", message or "").lower()
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        score = 0
        company = re.sub(r"\s+", "", str(row.get("company_name") or "")).lower()
        contact = re.sub(r"\s+", "", str(row.get("contact_name") or "")).lower()
        if company and len(company) >= 2 and company in normalized_message:
            score += len(company) * 2
        if contact and len(contact) >= 2 and contact in normalized_message:
            score += len(contact) * 3
        if score:
            scored.append((score, row))
    if scored:
        scored.sort(key=lambda item: (item[0], item[1].get("updated_at") or item[1].get("created_at") or ""), reverse=True)
        return scored[0][1]
    return selected


def fetch_target_sales_activity(
    cursor,
    session: dict[str, Any],
    customer: dict[str, Any] | None,
    message: str,
    prefer_due_at: datetime | None = None,
) -> dict[str, Any] | None:
    filters = [
        "a.tenant_id = %s",
        "a.owner_user_id = %s",
        "a.deleted_at IS NULL",
        "a.status = 'planned'",
    ]
    params: list[Any] = [session["tenant_id"], session["user_id"]]
    if customer:
        if customer.get("contact_id"):
            filters.append("a.contact_id = %s")
            params.append(customer["contact_id"])
        elif customer.get("account_id"):
            filters.append("a.account_id = %s")
            params.append(customer["account_id"])
    if prefer_due_at:
        filters.append("DATE(a.due_at) = %s")
        params.append(prefer_due_at.date())
    keyword = ""
    title_match = re.search(r"['\"]([^'\"]{2,80})['\"]", message or "")
    if title_match:
        keyword = title_match.group(1).strip()
    if keyword:
        filters.append("(a.subject LIKE %s OR a.content LIKE %s)")
        keyword_like = f"%{keyword}%"
        params.extend([keyword_like, keyword_like])

    cursor.execute(
        f"""
        SELECT
            a.id, a.tenant_id, a.owner_user_id, a.account_id, a.contact_id,
            a.activity_type, a.subject, a.content, a.status, a.due_at,
            a.completed_at, a.created_at, a.updated_at,
            ac.name AS company_name,
            c.name AS contact_name
        FROM activities a
        LEFT JOIN accounts ac
               ON ac.id = a.account_id
              AND ac.tenant_id = a.tenant_id
              AND ac.deleted_at IS NULL
        LEFT JOIN contacts c
               ON c.id = a.contact_id
              AND c.tenant_id = a.tenant_id
              AND c.deleted_at IS NULL
        WHERE {" AND ".join(filters)}
        ORDER BY
            CASE WHEN a.due_at >= NOW(6) THEN 0 ELSE 1 END,
            a.due_at ASC,
            a.id DESC
        LIMIT 1
        """,
        tuple(params),
    )
    return cursor.fetchone()


def activity_customer_label(activity: dict[str, Any] | None, customer: dict[str, Any] | None = None) -> str:
    company = (activity or {}).get("company_name") or (customer or {}).get("company_name") or "회사명 미확인"
    contact = (activity or {}).get("contact_name") or (customer or {}).get("contact_name") or "고객명 미확인"
    return f"{company} / {contact}"


def activity_calendar_payload(activity: dict[str, Any] | None = None, due_at: datetime | None = None) -> dict[str, int] | None:
    value = due_at or (activity or {}).get("due_at")
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except Exception:
            value = None
    if not isinstance(value, datetime):
        return None
    return {"year": value.year, "month": value.month}


def insert_sales_activity(
    cursor,
    session: dict[str, Any],
    customer: dict[str, Any],
    message: str,
    due_at: datetime,
    activity_type: str,
    subject_suffix: str = "영업활동",
) -> dict[str, Any]:
    company = customer.get("company_name") or "회사명 미확인"
    contact = customer.get("contact_name") or "고객명 미확인"
    subject = f"{company} / {contact} {subject_suffix}"
    cursor.execute(
        """
        INSERT INTO activities (
            tenant_id, owner_user_id, account_id, contact_id,
            activity_type, subject, content, status, due_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'planned', %s)
        """,
        (
            session["tenant_id"],
            session["user_id"],
            customer.get("account_id"),
            customer.get("contact_id"),
            activity_type,
            subject,
            message,
            due_at,
        ),
    )
    activity_id = cursor.lastrowid
    cursor.execute(
        """
        SELECT id, tenant_id, owner_user_id, account_id, contact_id, activity_type, subject, content, status, due_at, created_at, updated_at
        FROM activities
        WHERE id = %s AND tenant_id = %s
        """,
        (activity_id, session["tenant_id"]),
    )
    return cursor.fetchone()


def list_sales_activities_from_message(
    session: dict[str, Any],
    message: str,
    context: dict[str, Any] | None,
    request: Request,
) -> dict[str, Any]:
    due_at = parse_sales_activity_due_at(message)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        customer = resolve_sales_activity_customer(cursor, session, message, context)
        filters = [
            "a.tenant_id = %s",
            "a.owner_user_id = %s",
            "a.deleted_at IS NULL",
            "a.status = 'planned'",
        ]
        params: list[Any] = [session["tenant_id"], session["user_id"]]
        if customer:
            filters.append("a.contact_id = %s")
            params.append(customer["contact_id"])
        if due_at:
            filters.append("DATE(a.due_at) = %s")
            params.append(due_at.date())
        cursor.execute(
            f"""
            SELECT
                a.id, a.activity_type, a.subject, a.status, a.due_at,
                ac.name AS company_name, c.name AS contact_name
            FROM activities a
            LEFT JOIN accounts ac
                   ON ac.id = a.account_id
                  AND ac.tenant_id = a.tenant_id
                  AND ac.deleted_at IS NULL
            LEFT JOIN contacts c
                   ON c.id = a.contact_id
                  AND c.tenant_id = a.tenant_id
                  AND c.deleted_at IS NULL
            WHERE {" AND ".join(filters)}
              AND a.due_at >= DATE_SUB(NOW(6), INTERVAL 1 DAY)
            ORDER BY a.due_at ASC, a.id DESC
            LIMIT 10
            """,
            tuple(params),
        )
        activities = admin_json_rows(cursor.fetchall())
    if not activities:
        return {"saved": False, "action": "list", "reply": "조회할 예정 영업활동 일정을 찾지 못했습니다."}
    lines = [
        f"{index + 1}. {activity_customer_label(activity)} - {activity.get('subject') or '영업활동'} ({str(activity.get('due_at'))[:16]})"
        for index, activity in enumerate(activities)
    ]
    return {
        "saved": False,
        "action": "list",
        "reply": "예정된 영업활동 일정입니다.\n" + "\n".join(lines),
        "activities": activities,
        "calendar": activity_calendar_payload(activities[0]),
    }


def cancel_sales_activity_from_message(
    session: dict[str, Any],
    message: str,
    context: dict[str, Any] | None,
    request: Request,
) -> dict[str, Any]:
    due_at = parse_sales_activity_due_at(message)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        customer = resolve_sales_activity_customer(cursor, session, message, context)
        activity = fetch_target_sales_activity(cursor, session, customer, message, due_at)
        if not activity:
            return {"saved": False, "action": "cancel", "reply": "취소할 예정 영업활동 일정을 찾지 못했습니다. 고객과 날짜를 함께 알려주세요."}
        before = dict(activity)
        cursor.execute(
            "UPDATE activities SET status = 'cancelled', content = CONCAT(COALESCE(content, ''), %s) WHERE id = %s AND tenant_id = %s",
            (f"\n\n[취소 요청] {message}", activity["id"], session["tenant_id"]),
        )
        cursor.execute(
            """
            SELECT id, tenant_id, owner_user_id, account_id, contact_id, activity_type, subject, content, status, due_at, created_at, updated_at
            FROM activities
            WHERE id = %s AND tenant_id = %s
            """,
            (activity["id"], session["tenant_id"]),
        )
        after = cursor.fetchone()
        write_audit_log(cursor, session, "cancel", "activity", activity["id"], before, after, request)
    return {
        "saved": True,
        "action": "cancel",
        "reply": f"{activity_customer_label(activity, customer)} 고객의 {str(activity.get('due_at'))[:16]} 영업활동 일정을 취소했습니다.",
        "activity": admin_json_row(after),
        "calendar": activity_calendar_payload(activity),
    }


def reschedule_sales_activity_from_message(
    session: dict[str, Any],
    message: str,
    context: dict[str, Any] | None,
    request: Request,
) -> dict[str, Any]:
    new_due_at = parse_sales_activity_new_due_at(message)
    if not new_due_at:
        return {"saved": False, "action": "reschedule", "reply": "변경할 새 날짜와 시간을 알려주세요. 예: 다음 주 화요일 오후 3시로 변경"}
    candidates = parse_sales_activity_due_at_candidates(message)
    old_due_at = candidates[0] if len(candidates) > 1 else None
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        customer = resolve_sales_activity_customer(cursor, session, message, context)
        activity = fetch_target_sales_activity(cursor, session, customer, message, old_due_at)
        if not activity:
            return {"saved": False, "action": "reschedule", "reply": "날짜를 변경할 예정 영업활동 일정을 찾지 못했습니다. 고객과 기존 일정 날짜를 함께 알려주세요."}
        before = dict(activity)
        cursor.execute(
            "UPDATE activities SET due_at = %s, content = CONCAT(COALESCE(content, ''), %s) WHERE id = %s AND tenant_id = %s",
            (new_due_at, f"\n\n[일정 변경 요청] {message}", activity["id"], session["tenant_id"]),
        )
        cursor.execute(
            """
            SELECT id, tenant_id, owner_user_id, account_id, contact_id, activity_type, subject, content, status, due_at, created_at, updated_at
            FROM activities
            WHERE id = %s AND tenant_id = %s
            """,
            (activity["id"], session["tenant_id"]),
        )
        after = cursor.fetchone()
        write_audit_log(cursor, session, "reschedule", "activity", activity["id"], before, after, request)
    return {
        "saved": True,
        "action": "reschedule",
        "reply": f"{activity_customer_label(activity, customer)} 고객의 영업활동 일정을 {new_due_at.strftime('%Y-%m-%d %H:%M')}로 변경했습니다. 캘린더에서 확인할 수 있도록 열어둘게요.",
        "activity": admin_json_row(after),
        "calendar": activity_calendar_payload(due_at=new_due_at),
    }


def create_recurring_sales_activities_from_message(
    session: dict[str, Any],
    message: str,
    context: dict[str, Any] | None,
    request: Request,
) -> dict[str, Any]:
    first_due_at = parse_sales_activity_due_at(message)
    if first_due_at is None:
        return {
            "saved": False,
            "action": "repeat",
            "reply": "반복 일정을 저장하려면 시작 날짜나 요일을 함께 알려주세요. 예: 매주 월요일 오전 10시 4회 미팅 일정 등록",
        }
    rule = parse_recurrence_rule(message, first_due_at)
    if not rule:
        return create_sales_activity_from_message(session, message, context, request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        customer = resolve_sales_activity_customer(cursor, session, message, context)
        if not customer:
            return {
                "saved": False,
                "action": "repeat",
                "reply": "반복 영업활동 일정을 저장하려면 고객 패널에서 고객을 선택하거나, 등록된 고객의 회사명/이름을 메시지에 포함해 주세요.",
            }
        activity_type = parse_sales_activity_type(message)
        activities = []
        for index in range(rule["count"]):
            due_at = recurrence_due_at(rule, index)
            activity = insert_sales_activity(cursor, session, customer, message, due_at, activity_type, "반복 영업활동")
            activities.append(admin_json_row(activity))
        write_audit_log(cursor, session, "create_recurring", "activity", None, None, {"activities": activities}, request)
    label = activity_customer_label(None, customer)
    return {
        "saved": True,
        "action": "repeat",
        "reply": f"{label} 고객의 반복 영업활동 일정을 {len(activities)}건 저장했습니다. 첫 일정이 있는 월의 캘린더를 열어둘게요.",
        "activities": activities,
        "activity": activities[0] if activities else None,
        "customer": contact_row_to_customer(customer),
        "calendar": activity_calendar_payload(activities[0]) if activities else None,
    }


def create_sales_activity_from_message(
    session: dict[str, Any],
    message: str,
    context: dict[str, Any] | None,
    request: Request,
) -> dict[str, Any]:
    due_at = parse_sales_activity_due_at(message)
    if due_at is None:
        return {
            "saved": False,
            "reply": "영업활동 일정으로 이해했습니다. 저장하려면 날짜를 함께 알려주세요. 예: 내일 오후 2시에 미팅 일정 등록",
        }

    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        customer = resolve_sales_activity_customer(cursor, session, message, context)
        if not customer:
            return {
                "saved": False,
                "reply": "영업활동 일정을 저장하려면 고객 패널에서 고객을 선택하거나, 등록된 고객의 회사명/이름을 메시지에 포함해 주세요.",
            }
        activity_type = parse_sales_activity_type(message)
        company = customer.get("company_name") or "회사명 미확인"
        contact = customer.get("contact_name") or "고객명 미확인"
        subject = f"{company} / {contact} 영업활동"
        cursor.execute(
            """
            INSERT INTO activities (
                tenant_id, owner_user_id, account_id, contact_id,
                activity_type, subject, content, status, due_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'planned', %s)
            """,
            (
                session["tenant_id"],
                session["user_id"],
                customer.get("account_id"),
                customer.get("contact_id"),
                activity_type,
                subject,
                message,
                due_at,
            ),
        )
        activity_id = cursor.lastrowid
        cursor.execute(
            """
            SELECT id, tenant_id, owner_user_id, account_id, contact_id, activity_type, subject, content, status, due_at, created_at, updated_at
            FROM activities
            WHERE id = %s AND tenant_id = %s
            """,
            (activity_id, session["tenant_id"]),
        )
        activity = cursor.fetchone()
        write_audit_log(cursor, session, "create", "activity", activity_id, None, activity, request)

    due_label = due_at.strftime("%Y-%m-%d %H:%M")
    return {
        "saved": True,
        "action": "create",
        "reply": f"{company} / {contact} 고객의 영업활동 일정을 {due_label}에 저장했습니다. 캘린더에서 바로 확인할 수 있도록 열어둘게요.",
        "activity": admin_json_row(activity),
        "customer": contact_row_to_customer(customer),
        "calendar": {"year": due_at.year, "month": due_at.month},
    }


def manage_sales_activity_from_message(
    session: dict[str, Any],
    message: str,
    context: dict[str, Any] | None,
    request: Request,
) -> dict[str, Any]:
    if SALES_ACTIVITY_CANCEL_RE.search(message):
        return cancel_sales_activity_from_message(session, message, context, request)
    if SALES_ACTIVITY_RESCHEDULE_RE.search(message):
        return reschedule_sales_activity_from_message(session, message, context, request)
    if SALES_ACTIVITY_REPEAT_RE.search(message):
        return create_recurring_sales_activities_from_message(session, message, context, request)
    if SALES_ACTIVITY_LIST_RE.search(message) and not SALES_ACTIVITY_ACTION_RE.search(message):
        return list_sales_activities_from_message(session, message, context, request)
    return create_sales_activity_from_message(session, message, context, request)


def build_chat_context(context: dict[str, Any] | None) -> str:
    if not context:
        return "현재 세션 컨텍스트가 없습니다."

    cards = context.get("cards") or []
    history = context.get("history") or []
    selected_customer = context.get("selectedCustomer") or None
    normalized_cards = []

    for index, card in enumerate(cards[:10], start=1):
        normalized_cards.append(
            {
                "priority": index,
                "recency_rule": "작을수록 최근 정보입니다.",
                "createdAt": card.get("createdAt"),
                "fileName": card.get("fileName"),
                "data": card.get("data") or {},
                "briefing": card.get("briefing") or "",
            }
        )

    return json.dumps(
        {
            "selected_customer_highest_priority": selected_customer,
            "business_cards_latest_first": normalized_cards,
            "recent_chat_history_oldest_first": history[-12:],
            "resolution_rule": (
                "selected_customer_highest_priority가 있으면 사용자가 고객 그리드에서 명시적으로 선택한 고객이므로 "
                "그 고객 정보를 최우선 작업 대상으로 삼는다. 동일한 회사명, 이름, 이메일, 전화번호, 직위 등 같은 항목이 여러 번 등장하면 "
                "business_cards_latest_first에서 priority가 더 작은 최신 항목을 우선한다. "
                "대화 내용도 recent_chat_history_oldest_first의 뒤쪽 항목일수록 최신이므로 최신 질문과 답변을 우선한다."
            ),
        },
        ensure_ascii=False,
    )


@app.post("/api/auth/login")
async def login(payload: LoginRequest, response: Response, request: Request):
    enforce_auth_rate_limit(request, "login")
    tenant_code = payload.tenant_code.strip()
    email = payload.email.strip().lower()
    if not tenant_code or not email or not payload.password:
        raise HTTPException(status_code=400, detail="테넌트, 이메일, 비밀번호를 입력해 주세요.")

    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id AS user_id,
                u.tenant_id,
                u.email,
                u.password_hash,
                u.name AS user_name,
                u.role,
                u.status AS user_status,
                t.tenant_code,
                t.name AS tenant_name,
                t.status AS tenant_status
            FROM users u
            JOIN tenants t
              ON t.id = u.tenant_id
             AND t.deleted_at IS NULL
            WHERE t.tenant_code = %s
              AND LOWER(u.email) = %s
              AND u.deleted_at IS NULL
            LIMIT 1
            """,
            (tenant_code, email),
        )
        row = cursor.fetchone()
        if not row or row["user_status"] != "active" or row["tenant_status"] not in ("active", "trial"):
            raise HTTPException(status_code=401, detail="로그인 정보를 확인해 주세요.")
        if not verify_password(payload.password, row.get("password_hash")):
            raise HTTPException(status_code=401, detail="로그인 정보를 확인해 주세요.")

        cursor.execute("UPDATE users SET last_login_at = NOW(6) WHERE id = %s", (row["user_id"],))
        session = public_session(row)
        try:
            write_audit_log(
                cursor,
                session,
                "login",
                "auth",
                row["user_id"],
                None,
                {"email": email, "tenant_code": tenant_code},
                request,
            )
        except Exception as error:
            print("Audit log write failed:", error)
        set_session_cookie(response, session)
        return {"success": True, "session": {**session, "role_label": role_label(session["role"])}}


@app.post("/api/auth/register")
async def register(payload: RegisterRequest, request: Request):
    enforce_auth_rate_limit(request, "register")
    tenant_code = payload.tenant_code.strip()
    tenant_name = payload.tenant_name.strip() or tenant_code
    name = payload.name.strip()
    email = payload.email.strip().lower()
    password = payload.password
    role = payload.role.strip()
    join_code = payload.join_code.strip()

    if not tenant_code or not name or not email or not password:
        raise HTTPException(status_code=400, detail="테넌트, 이름, 이메일, 비밀번호를 입력해 주세요.")
    if role not in USER_ROLES:
        raise HTTPException(status_code=400, detail="사용자 역할을 확인해 주세요.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상 입력해 주세요.")

    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, tenant_code, name, status
            FROM tenants
            WHERE tenant_code = %s
              AND deleted_at IS NULL
            LIMIT 1
            """,
            (tenant_code,),
        )
        tenant = cursor.fetchone()

        if tenant and tenant["status"] not in ("active", "trial"):
            raise HTTPException(status_code=409, detail="사용할 수 없는 테넌트입니다.")

        created_tenant = False
        if not tenant:
            role = "owner"
            cursor.execute(
                """
                INSERT INTO tenants (tenant_code, name, status)
                VALUES (%s, %s, 'active')
                """,
                (tenant_code, tenant_name),
            )
            tenant = {
                "id": cursor.lastrowid,
                "tenant_code": tenant_code,
                "name": tenant_name,
                "status": "active",
            }
            created_tenant = True
        else:
            if not ALLOW_EXISTING_TENANT_SELF_JOIN:
                raise HTTPException(status_code=403, detail="기존 테넌트 가입은 관리자 초대가 필요합니다.")
            if TENANT_JOIN_CODE and not hmac.compare_digest(join_code, TENANT_JOIN_CODE):
                raise HTTPException(status_code=403, detail="가입 코드가 올바르지 않습니다.")
            if role not in TENANT_SELF_JOIN_ROLES:
                role = "sales"

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE tenant_id = %s
              AND LOWER(email) = %s
              AND deleted_at IS NULL
            LIMIT 1
            """,
            (tenant["id"], email),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="이미 등록된 이메일입니다.")

        cursor.execute(
            """
            INSERT INTO users (tenant_id, email, password_hash, name, role, status, last_login_at)
            VALUES (%s, %s, %s, %s, %s, 'active', NULL)
            """,
            (tenant["id"], email, hash_password(password), name, role),
        )
        user_id = cursor.lastrowid
        audit_session = {"tenant_id": tenant["id"], "user_id": user_id}
        if created_tenant:
            write_audit_log(cursor, audit_session, "create", "tenants", tenant["id"], None, tenant, request)
        cursor.execute(
            "SELECT id, tenant_id, team_id, email, name, phone, role, status, last_login_at, created_at, updated_at, deleted_at FROM users WHERE id = %s",
            (user_id,),
        )
        created_user = cursor.fetchone()
        write_audit_log(cursor, audit_session, "create", "users", user_id, None, created_user, request)
        return {
            "success": True,
            "message": "회원가입이 완료되었습니다. 로그인해 주세요.",
            "tenant_code": tenant["tenant_code"],
            "email": email,
        }


@app.get("/api/auth/me")
async def me(request: Request):
    session = require_session(request)
    return {"success": True, "session": {**session, "role_label": role_label(session["role"])}}


@app.post("/api/auth/logout")
async def logout(response: Response, request: Request):
    session = get_session(request)
    record_audit_event(session, "logout", "auth", session["user_id"] if session else None, None, {}, request)
    clear_session_cookie(response)
    return {"success": True}


@app.get("/logout")
async def logout_page(request: Request):
    session = get_session(request)
    record_audit_event(session, "logout", "auth", session["user_id"] if session else None, None, {}, request)
    response = RedirectResponse("/login.html", status_code=303)
    clear_session_cookie(response)
    return response


@app.get("/api/admin/summary")
async def admin_summary(request: Request):
    session = require_admin_session(request)
    tenant_id = session["tenant_id"]
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, tenant_code, name, business_no, plan_code, status, timezone, locale, created_at, updated_at
            FROM tenants
            WHERE id = %s
              AND deleted_at IS NULL
            LIMIT 1
            """,
            (tenant_id,),
        )
        tenant = cursor.fetchone()
        counts = {}
        for key, table in (
            ("users", "users"),
            ("teams", "teams"),
            ("pipeline_stages", "pipeline_stages"),
            ("audit_logs", "audit_logs"),
        ):
            cursor.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE tenant_id = %s AND deleted_at IS NULL", (tenant_id,))
            counts[key] = cursor.fetchone()["count"]
        _setting_id, codes = fetch_custom_codes(cursor, tenant_id)
        counts["code_groups"] = len(codes["groups"])
        counts["code_items"] = sum(len(group.get("items") or []) for group in codes["groups"])
    record_audit_event(session, "view", "admin_summary", None, None, {"counts": counts}, request)
    return {
        "success": True,
        "tenant": admin_json_row(tenant or {}),
        "counts": counts,
        "session": {**session, "role_label": role_label(session["role"])},
    }


@app.get("/api/admin/company")
async def admin_company(request: Request):
    session = require_admin_session(request)
    tenant_id = session["tenant_id"]
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, tenant_code, name, business_no, plan_code, status, timezone, locale, created_at, updated_at
            FROM tenants
            WHERE id = %s
              AND deleted_at IS NULL
            LIMIT 1
            """,
            (tenant_id,),
        )
        tenant = cursor.fetchone()
        cursor.execute(
            """
            SELECT id, setting_key, setting_value, description, created_at, updated_at
            FROM tenant_settings
            WHERE tenant_id = %s
            ORDER BY setting_key
            """,
            (tenant_id,),
        )
        settings = cursor.fetchall()
    record_audit_event(session, "view", "tenant", tenant_id, None, {"settings_count": len(settings)}, request)
    return {"success": True, "company": admin_json_row(tenant or {}), "settings": admin_json_rows(settings)}


@app.put("/api/admin/company")
async def admin_update_company(payload: AdminCompanyPayload, request: Request):
    session = require_admin_session(request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, tenant_code, name, business_no, plan_code, status, timezone, locale, created_at, updated_at
            FROM tenants
            WHERE id = %s
              AND deleted_at IS NULL
            LIMIT 1
            """,
            (session["tenant_id"],),
        )
        before = cursor.fetchone()
        if not before:
            raise HTTPException(status_code=404, detail="회사 정보를 찾지 못했습니다.")
        after_values = {
            "name": payload.name.strip() or before["name"],
            "business_no": none_if_blank(payload.business_no),
            "plan_code": none_if_blank(payload.plan_code),
            "timezone": payload.timezone.strip() or "Asia/Seoul",
            "locale": payload.locale.strip() or "ko-KR",
        }
        cursor.execute(
            """
            UPDATE tenants
            SET name = %s,
                business_no = %s,
                plan_code = %s,
                timezone = %s,
                locale = %s
            WHERE id = %s
              AND deleted_at IS NULL
            """,
            (
                after_values["name"],
                after_values["business_no"],
                after_values["plan_code"],
                after_values["timezone"],
                after_values["locale"],
                session["tenant_id"],
            ),
        )
        cursor.execute(
            """
            SELECT id, tenant_code, name, business_no, plan_code, status, timezone, locale, created_at, updated_at
            FROM tenants
            WHERE id = %s
            LIMIT 1
            """,
            (session["tenant_id"],),
        )
        after = cursor.fetchone()
        write_audit_log(cursor, session, "update", "tenant", session["tenant_id"], before, after, request)
    return {"success": True, "company": admin_json_row(after)}


@app.get("/api/admin/users")
async def admin_users(request: Request):
    session = require_admin_session(request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id, u.email, u.name, u.phone, u.role, u.status, u.team_id,
                t.name AS team_name, u.last_login_at, u.created_at, u.updated_at
            FROM users u
            LEFT JOIN teams t
                   ON t.id = u.team_id
                  AND t.tenant_id = u.tenant_id
                  AND t.deleted_at IS NULL
            WHERE u.tenant_id = %s
              AND u.deleted_at IS NULL
            ORDER BY u.created_at DESC, u.id DESC
            """,
            (session["tenant_id"],),
        )
        users = cursor.fetchall()
    record_audit_event(session, "list", "user", None, None, {"count": len(users)}, request)
    return {
        "success": True,
        "users": admin_json_rows(users),
        "roles": [{"value": key, "label": role_label(key)} for key in USER_ROLES],
        "statuses": sorted(USER_STATUS_VALUES),
    }


@app.post("/api/admin/users/invite")
async def admin_invite_user(payload: AdminInviteUserPayload, request: Request):
    session = require_admin_session(request)
    email = payload.email.strip().lower()
    name = payload.name.strip()
    role = payload.role.strip()
    if not email or not name:
        raise HTTPException(status_code=400, detail="초대할 사용자 이름과 이메일을 입력해 주세요.")
    if role not in USER_ROLES or role == "owner":
        raise HTTPException(status_code=400, detail="초대 가능한 사용자 역할을 확인해 주세요.")

    temporary_password = temporary_invite_password()
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        if payload.team_id is not None:
            ensure_admin_target_belongs(cursor, "teams", payload.team_id, session["tenant_id"])
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE tenant_id = %s
              AND LOWER(email) = %s
              AND deleted_at IS NULL
            LIMIT 1
            """,
            (session["tenant_id"], email),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="이미 등록된 사용자 이메일입니다.")
        cursor.execute(
            """
            INSERT INTO users (tenant_id, team_id, email, password_hash, name, phone, role, status, last_login_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'invited', NULL)
            """,
            (
                session["tenant_id"],
                payload.team_id,
                email,
                hash_password(temporary_password),
                name,
                none_if_blank(payload.phone),
                role,
            ),
        )
        user_id = cursor.lastrowid
        cursor.execute(
            "SELECT id, email, name, phone, role, status, team_id, last_login_at, created_at, updated_at FROM users WHERE id = %s",
            (user_id,),
        )
        after = cursor.fetchone()
        write_audit_log(cursor, session, "invite", "user", user_id, None, after, request)
    return {"success": True, "user": admin_json_row(after), "temporary_password": temporary_password}


@app.put("/api/admin/users/{user_id}")
async def admin_update_user(user_id: int, payload: AdminUserPayload, request: Request):
    session = require_admin_session(request)
    if payload.role not in USER_ROLES:
        raise HTTPException(status_code=400, detail="사용자 역할을 확인해 주세요.")
    if payload.status not in USER_STATUS_VALUES:
        raise HTTPException(status_code=400, detail="사용자 상태를 확인해 주세요.")

    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        before = ensure_admin_target_belongs(cursor, "users", user_id, session["tenant_id"])
        if user_id == session["user_id"] and (payload.role != before["role"] or payload.status != before["status"]):
            raise HTTPException(status_code=400, detail="본인의 역할이나 상태는 직접 변경할 수 없습니다.")
        if payload.team_id is not None:
            ensure_admin_target_belongs(cursor, "teams", payload.team_id, session["tenant_id"])
        cursor.execute(
            """
            UPDATE users
            SET name = %s,
                phone = %s,
                role = %s,
                status = %s,
                team_id = %s
            WHERE id = %s
              AND tenant_id = %s
              AND deleted_at IS NULL
            """,
            (
                payload.name.strip() or before["name"],
                none_if_blank(payload.phone),
                payload.role,
                payload.status,
                payload.team_id,
                user_id,
                session["tenant_id"],
            ),
        )
        cursor.execute(
            "SELECT id, email, name, phone, role, status, team_id, last_login_at, created_at, updated_at FROM users WHERE id = %s",
            (user_id,),
        )
        after = cursor.fetchone()
        write_audit_log(cursor, session, "update", "user", user_id, before, after, request)
    return {"success": True, "user": admin_json_row(after)}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, request: Request):
    session = require_admin_session(request)
    if user_id == session["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own signed-in user.")

    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        before = ensure_admin_target_belongs(cursor, "users", user_id, session["tenant_id"])
        cursor.execute(
            """
            UPDATE users
            SET status = 'disabled',
                team_id = NULL,
                deleted_at = NOW(6)
            WHERE id = %s
              AND tenant_id = %s
              AND deleted_at IS NULL
            """,
            (user_id, session["tenant_id"]),
        )
        write_audit_log(cursor, session, "delete", "user", user_id, before, None, request)
    return {"success": True}


@app.get("/api/admin/teams")
async def admin_teams(request: Request):
    session = require_admin_session(request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                t.id, t.parent_team_id, p.name AS parent_team_name, t.name, t.description,
                t.sort_order, COUNT(u.id) AS member_count, t.created_at, t.updated_at
            FROM teams t
            LEFT JOIN teams p
                   ON p.id = t.parent_team_id
                  AND p.tenant_id = t.tenant_id
                  AND p.deleted_at IS NULL
            LEFT JOIN users u
                   ON u.team_id = t.id
                  AND u.tenant_id = t.tenant_id
                  AND u.deleted_at IS NULL
            WHERE t.tenant_id = %s
              AND t.deleted_at IS NULL
            GROUP BY t.id, t.parent_team_id, p.name, t.name, t.description, t.sort_order, t.created_at, t.updated_at
            ORDER BY t.sort_order, t.name
            """,
            (session["tenant_id"],),
        )
        teams = cursor.fetchall()
        _setting_id, leader_map = fetch_team_leaders(cursor, session["tenant_id"])
        cursor.execute(
            """
            SELECT id, name, email, team_id, role, status
            FROM users
            WHERE tenant_id = %s
              AND deleted_at IS NULL
            ORDER BY name, email
            """,
            (session["tenant_id"],),
        )
        users = cursor.fetchall()

    user_by_id = {row["id"]: admin_json_row(row) for row in users}
    members_by_team: dict[int, list[dict[str, Any]]] = {}
    for user in users:
        if user.get("team_id"):
            members_by_team.setdefault(user["team_id"], []).append(admin_json_row(user))

    enriched_teams = []
    for team in teams:
        row = admin_json_row(team)
        leader_user_id = leader_map.get(str(team["id"]))
        row["leader_user_id"] = leader_user_id
        row["leader_name"] = user_by_id.get(leader_user_id, {}).get("name", "") if leader_user_id else ""
        row["leader_email"] = user_by_id.get(leader_user_id, {}).get("email", "") if leader_user_id else ""
        row["members"] = members_by_team.get(team["id"], [])
        row["member_user_ids"] = [member["id"] for member in row["members"]]
        enriched_teams.append(row)
    record_audit_event(session, "list", "team", None, None, {"count": len(enriched_teams)}, request)
    return {"success": True, "teams": enriched_teams, "users": admin_json_rows(users)}


@app.post("/api/admin/teams")
async def admin_create_team(payload: AdminTeamPayload, request: Request):
    session = require_admin_session(request)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="팀 이름을 입력해 주세요.")
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        if payload.parent_team_id is not None:
            ensure_admin_target_belongs(cursor, "teams", payload.parent_team_id, session["tenant_id"])
        member_user_ids = validate_team_members(cursor, payload.member_user_ids, session["tenant_id"])
        if payload.leader_user_id is not None:
            ensure_admin_user_belongs(cursor, payload.leader_user_id, session["tenant_id"])
            if payload.leader_user_id not in member_user_ids:
                member_user_ids.append(payload.leader_user_id)
        cursor.execute(
            """
            INSERT INTO teams (tenant_id, parent_team_id, name, description, sort_order)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (session["tenant_id"], payload.parent_team_id, name, none_if_blank(payload.description), payload.sort_order),
        )
        team_id = cursor.lastrowid
        if member_user_ids:
            placeholders = ",".join(["%s"] * len(member_user_ids))
            cursor.execute(
                f"UPDATE users SET team_id = %s WHERE tenant_id = %s AND id IN ({placeholders})",
                (team_id, session["tenant_id"], *member_user_ids),
            )
        if payload.leader_user_id is not None:
            _setting_id, leader_map = fetch_team_leaders(cursor, session["tenant_id"])
            leader_map[str(team_id)] = payload.leader_user_id
            save_team_leaders(cursor, session["tenant_id"], leader_map)
        after = ensure_admin_target_belongs(cursor, "teams", team_id, session["tenant_id"])
        write_audit_log(cursor, session, "create", "team", team_id, None, after, request)
    return {"success": True, "team": admin_json_row(after)}


@app.put("/api/admin/teams/{team_id}")
async def admin_update_team(team_id: int, payload: AdminTeamPayload, request: Request):
    session = require_admin_session(request)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="팀 이름을 입력해 주세요.")
    if payload.parent_team_id == team_id:
        raise HTTPException(status_code=400, detail="자기 자신을 상위 팀으로 지정할 수 없습니다.")
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        before = ensure_admin_target_belongs(cursor, "teams", team_id, session["tenant_id"])
        if payload.parent_team_id is not None:
            ensure_admin_target_belongs(cursor, "teams", payload.parent_team_id, session["tenant_id"])
        member_user_ids = validate_team_members(cursor, payload.member_user_ids, session["tenant_id"])
        if payload.leader_user_id is not None:
            ensure_admin_user_belongs(cursor, payload.leader_user_id, session["tenant_id"])
            if payload.leader_user_id not in member_user_ids:
                member_user_ids.append(payload.leader_user_id)
        cursor.execute(
            """
            UPDATE teams
            SET parent_team_id = %s,
                name = %s,
                description = %s,
                sort_order = %s
            WHERE id = %s
              AND tenant_id = %s
              AND deleted_at IS NULL
            """,
            (payload.parent_team_id, name, none_if_blank(payload.description), payload.sort_order, team_id, session["tenant_id"]),
        )
        cursor.execute("UPDATE users SET team_id = NULL WHERE tenant_id = %s AND team_id = %s", (session["tenant_id"], team_id))
        if member_user_ids:
            placeholders = ",".join(["%s"] * len(member_user_ids))
            cursor.execute(
                f"UPDATE users SET team_id = %s WHERE tenant_id = %s AND id IN ({placeholders})",
                (team_id, session["tenant_id"], *member_user_ids),
            )
        _setting_id, leader_map = fetch_team_leaders(cursor, session["tenant_id"])
        if payload.leader_user_id is None:
            leader_map.pop(str(team_id), None)
        else:
            leader_map[str(team_id)] = payload.leader_user_id
        save_team_leaders(cursor, session["tenant_id"], leader_map)
        after = ensure_admin_target_belongs(cursor, "teams", team_id, session["tenant_id"])
        write_audit_log(
            cursor,
            session,
            "update",
            "team",
            team_id,
            {**before, "leader_map": leader_map.get(str(team_id)), "member_user_ids": []},
            {**after, "leader_user_id": payload.leader_user_id, "member_user_ids": member_user_ids},
            request,
        )
    return {"success": True, "team": admin_json_row(after)}


@app.delete("/api/admin/teams/{team_id}")
async def admin_delete_team(team_id: int, request: Request):
    session = require_admin_session(request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        before = ensure_admin_target_belongs(cursor, "teams", team_id, session["tenant_id"])
        cursor.execute("UPDATE users SET team_id = NULL WHERE tenant_id = %s AND team_id = %s", (session["tenant_id"], team_id))
        _setting_id, leader_map = fetch_team_leaders(cursor, session["tenant_id"])
        leader_map.pop(str(team_id), None)
        save_team_leaders(cursor, session["tenant_id"], leader_map)
        cursor.execute(
            "UPDATE teams SET deleted_at = NOW(6) WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL",
            (team_id, session["tenant_id"]),
        )
        write_audit_log(cursor, session, "delete", "team", team_id, before, None, request)
    return {"success": True}


@app.get("/api/admin/roles")
async def admin_roles(request: Request):
    session = require_admin_session(request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT role, COUNT(*) AS user_count
            FROM users
            WHERE tenant_id = %s
              AND deleted_at IS NULL
            GROUP BY role
            """,
            (session["tenant_id"],),
        )
        counts = {row["role"]: row["user_count"] for row in cursor.fetchall()}
    permissions = {
        "owner": ["회사 정보 관리", "사용자/팀 관리", "권한 확인", "영업 단계 설정", "사용로그 조회"],
        "admin": ["회사 정보 관리", "사용자/팀 관리", "권한 확인", "영업 단계 설정", "사용로그 조회"],
        "manager": ["팀 고객/영업 업무 관리", "영업 단계 조회"],
        "sales": ["본인 고객/영업 업무 관리"],
        "viewer": ["조회 전용"],
    }
    roles = [
        {"value": key, "label": role_label(key), "user_count": counts.get(key, 0), "permissions": permissions.get(key, [])}
        for key in USER_ROLES
    ]
    record_audit_event(session, "view", "role", None, None, {"count": len(roles)}, request)
    return {"success": True, "roles": roles}


@app.get("/api/admin/codes")
async def admin_codes(request: Request):
    session = require_admin_session(request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        _setting_id, codes = fetch_custom_codes(cursor, session["tenant_id"])
    record_audit_event(
        session,
        "view",
        "custom_codes",
        None,
        None,
        {"groups": len(codes.get("groups") or [])},
        request,
    )
    return {"success": True, "codes": codes}


@app.put("/api/admin/codes")
async def admin_update_codes(payload: AdminCodesPayload, request: Request):
    session = require_admin_session(request)
    codes = normalized_custom_codes(payload)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        setting_id, before = fetch_custom_codes(cursor, session["tenant_id"])
        setting_value = json.dumps(codes, ensure_ascii=False)
        if setting_id:
            cursor.execute(
                """
                UPDATE tenant_settings
                SET setting_value = %s,
                    description = %s
                WHERE id = %s
                  AND tenant_id = %s
                """,
                (setting_value, "관리자 코드관리 사용자 정의 코드", setting_id, session["tenant_id"]),
            )
            entity_id = setting_id
        else:
            cursor.execute(
                """
                INSERT INTO tenant_settings (tenant_id, setting_key, setting_value, description)
                VALUES (%s, %s, %s, %s)
                """,
                (session["tenant_id"], CUSTOM_CODES_SETTING_KEY, setting_value, "관리자 코드관리 사용자 정의 코드"),
            )
            entity_id = cursor.lastrowid
        write_audit_log(cursor, session, "update", "custom_codes", entity_id, before, codes, request)
    return {"success": True, "codes": codes}


@app.get("/api/admin/pipeline-stages")
async def admin_pipeline_stages(request: Request):
    session = require_admin_session(request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, stage_code, name, description, probability_percent, sort_order, is_active, created_at, updated_at
            FROM pipeline_stages
            WHERE tenant_id = %s
              AND deleted_at IS NULL
            ORDER BY sort_order, id
            """,
            (session["tenant_id"],),
        )
        stages = cursor.fetchall()
    record_audit_event(session, "list", "pipeline_stage", None, None, {"count": len(stages)}, request)
    return {"success": True, "stages": admin_json_rows(stages), "stage_codes": sorted(PIPELINE_STAGE_CODES), "default_stages": DEFAULT_PIPELINE_STAGES}


@app.post("/api/admin/pipeline-stages/defaults")
async def admin_create_default_pipeline_stages(request: Request):
    session = require_admin_session(request)
    created: list[dict[str, Any]] = []
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT stage_code
            FROM pipeline_stages
            WHERE tenant_id = %s
              AND deleted_at IS NULL
            """,
            (session["tenant_id"],),
        )
        existing = {row["stage_code"] for row in cursor.fetchall()}
        for stage in DEFAULT_PIPELINE_STAGES:
            if stage["stage_code"] in existing:
                continue
            cursor.execute(
                """
                INSERT INTO pipeline_stages (
                    tenant_id, stage_code, name, description, probability_percent, sort_order, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, 1)
                """,
                (
                    session["tenant_id"],
                    stage["stage_code"],
                    stage["name"],
                    stage["description"],
                    stage["probability_percent"],
                    stage["sort_order"],
                ),
            )
            stage_id = cursor.lastrowid
            after = ensure_admin_target_belongs(cursor, "pipeline_stages", stage_id, session["tenant_id"])
            created.append(admin_json_row(after))
        if created:
            write_audit_log(cursor, session, "create_defaults", "pipeline_stage", None, None, {"created": created}, request)
    return {"success": True, "created": created, "count": len(created)}


@app.post("/api/admin/pipeline-stages")
async def admin_create_pipeline_stage(payload: AdminPipelineStagePayload, request: Request):
    session = require_admin_session(request)
    if payload.stage_code not in PIPELINE_STAGE_CODES:
        raise HTTPException(status_code=400, detail="영업 단계 코드를 확인해 주세요.")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="단계 이름을 입력해 주세요.")
    probability = max(0, min(100, payload.probability_percent))
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            INSERT INTO pipeline_stages (
                tenant_id, stage_code, name, description, probability_percent, sort_order, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session["tenant_id"],
                payload.stage_code,
                payload.name.strip(),
                none_if_blank(payload.description),
                probability,
                payload.sort_order,
                1 if payload.is_active else 0,
            ),
        )
        stage_id = cursor.lastrowid
        after = ensure_admin_target_belongs(cursor, "pipeline_stages", stage_id, session["tenant_id"])
        write_audit_log(cursor, session, "create", "pipeline_stage", stage_id, None, after, request)
    return {"success": True, "stage": admin_json_row(after)}


@app.put("/api/admin/pipeline-stages/{stage_id}")
async def admin_update_pipeline_stage(stage_id: int, payload: AdminPipelineStagePayload, request: Request):
    session = require_admin_session(request)
    if payload.stage_code not in PIPELINE_STAGE_CODES:
        raise HTTPException(status_code=400, detail="영업 단계 코드를 확인해 주세요.")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="단계 이름을 입력해 주세요.")
    probability = max(0, min(100, payload.probability_percent))
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        before = ensure_admin_target_belongs(cursor, "pipeline_stages", stage_id, session["tenant_id"])
        cursor.execute(
            """
            UPDATE pipeline_stages
            SET stage_code = %s,
                name = %s,
                description = %s,
                probability_percent = %s,
                sort_order = %s,
                is_active = %s
            WHERE id = %s
              AND tenant_id = %s
              AND deleted_at IS NULL
            """,
            (
                payload.stage_code,
                payload.name.strip(),
                none_if_blank(payload.description),
                probability,
                payload.sort_order,
                1 if payload.is_active else 0,
                stage_id,
                session["tenant_id"],
            ),
        )
        after = ensure_admin_target_belongs(cursor, "pipeline_stages", stage_id, session["tenant_id"])
        write_audit_log(cursor, session, "update", "pipeline_stage", stage_id, before, after, request)
    return {"success": True, "stage": admin_json_row(after)}


@app.delete("/api/admin/pipeline-stages/{stage_id}")
async def admin_delete_pipeline_stage(stage_id: int, request: Request):
    session = require_admin_session(request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        before = ensure_admin_target_belongs(cursor, "pipeline_stages", stage_id, session["tenant_id"])
        cursor.execute(
            "UPDATE pipeline_stages SET deleted_at = NOW(6) WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL",
            (stage_id, session["tenant_id"]),
        )
        write_audit_log(cursor, session, "delete", "pipeline_stage", stage_id, before, None, request)
    return {"success": True}


@app.get("/api/admin/logs")
async def admin_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
):
    session = require_admin_session(request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                l.id, l.actor_user_id, u.name AS actor_name, u.email AS actor_email,
                l.action, l.entity_type, l.entity_id, l.ip_address, l.user_agent,
                l.before_json, l.after_json, l.created_at
            FROM audit_logs l
            LEFT JOIN users u
                   ON u.id = l.actor_user_id
                  AND u.tenant_id = l.tenant_id
            WHERE l.tenant_id = %s
              AND l.deleted_at IS NULL
            ORDER BY l.created_at DESC, l.id DESC
            LIMIT %s
            """,
            (session["tenant_id"], limit),
        )
        logs = cursor.fetchall()
    record_audit_event(session, "list", "audit_log", None, None, {"count": len(logs), "limit": limit}, request)
    return {"success": True, "logs": admin_json_rows(logs)}


@app.post("/api/extract")
async def extract_business_card(
    request: Request,
    file: UploadFile = File(...),
    skip_briefing: bool = Query(default=False),
):
    session = require_session(request)
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 명함 인식 분석을 실행할 수 있습니다.")
    enforce_content_length(request, MAX_UPLOAD_BYTES)

    try:
        contents = await read_upload_limited(file, MAX_UPLOAD_BYTES)
        result = app_graph.invoke(
            {
                "image_bytes": contents,
                "card_info": {},
                "missing_fields": [],
                "company_briefing": "",
                "is_business_card": False,
                "skip_briefing": skip_briefing,
            }
        )
        if not result.get("is_business_card", False):
            try:
                social_profile = extract_social_profile_screenshot(contents)
            except Exception as error:
                print("SNS profile screenshot extraction failed:", error)
                social_profile = {"is_social_profile": False, "display_name": ""}

            if social_profile.get("is_social_profile") and str(social_profile.get("display_name") or "").strip():
                customer = save_social_profile_screenshot_customer(
                    social_profile,
                    file.filename or "",
                    session["tenant_id"],
                    session["user_id"],
                    session,
                    request,
                )
                record_audit_event(
                    session,
                    "extract",
                    "business_card",
                    customer.get("id") if customer else None,
                    None,
                    {
                        "file_name": file.filename or "",
                        "is_business_card": False,
                        "is_social_profile": True,
                        "platform": social_profile.get("platform") or "",
                    },
                    request,
                )
                return {
                    "success": True,
                    "is_business_card": False,
                    "is_social_profile": True,
                    "data": {
                        "회사명": social_profile.get("company_name") or social_profile.get("display_name") or "",
                        "이름": social_profile.get("display_name") or "",
                        "직무": social_profile.get("headline") or "SNS 프로필 화면 캡처",
                        "직위": social_profile.get("platform") or "SNS",
                        "휴대전화": "",
                        "이메일": "",
                        "홈페이지": social_profile.get("profile_url") or "",
                        "SNS종류": social_profile.get("platform") or "SNS",
                        "SNS대상": "profile_screenshot",
                        "SNS링크": social_profile.get("profile_url") or "",
                        "SNS요약": social_profile.get("summary") or "",
                    },
                    "briefing": social_profile.get("summary") or "",
                    "customer": customer,
                    "social_profile": social_profile,
                }

        customer = (
            save_extracted_customer(
                result.get("card_info", {}),
                result.get("company_briefing", ""),
                file.filename or "",
                session["tenant_id"],
                session["user_id"],
                session,
                request,
            )
            if result.get("is_business_card", False)
            else None
        )
        record_audit_event(
            session,
            "extract",
            "business_card",
            customer.get("id") if customer else None,
            None,
            {
                "file_name": file.filename or "",
                "is_business_card": bool(result.get("is_business_card", False)),
                "is_social_profile": False,
                "saved": bool(customer),
            },
            request,
        )
        return {
            "success": True,
            "is_business_card": result.get("is_business_card", False),
            "is_social_profile": False,
            "data": result.get("card_info", {}),
            "briefing": result.get("company_briefing", ""),
            "customer": customer,
        }
    except HTTPException:
        raise
    except mysql.connector.Error as error:
        return database_error_response(error, request)
    except Exception as error:
        print("Business card extraction failed:", error)
        return internal_error_response("이미지 분석 중 오류가 발생했습니다.", request=request)


@app.post("/api/extract/document")
async def extract_sales_document(request: Request, file: UploadFile = File(...)):
    session = require_session(request)
    enforce_content_length(request, MAX_UPLOAD_BYTES)
    if not is_supported_document_upload(file):
        raise HTTPException(status_code=400, detail="Word, Excel, PDF, 텍스트 파일만 문서 분석을 실행할 수 있습니다.")

    contents = await read_upload_limited(file, MAX_UPLOAD_BYTES)
    original_filename = safe_original_filename(file.filename)
    content_type = (file.content_type or "application/octet-stream").split(";")[0].strip()
    extracted_text = extract_document_text(contents, original_filename, content_type).strip()
    info = extract_sales_document_info(contents, original_filename, content_type, extracted_text)
    if info.document_type not in {"quote", "contract"}:
        record_audit_event(
            session,
            "extract",
            "sales_document",
            None,
            None,
            {
                "filename": original_filename,
                "document_type": info.document_type,
                "saved": False,
                "size_bytes": len(contents),
            },
            request,
        )
        return {
            "success": True,
            "saved": False,
            "document_type": info.document_type,
            "reply": "업로드한 문서를 분석했지만 견적서나 계약서로 확정하지 못해 DB에는 저장하지 않았습니다.",
            "extracted": info.model_dump(),
        }

    storage_path, stored_filename = stored_document_path(session, original_filename)
    entity_type = "quote" if info.document_type == "quote" else "contract"
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        if info.document_type == "quote":
            entity = save_quote_from_document(cursor, session, info, request)
            entity_id = entity["id"]
            target_menu = "quotes"
        else:
            entity = save_contract_from_document(cursor, session, info, request)
            entity_id = entity["id"]
            target_menu = "contracts"

        storage_path.write_bytes(contents)
        document = insert_uploaded_document(
            cursor,
            session,
            entity_type,
            entity_id,
            original_filename,
            stored_filename,
            storage_path,
            content_type,
            contents,
            extracted_text,
            info.model_dump(),
        )
        write_audit_log(
            cursor,
            session,
            "create",
            "uploaded_documents",
            document["id"],
            None,
            {
                **document,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "size_bytes": len(contents),
                "sha256": hashlib.sha256(contents).hexdigest(),
            },
            request,
        )

    record_audit_event(
        session,
        "extract",
        "sales_document",
        entity_id,
        None,
        {
            "filename": original_filename,
            "document_type": info.document_type,
            "document_id": document["id"],
            "saved": True,
        },
        request,
    )
    return {
        "success": True,
        "saved": True,
        "document_type": info.document_type,
        "target_menu": target_menu,
        "entity": entity,
        "document": document,
        "extracted": info.model_dump(),
        "reply": f"{'견적서' if info.document_type == 'quote' else '계약서'} 문서를 분석해 DB에 저장했습니다.",
    }


@app.post("/api/extract/sns")
async def extract_sns_links(payload: SnsLinksRequest, request: Request):
    session = require_session(request)
    links = extract_social_links(payload.message)
    if not links:
        raise HTTPException(status_code=400, detail="지원하는 SNS 링크를 찾지 못했습니다.")
    if len(links) > MAX_SNS_LINKS_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"SNS 링크는 한 번에 최대 {MAX_SNS_LINKS_PER_REQUEST}개까지 처리할 수 있습니다.")

    try:
        items = [save_sns_customer(link, session["tenant_id"], session["user_id"]) for link in links]
        saved_count = sum(1 for item in items if item.get("saved"))
        pending_count = sum(1 for item in items if item.get("needs_confirmation"))
        record_audit_event(
            session,
            "extract",
            "sns",
            None,
            None,
            {"link_count": len(links), "saved_count": saved_count, "pending_count": pending_count},
            request,
        )
        return {"success": True, "count": saved_count, "pending_count": pending_count, "items": items}
    except HTTPException:
        raise
    except mysql.connector.Error as error:
        return database_error_response(error, request)
    except Exception as error:
        print("SNS extraction failed:", error)
        return internal_error_response("SNS 링크 처리 중 오류가 발생했습니다.", request=request)


@app.post("/api/inspect/sns")
async def inspect_sns_links(payload: SnsLinksRequest, request: Request):
    session = require_session(request)
    links = extract_social_links(payload.message)
    if not links:
        raise HTTPException(status_code=400, detail="지원하는 SNS 링크를 찾지 못했습니다.")
    if len(links) > MAX_SNS_LINKS_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"SNS 링크는 한 번에 최대 {MAX_SNS_LINKS_PER_REQUEST}개까지 확인할 수 있습니다.")

    effective_context = payload.context if isinstance(payload.context, dict) else {}
    resolved_customer = None
    customer_candidates: list[dict[str, Any]] = []
    try:
        with db_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            effective_context, customer_candidates, resolved_customer = resolve_command_customer_preflight(
                cursor,
                session,
                payload.message,
                effective_context,
            )
    except HTTPException:
        raise
    except mysql.connector.Error as error:
        return database_error_response(error, request)
    except Exception as error:
        print("SNS customer command preflight failed:", error)
        return internal_error_response("고객 정보를 먼저 확인하는 중 오류가 발생했습니다.", request=request)

    if customer_candidates:
        record_audit_event(
            session,
            "list",
            "customer_command_candidates",
            None,
            None,
            {"message_preview": payload.message[:300], "candidate_count": len(customer_candidates), "source": "sns"},
            request,
        )
        return {
            "success": True,
            "reply": "SNS 링크 정보를 확인하기 전에 고객을 먼저 확인해 주세요. 아래 후보 중 이번 작업 대상 고객을 선택하면 같은 명령을 이어서 처리하겠습니다.",
            "customer_selection_required": True,
            "pending_message": payload.message,
            "candidates": admin_json_rows(customer_candidates),
        }

    try:
        items = [inspect_social_link(link) for link in links]
        record_audit_event(
            session,
            "inspect",
            "sns",
            selected_customer_id_from_context(effective_context),
            None,
            {
                "link_count": len(items),
                "resolved_customer_id": resolved_customer.get("contact_id") if resolved_customer else None,
            },
            request,
        )
        return {
            "success": True,
            "count": len(items),
            "items": items,
            "resolved_customer": admin_json_row(contact_row_to_customer(resolved_customer)) if resolved_customer else None,
        }
    except HTTPException:
        raise
    except mysql.connector.Error as error:
        return database_error_response(error, request)
    except Exception as error:
        print("SNS inspection failed:", error)
        return internal_error_response("SNS 링크 정보를 확인하는 중 오류가 발생했습니다.", request=request)


@app.get("/api/documents/{document_id}/download")
async def download_document(document_id: int, request: Request):
    session = require_session(request)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, tenant_id, owner_user_id, original_filename, storage_path, content_type
            FROM uploaded_documents
            WHERE id = %s
              AND tenant_id = %s
              AND owner_user_id = %s
              AND deleted_at IS NULL
            """,
            (document_id, session["tenant_id"], session["user_id"]),
        )
        document = cursor.fetchone()
    if not document:
        raise HTTPException(status_code=404, detail="문서 파일을 찾을 수 없습니다.")
    path = Path(document["storage_path"]).resolve()
    base = DOCUMENT_UPLOAD_DIR.resolve()
    try:
        path.relative_to(base)
    except Exception:
        raise HTTPException(status_code=403, detail="허용되지 않은 문서 경로입니다.")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="문서 파일이 서버에 없습니다.")
    record_audit_event(
        session,
        "download",
        "uploaded_document",
        document_id,
        None,
        {"filename": document["original_filename"]},
        request,
    )
    return FileResponse(
        path,
        media_type=document.get("content_type") or "application/octet-stream",
        filename=document["original_filename"],
    )


@app.get("/api/db/health")
async def db_health():
    try:
        with db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"success": True, "status": "ok"}
    except mysql.connector.Error as error:
        return database_error_response(error)
    except Exception as error:
        print("DB health check failed:", error)
        return internal_error_response("DB 상태를 확인할 수 없습니다.", status_code=503, error_code="FSI-DB-CONNECTION", request=None)


@app.get("/api/customers")
async def list_customers(
    request: Request,
    search: str = "",
    company_name: str = "",
    contact_name: str = "",
    limit: int = Query(default=100, ge=1, le=500),
):
    session = require_session(request)
    current_tenant_id = session["tenant_id"]
    current_user_id = session["user_id"]
    query = """
        SELECT
            c.id AS contact_id,
            c.tenant_id,
            c.account_id,
            c.owner_user_id,
            c.name AS contact_name,
            c.title,
            c.department,
            c.email,
            c.phone,
            c.mobile,
            c.is_primary,
            c.created_at,
            c.updated_at,
            a.name AS company_name,
            a.website,
            a.phone AS account_phone,
            a.address,
            a.business_no,
            a.industry
        FROM contacts c
        LEFT JOIN accounts a
               ON a.id = c.account_id
              AND a.tenant_id = c.tenant_id
              AND a.deleted_at IS NULL
        WHERE c.tenant_id = %s
          AND c.owner_user_id = %s
          AND c.deleted_at IS NULL
          AND (
                %s = ''
             OR a.name LIKE %s
             OR c.name LIKE %s
             OR c.mobile LIKE %s
             OR c.email LIKE %s
          )
          AND (%s = '' OR a.name LIKE %s)
          AND (%s = '' OR c.name LIKE %s)
        ORDER BY c.created_at DESC, c.id DESC
        LIMIT %s
    """
    keyword = f"%{search.strip()}%"
    company_keyword = f"%{company_name.strip()}%"
    contact_keyword = f"%{contact_name.strip()}%"
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            query,
            (
                current_tenant_id,
                current_user_id,
                search.strip(),
                keyword,
                keyword,
                keyword,
                keyword,
                company_name.strip(),
                company_keyword,
                contact_name.strip(),
                contact_keyword,
                limit,
            ),
        )
        customers = [contact_row_to_customer(row) for row in cursor.fetchall()]
    record_audit_event(
        session,
        "list",
        "customer",
        None,
        None,
        {
            "count": len(customers),
            "search": search.strip(),
            "company_name": company_name.strip(),
            "contact_name": contact_name.strip(),
            "limit": limit,
        },
        request,
    )
    return {"success": True, "customers": customers}


@app.get("/api/opportunities")
async def list_opportunities(
    request: Request,
    name: str = "",
    status: str = "",
    company_name: str = "",
    limit: int = Query(default=100, ge=1, le=500),
):
    session = require_session(request)
    name_keyword = f"%{name.strip()}%"
    status_keyword = f"%{status.strip()}%"
    company_keyword = f"%{company_name.strip()}%"
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                o.id, o.name, o.status, o.amount, o.currency, o.probability_percent,
                o.close_date, o.created_at, o.updated_at,
                a.name AS company_name,
                c.name AS contact_name,
                ps.name AS stage_name,
                ps.stage_code
            FROM opportunities o
            LEFT JOIN accounts a
                   ON a.id = o.account_id
                  AND a.tenant_id = o.tenant_id
                  AND a.deleted_at IS NULL
            LEFT JOIN contacts c
                   ON c.id = o.contact_id
                  AND c.tenant_id = o.tenant_id
                  AND c.deleted_at IS NULL
            LEFT JOIN pipeline_stages ps
                   ON ps.id = o.pipeline_stage_id
                  AND ps.tenant_id = o.tenant_id
                  AND ps.deleted_at IS NULL
            WHERE o.tenant_id = %s
              AND o.owner_user_id = %s
              AND o.deleted_at IS NULL
              AND (%s = '' OR o.name LIKE %s)
              AND (%s = '' OR o.status LIKE %s)
              AND (%s = '' OR a.name LIKE %s)
            ORDER BY o.updated_at DESC, o.id DESC
            LIMIT %s
            """,
            (
                session["tenant_id"],
                session["user_id"],
                name.strip(),
                name_keyword,
                status.strip(),
                status_keyword,
                company_name.strip(),
                company_keyword,
                limit,
            ),
        )
        opportunities = admin_json_rows(cursor.fetchall())
    record_audit_event(
        session,
        "list",
        "opportunity",
        None,
        None,
        {"count": len(opportunities), "name": name.strip(), "status": status.strip(), "company_name": company_name.strip()},
        request,
    )
    return {"success": True, "opportunities": opportunities}


@app.get("/api/calendar")
async def list_calendar_events(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    session = require_session(request)
    start_date = date(year, month, 1)
    end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    events: list[dict[str, Any]] = []
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                m.id, 'meeting' AS source_type, m.title, m.status,
                m.started_at AS starts_at, m.ended_at AS ends_at,
                m.location, a.name AS company_name
            FROM meetings m
            LEFT JOIN accounts a
                   ON a.id = m.account_id
                  AND a.tenant_id = m.tenant_id
                  AND a.deleted_at IS NULL
            WHERE m.tenant_id = %s
              AND m.organizer_user_id = %s
              AND m.deleted_at IS NULL
              AND m.started_at >= %s
              AND m.started_at < %s
            ORDER BY m.started_at, m.id
            """,
            (session["tenant_id"], session["user_id"], start_date, end_date),
        )
        events.extend(admin_json_rows(cursor.fetchall()))
        cursor.execute(
            """
            SELECT
                a.id, 'activity' AS source_type, a.subject AS title, a.status,
                a.due_at AS starts_at, a.completed_at AS ends_at,
                a.activity_type AS location, ac.name AS company_name
            FROM activities a
            LEFT JOIN accounts ac
                   ON ac.id = a.account_id
                  AND ac.tenant_id = a.tenant_id
                  AND ac.deleted_at IS NULL
            WHERE a.tenant_id = %s
              AND a.owner_user_id = %s
              AND a.deleted_at IS NULL
              AND a.due_at >= %s
              AND a.due_at < %s
            ORDER BY a.due_at, a.id
            """,
            (session["tenant_id"], session["user_id"], start_date, end_date),
        )
        events.extend(admin_json_rows(cursor.fetchall()))
        cursor.execute(
            """
            SELECT
                ai.id, 'action_item' AS source_type, ai.title, ai.status,
                ai.due_date AS starts_at, ai.completed_at AS ends_at,
                ai.priority AS location, NULL AS company_name
            FROM action_items ai
            WHERE ai.tenant_id = %s
              AND (ai.assignee_user_id = %s OR ai.reporter_user_id = %s)
              AND ai.deleted_at IS NULL
              AND ai.due_date >= %s
              AND ai.due_date < %s
            ORDER BY ai.due_date, ai.id
            """,
            (session["tenant_id"], session["user_id"], session["user_id"], start_date, end_date),
        )
        events.extend(admin_json_rows(cursor.fetchall()))
    events.sort(key=lambda item: (str(item.get("starts_at") or ""), item.get("source_type") or "", item.get("id") or 0))
    record_audit_event(session, "list", "calendar", None, None, {"count": len(events), "year": year, "month": month}, request)
    return {"success": True, "year": year, "month": month, "events": events}


@app.get("/api/quotes")
async def list_quotes(
    request: Request,
    company_name: str = "",
    contact_name: str = "",
    limit: int = Query(default=100, ge=1, le=500),
):
    session = require_session(request)
    company_keyword = f"%{company_name.strip()}%"
    contact_keyword = f"%{contact_name.strip()}%"
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                q.id, q.quote_no, q.title, q.status, q.currency, q.total_amount,
                q.valid_until, q.sent_at, q.accepted_at, q.rejected_at, q.created_at, q.updated_at,
                a.name AS company_name,
                c.name AS contact_name,
                o.name AS opportunity_name,
                ud.id AS document_id,
                ud.original_filename AS document_filename,
                CONCAT('/api/documents/', ud.id, '/download') AS document_url
            FROM quotes q
            LEFT JOIN accounts a
                   ON a.id = q.account_id
                  AND a.tenant_id = q.tenant_id
                  AND a.deleted_at IS NULL
            LEFT JOIN contacts c
                   ON c.id = q.contact_id
                  AND c.tenant_id = q.tenant_id
                  AND c.deleted_at IS NULL
            LEFT JOIN opportunities o
                   ON o.id = q.opportunity_id
                  AND o.tenant_id = q.tenant_id
                  AND o.deleted_at IS NULL
            LEFT JOIN uploaded_documents ud
                   ON ud.id = (
                       SELECT MAX(ud2.id)
                       FROM uploaded_documents ud2
                       WHERE ud2.tenant_id = q.tenant_id
                         AND ud2.owner_user_id = q.owner_user_id
                         AND ud2.entity_type = 'quote'
                         AND ud2.entity_id = q.id
                         AND ud2.deleted_at IS NULL
                   )
            WHERE q.tenant_id = %s
              AND q.owner_user_id = %s
              AND q.deleted_at IS NULL
              AND (%s = '' OR a.name LIKE %s)
              AND (%s = '' OR c.name LIKE %s)
            ORDER BY q.updated_at DESC, q.id DESC
            LIMIT %s
            """,
            (
                session["tenant_id"],
                session["user_id"],
                company_name.strip(),
                company_keyword,
                contact_name.strip(),
                contact_keyword,
                limit,
            ),
        )
        quotes = admin_json_rows(cursor.fetchall())
    record_audit_event(
        session,
        "list",
        "quote",
        None,
        None,
        {"count": len(quotes), "company_name": company_name.strip(), "contact_name": contact_name.strip()},
        request,
    )
    return {"success": True, "quotes": quotes}


@app.get("/api/contracts")
async def list_contracts(
    request: Request,
    company_name: str = "",
    contact_name: str = "",
    limit: int = Query(default=100, ge=1, le=500),
):
    session = require_session(request)
    company_keyword = f"%{company_name.strip()}%"
    contact_keyword = f"%{contact_name.strip()}%"
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                ct.id, ct.contract_no, ct.title, ct.status, ct.currency, ct.contract_amount,
                ct.start_date, ct.end_date, ct.signed_at, ct.activated_at, ct.terminated_at, ct.created_at, ct.updated_at,
                a.name AS company_name,
                c.name AS contact_name,
                q.quote_no,
                o.name AS opportunity_name,
                ud.id AS document_id,
                ud.original_filename AS document_filename,
                CONCAT('/api/documents/', ud.id, '/download') AS document_url
            FROM contracts ct
            LEFT JOIN accounts a
                   ON a.id = ct.account_id
                  AND a.tenant_id = ct.tenant_id
                  AND a.deleted_at IS NULL
            LEFT JOIN contacts c
                   ON c.id = ct.contact_id
                  AND c.tenant_id = ct.tenant_id
                  AND c.deleted_at IS NULL
            LEFT JOIN quotes q
                   ON q.id = ct.quote_id
                  AND q.tenant_id = ct.tenant_id
                  AND q.deleted_at IS NULL
            LEFT JOIN opportunities o
                   ON o.id = ct.opportunity_id
                  AND o.tenant_id = ct.tenant_id
                  AND o.deleted_at IS NULL
            LEFT JOIN uploaded_documents ud
                   ON ud.id = (
                       SELECT MAX(ud2.id)
                       FROM uploaded_documents ud2
                       WHERE ud2.tenant_id = ct.tenant_id
                         AND ud2.owner_user_id = ct.owner_user_id
                         AND ud2.entity_type = 'contract'
                         AND ud2.entity_id = ct.id
                         AND ud2.deleted_at IS NULL
                   )
            WHERE ct.tenant_id = %s
              AND ct.owner_user_id = %s
              AND ct.deleted_at IS NULL
              AND (%s = '' OR a.name LIKE %s)
              AND (%s = '' OR c.name LIKE %s)
            ORDER BY ct.updated_at DESC, ct.id DESC
            LIMIT %s
            """,
            (
                session["tenant_id"],
                session["user_id"],
                company_name.strip(),
                company_keyword,
                contact_name.strip(),
                contact_keyword,
                limit,
            ),
        )
        contracts = admin_json_rows(cursor.fetchall())
    record_audit_event(
        session,
        "list",
        "contract",
        None,
        None,
        {"count": len(contracts), "company_name": company_name.strip(), "contact_name": contact_name.strip()},
        request,
    )
    return {"success": True, "contracts": contracts}


@app.get("/api/customers/{customer_id}")
async def get_customer(customer_id: int, request: Request):
    session = require_session(request)
    current_tenant_id = session["tenant_id"]
    current_user_id = session["user_id"]
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        row = fetch_contact(cursor, customer_id, current_tenant_id, current_user_id)
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        customer = contact_row_to_customer(row)
    record_audit_event(session, "view", "customer", customer_id, None, {"customer_id": customer_id}, request)
    return {"success": True, "customer": customer}


@app.post("/api/customers")
async def create_customer(payload: CustomerPayload, request: Request):
    session = require_session(request)
    payload.tenant_id = session["tenant_id"]
    payload.owner_user_id = session["user_id"]
    customer = insert_customer(payload, session, request)
    record_audit_event(session, "create", "customer", customer.get("id"), None, customer, request)
    return {"success": True, "customer": customer}


@app.put("/api/customers/{customer_id}")
async def update_customer(customer_id: int, payload: CustomerPayload, request: Request):
    session = require_session(request)
    payload.tenant_id = session["tenant_id"]
    payload.owner_user_id = session["user_id"]
    customer = update_customer_record(customer_id, payload, session, request)
    record_audit_event(session, "update", "customer", customer_id, None, customer, request)
    return {"success": True, "customer": customer}


@app.delete("/api/customers/{customer_id}")
async def delete_customer(customer_id: int, request: Request):
    session = require_session(request)
    current_tenant_id = session["tenant_id"]
    current_user_id = session["user_id"]
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        before = fetch_contact_audit_row(cursor, customer_id, current_tenant_id, current_user_id)
        cursor.execute(
            """
            UPDATE contacts
            SET deleted_at = NOW(6)
            WHERE id = %s
              AND tenant_id = %s
              AND owner_user_id = %s
              AND deleted_at IS NULL
            """,
            (customer_id, current_tenant_id, current_user_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Customer not found")
        write_audit_log(cursor, session, "delete", "contacts", customer_id, before, None, request)
    record_audit_event(session, "delete", "customer", customer_id, None, {"customer_id": customer_id}, request)
    return {"success": True}


@app.get("/api/agent/command-cases")
async def get_agent_command_cases(request: Request):
    session = require_session(request)
    command_cases = command_cases_for_docs()
    record_audit_event(
        session,
        "list",
        "agent_command_cases",
        None,
        None,
        {"count": len(command_cases)},
        request,
    )
    return {"success": True, "command_cases": command_cases}


@app.post("/api/chat")
async def chat(chat_request: ChatRequest, request: Request):
    session = require_session(request)
    message = chat_request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    effective_context = chat_request.context if isinstance(chat_request.context, dict) else {}
    command_route = route_agent_command(message)
    resolved_customer = None
    customer_candidates: list[dict[str, Any]] = []
    if command_route.requires_customer_preflight:
        try:
            with db_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                effective_context, customer_candidates, resolved_customer = resolve_command_customer_preflight(
                    cursor,
                    session,
                    message,
                    effective_context,
                )
        except HTTPException:
            raise
        except mysql.connector.Error as error:
            return database_error_response(error, request)
        except Exception as error:
            print("Customer command preflight failed:", error)
            return internal_error_response("고객 정보를 먼저 확인하는 중 오류가 발생했습니다.", request=request)

    selected_customer = effective_context.get("selectedCustomer") if isinstance(effective_context, dict) else None
    selected_customer_id = (
        selected_customer.get("id") or selected_customer.get("contactId")
        if isinstance(selected_customer, dict)
        else None
    )
    record_audit_event(
        session,
        "ask",
        "agent",
        selected_customer_id,
        None,
        {
            "message_preview": message[:300],
            "selected_customer_id": selected_customer_id,
            "command_case_id": command_route.case_id,
            "command_handler": command_route.handler_name,
        },
        request,
    )
    record_audit_event(
        session,
        "route",
        "agent_command",
        selected_customer_id,
        None,
        {
            "message_preview": message[:300],
            "case_id": command_route.case_id,
            "title": command_route.title,
            "handler_name": command_route.handler_name,
            "matched": command_route.matched,
            "requires_customer_preflight": command_route.requires_customer_preflight,
        },
        request,
    )

    if customer_candidates:
        record_audit_event(
            session,
            "list",
            "customer_command_candidates",
            None,
            None,
            {"message_preview": message[:300], "candidate_count": len(customer_candidates)},
            request,
        )
        return {
            "success": True,
            "reply": "명령을 처리하기 전에 고객을 먼저 확인해 주세요. 아래 후보 중 이번 작업 대상 고객을 선택하면 같은 명령을 이어서 처리하겠습니다.",
            "customer_selection_required": True,
            "pending_message": message,
            "candidates": admin_json_rows(customer_candidates),
        }

    social_links = extract_social_links(message)
    if command_route.case_id == "sns_profile_research":
        if len(social_links) > MAX_SNS_LINKS_PER_REQUEST:
            raise HTTPException(status_code=400, detail=f"SNS 링크는 한 번에 최대 {MAX_SNS_LINKS_PER_REQUEST}개까지 확인할 수 있습니다.")
        try:
            items = [inspect_social_link(link) for link in social_links]
            record_audit_event(
                session,
                "inspect",
                "sns",
                selected_customer_id,
                None,
                {
                    "link_count": len(items),
                    "source": "chat",
                    "resolved_customer_id": resolved_customer.get("contact_id") if resolved_customer else None,
                },
                request,
            )
            return {
                "success": True,
                "reply": build_sns_inspect_reply(items),
                "sns_inspected": True,
                "count": len(items),
                "items": items,
                "resolved_customer": admin_json_row(contact_row_to_customer(resolved_customer)) if resolved_customer else None,
            }
        except HTTPException:
            raise
        except mysql.connector.Error as error:
            return database_error_response(error, request)
        except Exception as error:
            print("SNS chat inspection failed:", error)
            return internal_error_response("SNS 링크 정보를 확인하는 중 오류가 발생했습니다.", request=request)

    if command_route.case_id == "sales_activity_schedule":
        try:
            activity_result = manage_sales_activity_from_message(session, message, effective_context, request)
            return {
                "success": True,
                "reply": activity_result["reply"],
                "activity_schedule": True,
                "activity_saved": activity_result.get("saved", False),
                "schedule_action": activity_result.get("action"),
                "activity": activity_result.get("activity"),
                "activities": activity_result.get("activities"),
                "customer": activity_result.get("customer"),
                "calendar": activity_result.get("calendar"),
            }
        except HTTPException:
            raise
        except mysql.connector.Error as error:
            return database_error_response(error, request)
        except Exception as error:
            print("Sales activity schedule failed:", error)
            return internal_error_response("영업활동 일정을 저장하는 중 오류가 발생했습니다.", request=request)

    try:
        model = create_gemini_model(temperature=0.3)
        context_text = build_chat_context(effective_context)
        tool = TavilySearchResults(max_results=6)
        agent = create_react_agent(
            model,
            [tool],
            prompt=SystemMessage(
                content=(
                    "You are FingerSalesAI, a Korean B2B sales research assistant. "
                    "Answer in Korean. Use the provided session context as the user's current working context, "
                    "but do not rely only on that context when the user asks about facts, companies, markets, people, "
                    "news, competitors, strategies, or any information that could benefit from research. "
                    "Actively use the Tavily search tool to gather as much relevant current information as needed. "
                    "If selected_customer_highest_priority is present in the session context, treat it as the user's "
                    "currently selected customer and prioritize it over the latest extracted or listed customer. "
                    "When the same field appears multiple times in the session context, prefer the selected customer first, then the most recent "
                    "business-card extraction or the most recent chat turn. "
                    "Synthesize search results with the latest session context into a practical sales answer. "
                    "Do not use markdown bold markers such as ** anywhere in the answer. "
                    "When writing bullet lists, use the round bullet character '•' instead of markdown '*' bullets. "
                    "If you used search results, add one blank line before a short '참고 출처' section. "
                    "In that section, show sources as markdown links with readable Korean or site-name labels, "
                    "for example [한화 공식 사이트](https://example.com). Do not print bare URL text. "
                    "Do not invent facts that were not in context or search results."
                )
            ),
        )
        response = agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            f"Session context:\n{context_text}\n\n"
                            f"User question or instruction:\n{message}\n\n"
                            "최신 컨텍스트를 우선하되, 질문에 답하기 위해 필요한 정보는 검색으로 충분히 리서치한 뒤 답변하세요."
                        )
                    )
                ]
            }
        )
        reply = content_to_text(response["messages"][-1].content).strip()
        return {
            "success": True,
            "reply": reply,
            "resolved_customer": admin_json_row(contact_row_to_customer(resolved_customer)) if resolved_customer else None,
        }
    except HTTPException:
        raise
    except mysql.connector.Error as error:
        return database_error_response(error, request)
    except Exception as error:
        print("Chat failed:", error)
        return internal_error_response("답변 생성 중 오류가 발생했습니다.", request=request)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session = get_session(request)
    if not session:
        return RedirectResponse("/login.html", status_code=303)
    html = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    script_version = int((BASE_DIR / "script.js").stat().st_mtime)
    session_script = (
        "<script>"
        f"window.__FSAI_SESSION__ = {json.dumps({**session, 'role_label': role_label(session['role'])}, ensure_ascii=False)};"
        "</script>"
    )
    return html.replace(
        '<script src="/script.js"></script>',
        f"{session_script}\n    <script src=\"/script.js?v={script_version}\"></script>",
    )


@app.get("/admin", response_class=HTMLResponse)
@app.get("/settings/{section}", response_class=HTMLResponse)
async def admin_page(request: Request, section: str = ""):
    session = get_session(request)
    if not session:
        return RedirectResponse("/login.html", status_code=303)
    if session.get("role") not in ADMIN_ROLES:
        return RedirectResponse("/", status_code=303)
    html = (BASE_DIR / "admin.html").read_text(encoding="utf-8")
    admin_script_version = int((BASE_DIR / "admin.js").stat().st_mtime)
    session_script = (
        "<script>"
        f"window.__FSAI_SESSION__ = {json.dumps({**session, 'role_label': role_label(session['role'])}, ensure_ascii=False)};"
        "</script>"
    )
    return html.replace(
        '<script src="/admin.js"></script>',
        f"{session_script}\n    <script src=\"/admin.js?v={admin_script_version}\"></script>",
    )


@app.get("/login.html", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_session(request):
        return RedirectResponse("/", status_code=303)
    return (BASE_DIR / "login.html").read_text(encoding="utf-8")


@app.get("/{asset_name}")
async def asset(asset_name: str):
    allowed_assets = {
        "styles.css",
        "script.js",
        "admin.js",
        "login.html",
        "admin.html",
        "fingersales_logo.png",
        "fingerai_logo.png",
    }
    if asset_name not in allowed_assets:
        raise HTTPException(status_code=404, detail="Not found")

    path = BASE_DIR / asset_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    response = FileResponse(path)
    if asset_name in {"script.js", "admin.js", "styles.css"}:
        response.headers["Cache-Control"] = "no-cache"
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
