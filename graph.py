import base64
import json
import os
from pathlib import Path
from typing import TypedDict

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(Path("C:/Work/Code/NameCard/.env"))

if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


def create_gemini_model(model: str = "gemini-2.5-flash", temperature: float = 0):
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    return ChatGoogleGenerativeAI(model=model, temperature=temperature, api_key=api_key)


def content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "\n".join(part for part in parts if part)
    return str(content or "")


class BusinessCardInfo(BaseModel):
    is_business_card: bool = Field(description="True if the image is a business card or name card.")
    company_name: str = Field(default="", description="Company name. Empty string if missing.")
    name: str = Field(default="", description="Person name. Empty string if missing.")
    job_title: str = Field(default="", description="Job role or department. Empty string if missing.")
    job_position: str = Field(default="", description="Rank or position. Empty string if missing.")
    mobile_phone: str = Field(default="", description="Mobile phone number. Empty string if missing.")
    email: str = Field(default="", description="Email address. Empty string if missing.")
    homepage: str = Field(default="", description="Company website URL. Empty string if missing.")
    other_info: dict[str, str] = Field(default_factory=dict, description="Extra fields with Korean labels.")


class State(TypedDict):
    image_bytes: bytes
    card_info: dict
    missing_fields: list[str]
    company_briefing: str
    is_business_card: bool
    skip_briefing: bool


def extract_info(state: State):
    model = create_gemini_model()
    structured_model = model.with_structured_output(BusinessCardInfo)
    image_b64 = base64.b64encode(state["image_bytes"]).decode("utf-8")

    prompt = """
    You extract information from uploaded images for a sales assistant.
    First decide whether the image is a business card/name card.
    If it is a business card, extract the visible fields accurately.
    Put extra information such as address, office phone, fax, or company registration
    number into other_info with Korean labels.
    Return empty strings for missing values. Do not guess.
    """

    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ]
    )
    response: BusinessCardInfo = structured_model.invoke([message])
    data = response.model_dump()

    if not data.get("is_business_card"):
        return {"is_business_card": False, "card_info": {}, "missing_fields": []}

    card_info = {
        "회사명": data.get("company_name", "").strip(),
        "이름": data.get("name", "").strip(),
        "직무": data.get("job_title", "").strip(),
        "직위": data.get("job_position", "").strip(),
        "휴대전화": data.get("mobile_phone", "").strip(),
        "이메일": data.get("email", "").strip(),
        "홈페이지": data.get("homepage", "").strip(),
    }
    card_info.update({key: value for key, value in data.get("other_info", {}).items() if value})

    missing = []
    if card_info.get("회사명") and not card_info.get("홈페이지"):
        missing.append("홈페이지")
    if card_info.get("회사명") and card_info.get("이름") and not card_info.get("이메일"):
        missing.append("이메일")

    return {"is_business_card": True, "card_info": card_info, "missing_fields": missing}


def should_search(state: State):
    if not state.get("is_business_card"):
        return END
    if state.get("missing_fields"):
        return "search_web"
    if state.get("skip_briefing"):
        return END
    return "research_company"


def search_web(state: State):
    company = state["card_info"].get("회사명", "")
    name = state["card_info"].get("이름", "")
    missing = state.get("missing_fields", [])

    if not missing:
        return {"missing_fields": []}

    try:
        tool = TavilySearchResults(max_results=3)
        model = create_gemini_model()
        agent = create_react_agent(
            model,
            [tool],
            prompt=SystemMessage(
                content=(
                    "You are a careful contact researcher. Return only a valid JSON object "
                    "containing the requested Korean keys you can verify."
                )
            ),
        )
        prompt = (
            f"Find these missing fields: {', '.join(missing)} for company '{company}'"
            f" and person '{name}'. Return only JSON, for example {{\"홈페이지\":\"https://example.com\"}}."
        )
        response = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        last_message = content_to_text(response["messages"][-1].content).strip()
        if last_message.startswith("```json"):
            last_message = last_message[7:]
        if last_message.endswith("```"):
            last_message = last_message[:-3]

        found_data = json.loads(last_message.strip())
        card_info = state["card_info"].copy()
        for key, value in found_data.items():
            if key in missing and value:
                card_info[key] = f"{value} (웹 검색으로 보완)"

        return {"card_info": card_info, "missing_fields": []}
    except Exception as error:
        print("Contact research failed:", error)
        return {"missing_fields": []}


def research_company(state: State):
    company = state["card_info"].get("회사명", "")
    if not company:
        return {"company_briefing": "회사명이 추출되지 않아 회사 브리핑을 생성하지 못했습니다."}

    try:
        tool = TavilySearchResults(max_results=4)
        model = create_gemini_model()
        agent = create_react_agent(
            model,
            [tool],
            prompt=SystemMessage(
                content="You are a professional B2B sales analyst. Write concise Korean executive briefings."
            ),
        )
        prompt = f"""
        Research the company '{company}'. Find its official overview, business model,
        key products or services, and recent public signals.
        Write a Korean sales briefing in 2-3 compact paragraphs.
        Do not include a markdown heading.
        """
        response = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        return {"company_briefing": content_to_text(response["messages"][-1].content).strip()}
    except Exception as error:
        print("Company research failed:", error)
        return {"company_briefing": "회사 브리핑을 생성하는 중 오류가 발생했습니다."}


workflow = StateGraph(State)
workflow.add_node("extract_info", extract_info)
workflow.add_node("search_web", search_web)
workflow.add_node("research_company", research_company)
workflow.set_entry_point("extract_info")
workflow.add_conditional_edges("extract_info", should_search)
workflow.add_conditional_edges("search_web", lambda state: END if state.get("skip_briefing") else "research_company")
workflow.add_edge("research_company", END)

app_graph = workflow.compile()
