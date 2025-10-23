"""
Web Crawler Tool - BeautifulSoup 기반 웹 크롤링

Tavily API rate limit을 피하기 위한 대체 검색 도구
"""

from __future__ import annotations

import re
import time
from typing import Dict, List, Optional
from urllib.parse import quote_plus

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None  # type: ignore[assignment]
    BeautifulSoup = None  # type: ignore[assignment]


class WebCrawler:
    """BeautifulSoup 기반 웹 크롤러"""

    def __init__(self, delay: float = 1.0):
        """
        Args:
            delay: 요청 간 지연 시간 (초)
        """
        self.delay = delay
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def naver_news_crawl(self, news_url: str) -> Optional[str]:
        """네이버 뉴스 크롤링"""
        if not requests or not BeautifulSoup:
            print("⚠️ requests 또는 BeautifulSoup이 설치되지 않았습니다.")
            return None

        try:
            response = requests.get(news_url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                # 제목 추출
                title_elem = soup.find("h2", id="title_area")
                if not title_elem:
                    title_elem = soup.find("h3", class_="tts_head")
                title = title_elem.get_text() if title_elem else ""

                # 본문 추출
                content_elem = soup.find("div", id="contents")
                if not content_elem:
                    content_elem = soup.find("div", id="articleBodyContents")
                if not content_elem:
                    content_elem = soup.find("div", class_="article_body")
                content = content_elem.get_text() if content_elem else ""

                # 정리
                cleaned_title = re.sub(r"\n{2,}", "\n", title.strip())
                cleaned_content = re.sub(r"\n{2,}", "\n", content.strip())

                return f"{cleaned_title}\n{cleaned_content}"
            else:
                print(f"⚠️ HTTP 요청 실패. 응답 코드: {response.status_code}")
                return None

        except Exception as e:
            print(f"⚠️ 네이버 뉴스 크롤링 실패: {e}")
            return None

    def naver_search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """네이버 검색 결과 크롤링"""
        if not requests or not BeautifulSoup:
            print("⚠️ requests 또는 BeautifulSoup이 설치되지 않았습니다.")
            return []

        try:
            # 네이버 통합검색
            encoded_query = quote_plus(query)
            search_url = f"https://search.naver.com/search.naver?query={encoded_query}"

            response = requests.get(search_url, headers=self.headers, timeout=10)

            if response.status_code != 200:
                print(f"⚠️ 검색 실패: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            # 1. 뉴스 결과 추출
            news_items = soup.select(".news_area, .news_wrap")
            for item in news_items[:max_results]:
                title_elem = item.select_one(".news_tit, a.news_tit")
                desc_elem = item.select_one(".news_dsc, .dsc_txt_wrap")

                if title_elem:
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get("href", "")
                    description = desc_elem.get_text(strip=True) if desc_elem else title

                    results.append(
                        {
                            "title": title,
                            "url": url,
                            "content": description,
                            "snippet": description,
                        }
                    )

            # 2. 블로그/카페 결과 추가
            if len(results) < max_results:
                blog_items = soup.select(".total_wrap, .api_subject_bx")
                for item in blog_items[: max_results - len(results)]:
                    title_elem = item.select_one(".total_tit, .api_txt_lines")
                    desc_elem = item.select_one(".total_txt, .api_txt_lines")

                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        url_elem = item.select_one("a")
                        url = url_elem.get("href", "") if url_elem else ""
                        description = (
                            desc_elem.get_text(strip=True) if desc_elem else title
                        )

                        results.append(
                            {
                                "title": title,
                                "url": url,
                                "content": description,
                                "snippet": description,
                            }
                        )

            # 3. 통합검색 결과 추가 (일반 웹 결과)
            if len(results) < max_results:
                web_items = soup.select(".total_area, .bx")
                for item in web_items[: max_results - len(results)]:
                    title_elem = item.select_one(".link_tit, .tit")
                    desc_elem = item.select_one(".total_dsc, .dsc")

                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get("href", "")
                        description = (
                            desc_elem.get_text(strip=True) if desc_elem else title
                        )

                        results.append(
                            {
                                "title": title,
                                "url": url,
                                "content": description,
                                "snippet": description,
                            }
                        )

            time.sleep(self.delay)  # Rate limiting
            return results[:max_results]

        except Exception as e:
            print(f"⚠️ 네이버 검색 실패: {e}")
            return []

    def google_search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """구글 검색 결과 크롤링 (간단한 버전)"""
        if not requests or not BeautifulSoup:
            print("⚠️ requests 또는 BeautifulSoup이 설치되지 않았습니다.")
            return []

        try:
            encoded_query = quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}&hl=ko"

            response = requests.get(search_url, headers=self.headers, timeout=10)

            if response.status_code != 200:
                print(f"⚠️ 구글 검색 실패: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            # 검색 결과 추출
            search_items = soup.select(".g")[:max_results]
            for item in search_items:
                title_elem = item.select_one("h3")
                link_elem = item.select_one("a")
                snippet_elem = item.select_one(".VwiC3b")

                if title_elem and link_elem:
                    title = title_elem.get_text(strip=True)
                    url = link_elem.get("href", "")
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                    results.append(
                        {
                            "title": title,
                            "url": url,
                            "content": snippet,
                            "snippet": snippet,
                        }
                    )

            time.sleep(self.delay)  # Rate limiting
            return results[:max_results]

        except Exception as e:
            print(f"⚠️ 구글 검색 실패: {e}")
            return []

    def hybrid_search(
        self,
        query: str,
        max_results: int = 5,
        use_naver: bool = True,
        use_google: bool = False,
    ) -> List[Dict[str, str]]:
        """하이브리드 검색 (네이버 + 구글)"""
        results = []

        if use_naver:
            naver_results = self.naver_search(query, max_results // 2 + 1)
            results.extend(naver_results)

        if use_google and len(results) < max_results:
            remaining = max_results - len(results)
            google_results = self.google_search(query, remaining)
            results.extend(google_results)

        return results[:max_results]


def search_with_crawler(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """크롤러를 사용한 검색 (외부에서 사용)"""
    crawler = WebCrawler(delay=1.0)
    return crawler.hybrid_search(query, max_results, use_naver=True, use_google=False)


# 데모
if __name__ == "__main__":
    crawler = WebCrawler()

    print("=" * 80)
    print("🔍 네이버 검색 테스트")
    print("=" * 80)

    results = crawler.naver_search("우주산업 스타트업", max_results=3)
    for idx, result in enumerate(results, 1):
        print(f"\n[{idx}] {result['title']}")
        print(f"    URL: {result['url']}")
        print(f"    내용: {result['content'][:100]}...")

    print("\n" + "=" * 80)
