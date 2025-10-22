# agents/market_analyzer.py
from dotenv import load_dotenv
from graph.state import AgentState
from tools.news_search import search_keyword
from utils.helpers import extract_industry
from langchain_openai import ChatOpenAI

# 환경 변수 로드
load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def run(state: AgentState) -> dict:
    """시장 분석 에이전트"""

    # 1. 산업 추출
    industry = extract_industry(state["query"])
    print(f"분석 산업: {industry}")

    # 2. 산업 뉴스 검색
    industry_news = search_keyword(f"{industry} 시장 전망 2025")

    # 3. LLM으로 요약
    news_summary = summarize_with_llm(industry_news)

    # 4. 각 스타트업 뉴스
    company_insights = []
    for company in state["candidates"]:
        news = search_keyword(f"{company['name']} 투자")
        company_insights.append(
            {
                "name": company["name"],
                "news_count": len(news),
                "headlines": [n["content"] for n in news[:2]],
            }
        )

    # 병렬 실행 시 충돌 방지: 필요한 필드만 반환
    return {
        "market_analysis": {
            "industry": industry,
            "market_summary": news_summary,
            "company_insights": company_insights,
            "news_sources": [n["url"] for n in industry_news],
        },
    }


def summarize_with_llm(news_results):
    """LLM으로 뉴스 요약"""
    texts = "\n".join([n["content"] for n in news_results])

    prompt = f"""다음 뉴스를 분석하여 요약:
{texts}

요약 (3줄):"""

    return llm.invoke(prompt).content
