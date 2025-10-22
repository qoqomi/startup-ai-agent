# tools/news_search.py
from typing import Dict, List

from langchain_teddynote.tools import GoogleNews


def search_keyword(query: str) -> List[Dict[str, str]]:
    """Look up news by keyword."""

    print(f"뉴스 검색: {query}")
    news_tool = GoogleNews()
    return news_tool.search_by_keyword(query, k=5)
