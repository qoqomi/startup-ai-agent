"""
Agent: 후보 선택 (Candidate Selector)

AI 위성(우주산업) 스타트업을 검색하여 1개 후보를 선택합니다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# .env 로드 (프로젝트 루트 기준)
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")

try:
    from tavily import TavilyClient
except ImportError:  # pragma: no cover
    TavilyClient = None  # type: ignore[assignment]


@dataclass
class CandidateSelectorConfig:
    """후보 선택 에이전트 설정"""

    query: str = "AI 위성(우주산업) 스타트업"
    keywords: List[str] = None
    max_results: int = 10
    max_candidates: int = 1  # 후보 1개만 선택
    country_filter: str = "South Korea"
    search_depth: str = "advanced"
    include_domains: List[str] = None
    days: int = 730  # 최근 2년

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = ["위성 소형화", "저궤도 위성", "광학위성"]
        if self.include_domains is None:
            self.include_domains = [
                "venturesquare.net",
                "platum.kr",
                "startupn.kr",
                "techcrunch.com",
                "news.naver.com",
            ]


class StartupCandidate(BaseModel):
    """검색된 스타트업 후보"""

    name: str = Field(description="회사명 (한글 또는 영문)")
    country: str = Field(description="국가 (예: South Korea)")
    industry: str = Field(description="산업 분야 (예: AI Satellite)")
    description: str = Field(description="사업 설명 (50자 이내)")
    founded_year: Optional[int] = Field(default=None, description="설립연도")
    relevance_score: float = Field(default=0.0, description="관련성 점수 (0.0-1.0)")


class CandidateList(BaseModel):
    """후보 리스트"""

    candidates: List[StartupCandidate] = Field(
        description="선정된 스타트업 후보 리스트"
    )


class CandidateSelector:
    """후보 선택 에이전트"""

    def __init__(
        self,
        config: Optional[CandidateSelectorConfig] = None,
        tavily_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        self.config = config or CandidateSelectorConfig()
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        if not self.openai_api_key:
            print("⚠️ OPENAI_API_KEY 없음")

        # Tavily 비활성화 (API 한도 초과), 크롤러 사용
        self.tavily_client = None
        from tools.web_crawler import WebCrawler

        self.crawler = WebCrawler(delay=1.0)
        self.llm = (
            ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.0,
                api_key=self.openai_api_key,
            )
            if self.openai_api_key
            else None
        )

    def run(self, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """후보 선택 실행"""
        print(f"\n{'='*80}")
        print(f"🔍 [후보 선택] {self.config.query}")
        print(f"{'='*80}")

        # 1. Tavily 검색
        search_results = self._search_candidates()

        if not search_results:
            print("⚠️ 검색 결과 없음 - 기본 회사 사용")
            # 기본 회사 반환
            default_candidate = StartupCandidate(
                name="텔레픽스",
                country="South Korea",
                industry="AI Satellite",
                description="위성 데이터 처리 및 AI 솔루션 개발 스타트업",
                founded_year=2019,
                relevance_score=1.0,
            )
            candidates = [default_candidate]

            result = {
                "candidates": [
                    {
                        "name": default_candidate.name,
                        "country": default_candidate.country,
                        "industry": default_candidate.industry,
                        "description": default_candidate.description,
                        "founded_year": default_candidate.founded_year,
                        "relevance_score": default_candidate.relevance_score,
                    }
                ],
                "meta": {
                    "current_agent": "candidate_selector",
                    "stage": "candidate_selection",
                    "history": ["candidate_selector:completed"],
                },
            }
            print(f"\n✅ 기본 후보: {default_candidate.name}")
            return result

        # 2. LLM으로 후보 선정
        candidates = self._select_candidates(search_results)

        # 2-1. 후보가 없으면 기본 회사 사용
        if not candidates:
            print("⚠️ LLM이 후보를 선정하지 못함 - 기본 회사 사용")
            default_candidate = StartupCandidate(
                name="텔레픽스",
                country="South Korea",
                industry="AI Satellite",
                description="위성 데이터 처리 및 AI 솔루션 개발 스타트업",
                founded_year=2019,
                relevance_score=1.0,
            )
            candidates = [default_candidate]

        # 3. 결과 출력
        print(f"\n✅ 선정된 후보: {len(candidates)}개")
        for idx, candidate in enumerate(candidates, 1):
            print(f"\n[{idx}] {candidate.name}")
            print(f"    국가: {candidate.country}")
            print(f"    분야: {candidate.industry}")
            print(f"    설명: {candidate.description}")
            if candidate.founded_year:
                print(f"    설립: {candidate.founded_year}년")
            print(f"    관련성: {candidate.relevance_score:.2f}")

        # 4. State 업데이트
        result = {
            "candidates": [
                {
                    "name": c.name,
                    "country": c.country,
                    "industry": c.industry,
                    "description": c.description,
                    "founded_year": c.founded_year,
                    "relevance_score": c.relevance_score,
                }
                for c in candidates
            ],
            "meta": {
                "current_agent": "candidate_selector",
                "stage": "candidate_selection",
                "history": ["candidate_selector:completed"],
            },
        }

        return result

    def _search_candidates(self) -> List[Dict[str, Any]]:
        """크롤러로 후보 검색"""
        if not self.crawler:
            print("⚠️ 크롤러 없음")
            return []

        # 검색 쿼리 구성
        query_parts = [self.config.query]
        query_parts.extend(self.config.keywords)
        full_query = " ".join(query_parts)

        print(f"📡 네이버 검색: {full_query}")

        try:
            results = self.crawler.naver_search(
                full_query, max_results=self.config.max_results
            )
            print(f"   결과: {len(results)}건")
            return results

        except Exception as e:
            print(f"❌ 크롤러 검색 실패: {e}")
            return []

    def _select_candidates(
        self, search_results: List[Dict[str, Any]]
    ) -> List[StartupCandidate]:
        """LLM으로 후보 선정"""
        if not self.llm:
            print("⚠️ LLM 없음 - 후보 선정 불가")
            return []

        # 검색 결과를 텍스트로 변환
        corpus_parts = []
        for idx, result in enumerate(search_results, 1):
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")
            corpus_parts.append(f"[{idx}] {title}\n{content}\nURL: {url}\n")

        corpus = "\n".join(corpus_parts)

        # LLM 프롬프트
        system_prompt = """당신은 우주산업 전문 벤처 투자 분석가입니다.

