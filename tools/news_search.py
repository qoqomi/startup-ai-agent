# tools/news_search.py - 수정 버전
from langchain_teddynote.tools import GoogleNews


def search_keyword(query: str, *, k: int = 5) -> List[Dict[str, str]]:
    """뉴스 검색 (GoogleNews 사용)"""
    try:
        news_tool = GoogleNews()
        results = news_tool.search_by_keyword(query, k=k)
        print(f"✓ 뉴스 {len(results)}건")
        return results
    except Exception as e:
        print(f"⚠️ 실패: {e}")
        return []
