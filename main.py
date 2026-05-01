from pathlib import Path
import base64
import hashlib
import hmac
import html as html_lib
import os
import json
import re
import time
from typing import Any
from urllib.parse import unquote, urlparse, urlunparse
from urllib.request import Request as UrlRequest, urlopen

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

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
_auth_attempts: dict[str, list[float]] = {}

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


class SocialProfileScreenshotInfo(BaseModel):
    is_social_profile: bool = Field(description="True only if the image is a social network profile screen.")
    platform: str = Field(default="", description="Visible SNS platform name such as Facebook, LinkedIn, Instagram, X.")
    display_name: str = Field(default="", description="Exact visible main profile person name. Empty if not visible.")
    headline: str = Field(default="", description="Visible role, headline, or short intro. Empty if not visible.")
    company_name: str = Field(default="", description="Visible current company or organization. Empty if not visible.")
    profile_url: str = Field(default="", description="Visible profile URL if shown in the screenshot. Empty if not visible.")
    summary: str = Field(default="", description="Short Korean summary of only visible profile facts.")


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


@app.on_event("startup")
def startup() -> None:
    init_db()


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


def get_session(request: Request) -> dict[str, Any] | None:
    return read_session_token(request.cookies.get(SESSION_COOKIE_NAME))


def require_session(request: Request) -> dict[str, Any]:
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Login required")
    return session


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
    return {
        "url": url,
        "platform": platform,
        "entity_type": entity_type,
        "handle": handle.strip("@"),
        "display_name": display_name,
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


def fetch_social_public_metadata(link: dict[str, Any]) -> dict[str, str]:
    metadata = {"title": "", "og_title": "", "twitter_title": "", "description": "", "og_description": "", "fetch_error": ""}
    try:
        request = UrlRequest(
            link["url"],
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        with urlopen(request, timeout=6) as response:
            raw = response.read(300_000)
            charset = response.headers.get_content_charset() or "utf-8"
        try:
            document = raw.decode(charset, errors="replace")
        except LookupError:
            document = raw.decode("utf-8", errors="replace")
        title_match = re.search(r"<title[^>]*>(.*?)</title>", document, re.IGNORECASE | re.DOTALL)
        metadata.update(
            {
                "title": clean_html_text(title_match.group(1)) if title_match else "",
                "og_title": html_metadata_value(document, "og:title"),
                "twitter_title": html_metadata_value(document, "twitter:title"),
                "description": html_metadata_value(document, "description"),
                "og_description": html_metadata_value(document, "og:description"),
            }
        )
    except Exception as error:
        metadata["fetch_error"] = str(error)
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
    query_parts = [
        f'"{link["url"]}"',
        link["platform"],
        link.get("handle") or "",
        link.get("display_name") or "",
        metadata_name,
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
    authoritative_metadata_name = metadata_name if metadata_name_is_authoritative(link, metadata_name) else ""
    if authoritative_metadata_name:
        if extracted_name_conflicts(authoritative_metadata_name, extracted_name):
            extracted = {
                "contact_name": authoritative_metadata_name,
                "company_name": "",
                "job_title": "",
                "job_position": "",
                "email": "",
                "summary": f"{link['platform']} 공개 프로필 제목에서 확인한 이름입니다.",
                "briefing": (
                    f"{link['platform']} 공개 프로필 메타데이터에서 '{authoritative_metadata_name}' 이름을 확인했습니다. "
                    "검색 결과의 다른 인물 정보와 충돌해 회사, 직책, 연락처는 확정하지 않았습니다."
                ),
            }
        else:
            extracted["contact_name"] = authoritative_metadata_name

    name_verified = bool(authoritative_metadata_name)
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
        "name_source": "public_profile_metadata" if name_verified else "",
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
        "data": {
            "회사명": "",
            "이름": "",
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


def upsert_account(cursor, payload: CustomerPayload, tenant_id: int) -> int | None:
    company_name = payload.company_name.strip()
    if not company_name:
        return None

    cursor.execute(
        """
        SELECT id
        FROM accounts
        WHERE tenant_id = %s
          AND name = %s
          AND deleted_at IS NULL
        ORDER BY id
        LIMIT 1
        """,
        (tenant_id, company_name),
    )
    account = cursor.fetchone()
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
            """,
            (*account_values, account["id"], tenant_id),
        )
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
    return cursor.lastrowid


def insert_customer(payload: CustomerPayload) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(payload.tenant_id)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        account_id = upsert_account(cursor, payload, tenant_id)
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
        row = fetch_contact(cursor, cursor.lastrowid, tenant_id, payload.owner_user_id)
        return contact_row_to_customer(row)


def update_customer_record(customer_id: int, payload: CustomerPayload) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(payload.tenant_id)
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        current = fetch_contact(cursor, customer_id, tenant_id, payload.owner_user_id)
        if not current:
            raise HTTPException(status_code=404, detail="Customer not found")

        account_id = upsert_account(cursor, payload, tenant_id)
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
        row = fetch_contact(cursor, customer_id, tenant_id, payload.owner_user_id)
        return contact_row_to_customer(row)


def save_extracted_customer(
    data: dict[str, Any],
    briefing: str,
    source_file: str,
    tenant_id: int | None = None,
    owner_user_id: int | None = None,
) -> dict[str, Any]:
    normalized = normalize_card_data(data)
    payload = CustomerPayload(
        **normalized,
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        briefing=briefing or "",
        source_file=source_file or "",
    )
    return insert_customer(payload)


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
async def logout(response: Response):
    clear_session_cookie(response)
    return {"success": True}


@app.get("/logout")
async def logout_page():
    response = RedirectResponse("/login.html", status_code=303)
    clear_session_cookie(response)
    return response


@app.post("/api/extract")
async def extract_business_card(
    request: Request,
    file: UploadFile = File(...),
    skip_briefing: bool = Query(default=False),
):
    session = require_session(request)
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 명함 인식 분석을 실행할 수 있습니다.")

    try:
        contents = await file.read()
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

        return {
            "success": True,
            "is_business_card": result.get("is_business_card", False),
            "is_social_profile": False,
            "data": result.get("card_info", {}),
            "briefing": result.get("company_briefing", ""),
            "customer": save_extracted_customer(
                result.get("card_info", {}),
                result.get("company_briefing", ""),
                file.filename or "",
                session["tenant_id"],
                session["user_id"],
            )
            if result.get("is_business_card", False)
            else None,
        }
    except Exception as error:
        print("Business card extraction failed:", error)
        return {"success": False, "error": str(error)}


@app.post("/api/extract/sns")
async def extract_sns_links(payload: SnsLinksRequest, request: Request):
    session = require_session(request)
    links = extract_social_links(payload.message)
    if not links:
        raise HTTPException(status_code=400, detail="지원하는 SNS 링크를 찾지 못했습니다.")

    try:
        items = [save_sns_customer(link, session["tenant_id"], session["user_id"]) for link in links]
        saved_count = sum(1 for item in items if item.get("saved"))
        pending_count = sum(1 for item in items if item.get("needs_confirmation"))
        return {"success": True, "count": saved_count, "pending_count": pending_count, "items": items}
    except Exception as error:
        print("SNS extraction failed:", error)
        return {"success": False, "error": str(error)}


@app.get("/api/db/health")
async def db_health():
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT DATABASE() AS database_name, VERSION() AS version")
        result = cursor.fetchone()
        return {"success": True, "tenant_id": resolve_tenant_id(), **result}


@app.get("/api/customers")
async def list_customers(
    request: Request,
    search: str = "",
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
        ORDER BY c.created_at DESC, c.id DESC
        LIMIT %s
    """
    keyword = f"%{search.strip()}%"
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (current_tenant_id, current_user_id, search.strip(), keyword, keyword, keyword, keyword, limit))
        return {"success": True, "customers": [contact_row_to_customer(row) for row in cursor.fetchall()]}


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
        return {"success": True, "customer": contact_row_to_customer(row)}


@app.post("/api/customers")
async def create_customer(payload: CustomerPayload, request: Request):
    session = require_session(request)
    payload.tenant_id = session["tenant_id"]
    payload.owner_user_id = session["user_id"]
    return {"success": True, "customer": insert_customer(payload)}


@app.put("/api/customers/{customer_id}")
async def update_customer(customer_id: int, payload: CustomerPayload, request: Request):
    session = require_session(request)
    payload.tenant_id = session["tenant_id"]
    payload.owner_user_id = session["user_id"]
    return {"success": True, "customer": update_customer_record(customer_id, payload)}


@app.delete("/api/customers/{customer_id}")
async def delete_customer(customer_id: int, request: Request):
    session = require_session(request)
    current_tenant_id = session["tenant_id"]
    current_user_id = session["user_id"]
    with db_connection() as connection:
        cursor = connection.cursor()
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
        return {"success": True}


@app.post("/api/chat")
async def chat(chat_request: ChatRequest, request: Request):
    session = require_session(request)
    message = chat_request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    social_links = extract_social_links(message)
    if social_links:
        try:
            items = [save_sns_customer(link, session["tenant_id"], session["user_id"]) for link in social_links]
            saved_count = sum(1 for item in items if item.get("saved"))
            pending_count = sum(1 for item in items if item.get("needs_confirmation"))
            return {
                "success": True,
                "reply": build_sns_import_reply(items),
                "sns_imported": True,
                "count": saved_count,
                "pending_count": pending_count,
                "items": items,
            }
        except Exception as error:
            print("SNS chat fallback failed:", error)
            return {"success": False, "error": str(error)}

    try:
        model = create_gemini_model(temperature=0.3)
        context_text = build_chat_context(chat_request.context)
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
        return {"success": True, "reply": reply}
    except Exception as error:
        print("Chat failed:", error)
        return {"success": False, "error": str(error)}


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
        "login.html",
        "fingersales_logo.png",
        "fingerai_logo.png",
    }
    if asset_name not in allowed_assets:
        raise HTTPException(status_code=404, detail="Not found")

    path = BASE_DIR / asset_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    response = FileResponse(path)
    if asset_name in {"script.js", "styles.css"}:
        response.headers["Cache-Control"] = "no-cache"
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