주어진 검색 결과에서 **한국의 AI 위성(우주산업) 스타트업**을 찾아 **1개만** 선정하세요.

## 선정 기준:
1. **국가**: 반드시 "South Korea" (한국)
2. **산업**: AI 위성, 큐브위성, 위성 영상분석 등 우주산업 관련
3. **키워드**: 위성 소형화, 저궤도 위성, 광학위성 중 하나 이상 관련
4. **스타트업**: 대기업 계열사 제외, 독립 스타트업만

## 검증 체크리스트:
✓ 한국 기업인가?
✓ 위성 관련 사업인가?
✓ 스타트업인가? (대기업 X)
✓ AI/데이터 분석 기술 활용하는가?

## 출력 형식:
- name: 회사명 (한글)
- country: "South Korea" (필수)
- industry: "AI Satellite" 또는 구체적 분야
- description: 50자 이내 사업 설명
- founded_year: 설립연도 (알 수 없으면 null)
- relevance_score: 관련성 점수 (0.0-1.0)

## 예시:
{
  "candidates": [
    {
      "name": "나라스페이스",
      "country": "South Korea",
      "industry": "AI Satellite",
      "description": "큐브위성 개발 및 위성 영상분석 플랫폼 제공",
      "founded_year": 2016,
      "relevance_score": 0.95
    }
  ]
}

**중요**: 정확히 1개만 선정하고, 확실하지 않으면 빈 리스트를 반환하세요.
"""

        user_prompt = f"""다음 검색 결과에서 한국의 AI 위성 스타트업 1개를 선정하세요:

{corpus}

위 기준에 맞는 후보 1개를 JSON 형식으로 출력하세요."""

        print(f"\n🤖 LLM 분석 중...")

        try:
            structured_llm = self.llm.with_structured_output(CandidateList)
            response = structured_llm.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

            if isinstance(response, CandidateList):
                candidates = response.candidates
            else:
                print(f"⚠️ 예상치 못한 응답 형식: {type(response)}")
                return []

            # 한국 기업만 필터링
            korean_candidates = [
                c for c in candidates if c.country and "korea" in c.country.lower()
            ]

            # 최대 개수 제한
            return korean_candidates[: self.config.max_candidates]

        except Exception as e:
            print(f"❌ LLM 분석 실패: {e}")
            import traceback

            traceback.print_exc()
            return []


def _demo():
    """데모 실행"""
    selector = CandidateSelector()
    result = selector.run()

    print("\n" + "=" * 80)
    print("📊 최종 결과")
    print("=" * 80)
    print(f"선정된 후보: {len(result.get('candidates', []))}개")
    for candidate in result.get("candidates", []):
        print(f"  - {candidate['name']} ({candidate['country']})")


if __name__ == "__main__":
    _demo()
