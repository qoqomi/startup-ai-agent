# agents/survival_analyzer.py
from graph.state import AgentState
from tools.news_search import search_keyword


def run(state: AgentState) -> AgentState:
    """생존성 분석"""
    candidates = state["candidates"]

    survival_data = []

    for company in candidates:
        # 투자 유치 뉴스
        funding_news = search_keyword(f"{company['name']} 투자 유치")

        # 재무 관련 뉴스
        financial_news = search_keyword(f"{company['name']} 매출 적자")

        survival_data.append(
            {
                "company": company["name"],
                "recent_funding": len(funding_news) > 0,
                "financial_issues": has_negative_news(financial_news),
                "runway_estimate": estimate_runway(funding_news),
            }
        )

    # 병렬 실행 시 충돌 방지: 필요한 필드만 반환
    return {"survival_analysis": {"data": survival_data}}


def has_negative_news(news_results):
    """부정적 뉴스 감지"""
    negative_keywords = ["적자", "손실", "부도", "폐업", "위기", "경영난"]

    for news in news_results:
        content = news.get("content", "").lower()
        if any(keyword in content for keyword in negative_keywords):
            return True
    return False


def estimate_runway(funding_news):
    """런웨이 추정 (개월)"""
    if len(funding_news) > 0:
        # 최근 투자 유치가 있으면 18개월 추정
        return 18
    else:
        # 없으면 보수적으로 12개월
        return 12
