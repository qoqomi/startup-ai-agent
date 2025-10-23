"""
Agent: 경쟁사 분석 (Competitor Analyzer)

1차 분석 결과를 바탕으로 경쟁사를 찾고 비교 분석합니다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# .env 로드
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")

try:
    from tavily import TavilyClient
except ImportError:  # pragma: no cover
    TavilyClient = None  # type: ignore[assignment]


@dataclass
class CompetitorAnalyzerConfig:
    """경쟁사 분석 설정"""

    max_competitors: int = 2  # Rate limit 방지
    max_search_results: int = 5  # Rate limit 방지


class CompetitorProfile(BaseModel):
    """경쟁사 프로필"""

    name: str = Field(description="회사명")
    country: str = Field(description="국가")
    description: str = Field(description="사업 설명")
    strengths: List[str] = Field(description="강점")
    weaknesses: List[str] = Field(description="약점")


class CompetitorList(BaseModel):
    """경쟁사 리스트"""

    competitors: List[CompetitorProfile] = Field(description="경쟁사 목록")


class CompetitorAnalyzer:
    """경쟁사 분석 에이전트"""

    def __init__(
        self,
        config: Optional[CompetitorAnalyzerConfig] = None,
        tavily_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        self.config = config or CompetitorAnalyzerConfig()
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        # Tavily 비활성화 (API 한도 초과)
        self.tavily_client = None

        # 크롤러 초기화
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

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """경쟁사 분석 실행"""
        company = state.get("profile", {}).get("name")
        if not company:
            candidates = state.get("candidates", [])
            if candidates:
                company = candidates[0].get("name")

        if not company:
            raise ValueError("기업명이 필요합니다")

        print(f"\n{'='*80}")
        print(f"🔍 [경쟁사 분석] {company}")
        print(f"{'='*80}")

        # 1차 분석 결과 가져오기
        tech_analysis = state.get("tech_analysis", {})
        market_analysis = state.get("market_analysis", {})

        # 검색 쿼리 생성
        search_query = self._build_search_query(company, tech_analysis, market_analysis)

        # 경쟁사 검색
        competitors = self._search_competitors(search_query)

        if not competitors:
            print("⚠️ 경쟁사를 찾을 수 없습니다.")
            competitors = []

        # 비교 분석
        comparison = self._compare_with_competitors(company, competitors, state)

        # 결과 출력
        print(f"\n✅ 경쟁사 분석 완료")
        print(f"   경쟁사: {len(competitors)}개")
        for idx, comp in enumerate(competitors, 1):
            print(f"   [{idx}] {comp.get('name')} ({comp.get('country')})")

        # State 업데이트
        result = {
            "competitors": competitors,
            "comparison": comparison,
        }

        return result

    def _build_search_query(
        self,
        company: str,
        tech_analysis: Dict[str, Any],
        market_analysis: Dict[str, Any],
    ) -> str:
        """1차 분석을 바탕으로 경쟁사 검색 쿼리 생성"""
        query_parts = []

        # 핵심 기술 키워드
        core_tech = tech_analysis.get("core_technology", [])
        if core_tech:
            query_parts.extend(core_tech[:2])

        # 산업 키워드
        query_parts.append("우주산업")
        query_parts.append("위성")

        # 경쟁사 검색
        query_parts.append("경쟁사")
        query_parts.append("스타트업")

        query = " ".join(query_parts)
        print(f"📡 검색 쿼리: {query}")
        return query

    def _search_competitors(self, query: str) -> List[Dict[str, Any]]:
        """경쟁사 검색 (크롤러 사용)"""
        if not self.crawler or not self.llm:
            print("⚠️ 크롤러 또는 LLM 없음")
            return []

        try:
            # 크롤러로 검색
            search_results = self.crawler.naver_search(
                query, max_results=self.config.max_search_results
            )

            if not search_results:
                print("⚠️ 검색 결과 없음")
                return []

            # 검색 결과를 텍스트로 변환
            corpus = "\n\n".join(
                [
                    f"{r.get('title', '')}\n{r.get('content', '')}"
                    for r in search_results
                ]
            )

        except Exception as e:
            print(f"⚠️ 크롤러 실패: {e}")
            return []

        # LLM으로 경쟁사 추출
        try:
            competitors = self._extract_competitors_with_llm(corpus)
            return competitors[: self.config.max_competitors]

        except Exception as e:
            print(f"❌ 경쟁사 추출 실패: {e}")
            return []

    def _extract_competitors_with_llm(self, corpus: str) -> List[Dict[str, Any]]:
        """LLM으로 경쟁사 추출"""
        if not self.llm:
            return []

        system_prompt = """당신은 우주산업 경쟁 분석 전문가입니다.

다음 검색 결과에서 한국 또는 해외의 우주산업 스타트업을 찾아 최대 3개를 선정하세요.

## 선정 기준:
- 우주산업 (위성, 로켓, 우주 데이터 등) 관련
- 스타트업 또는 중소기업
- 실제 사업 운영 중

## 출력 형식:
{
  "competitors": [
    {
      "name": "회사명",
      "country": "국가",
      "description": "사업 설명 (50자 이내)",
      "strengths": ["강점1", "강점2"],
      "weaknesses": ["약점1", "약점2"]
    }
  ]
}"""

        user_prompt = f"""다음 텍스트에서 경쟁사를 찾아주세요:

{corpus[:3000]}

경쟁사 3개 이하를 JSON 형식으로 출력하세요."""

        try:
            structured_llm = self.llm.with_structured_output(CompetitorList)
            response = structured_llm.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

            if isinstance(response, CompetitorList):
                return [
                    {
                        "name": c.name,
                        "country": c.country,
                        "description": c.description,
                        "strengths": c.strengths,
                        "weaknesses": c.weaknesses,
                    }
                    for c in response.competitors
                ]

        except Exception as e:
            print(f"❌ LLM 경쟁사 추출 실패: {e}")

        return []

    def _compare_with_competitors(
        self,
        company: str,
        competitors: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """경쟁사와 비교 분석"""
        if not self.llm or not competitors:
            return {
                "our_strengths": [],
                "our_weaknesses": [],
                "narrative": f"{company}의 경쟁사 정보가 부족합니다.",
            }

        # 우리 회사 정보 요약
        our_summary = self._summarize_our_company(state)

        # 경쟁사 요약
        competitor_summary = "\n\n".join(
            [
                f"[{c['name']}] {c['description']}\n강점: {', '.join(c['strengths'])}\n약점: {', '.join(c['weaknesses'])}"
                for c in competitors
            ]
        )

        prompt = f"""당신은 투자 분석가입니다. {company}와 경쟁사들을 비교 분석하세요.

## 우리 회사 ({company}):
{our_summary}

## 경쟁사:
{competitor_summary}

## 출력 형식:
**우리의 강점**: [3가지]
**우리의 약점**: [3가지]
**경쟁사 대비 우위**: [2-3줄 설명]
**종합 평가**: [2-3줄]"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()

            # 파싱
            our_strengths = self._parse_bullet_points(content, "우리의 강점")
            our_weaknesses = self._parse_bullet_points(content, "우리의 약점")

            return {
                "our_strengths": our_strengths,
                "our_weaknesses": our_weaknesses,
                "competitor_strengths": [
                    s for c in competitors for s in c.get("strengths", [])
                ],
                "competitor_weaknesses": [
                    w for c in competitors for w in c.get("weaknesses", [])
                ],
                "narrative": content,
            }

        except Exception as e:
            print(f"⚠️ 비교 분석 실패: {e}")
            return {
                "our_strengths": [],
                "our_weaknesses": [],
                "narrative": f"{company} 비교 분석 실패",
            }

    def _summarize_our_company(self, state: Dict[str, Any]) -> str:
        """우리 회사 정보 요약"""
        summary_parts = []

        tech = state.get("tech_analysis", {})
        if tech:
            summary_parts.append(
                f"기술: TRL {tech.get('trl_level', 'N/A')}, 특허 {len(tech.get('patents', []))}건"
            )

        market = state.get("market_analysis", {})
        if market:
            tam = market.get("tam_sam_som", {}).get("TAM", "N/A")
            summary_parts.append(f"시장: TAM ${tam}B")

        survival = state.get("survival_analysis", {})
        if survival:
            funding = len(survival.get("funding_history", []))
            summary_parts.append(f"투자: {funding}건")

        return "\n".join(summary_parts) if summary_parts else "정보 부족"

    def _parse_bullet_points(self, text: str, section_name: str) -> List[str]:
        """텍스트에서 불릿 포인트 추출"""
        lines = text.split("\n")
        points = []
        in_section = False

        for line in lines:
            if section_name in line:
                in_section = True
                continue
            if in_section:
                # 다음 섹션 시작하면 종료
                if line.startswith("**"):
                    break
                # 불릿 포인트 추출
                if line.strip().startswith(("-", "•", "*", "1.", "2.", "3.")):
                    point = line.strip().lstrip("-•*123. ")
                    if point:
                        points.append(point)

        return points[:3]


def _demo():
    """데모 실행"""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from graph.state import create_initial_state

    state = create_initial_state()
    state["profile"] = {"name": "나라스페이스"}
    state["tech_analysis"] = {
        "trl_level": 9,
        "core_technology": ["AI", "큐브위성", "영상분석"],
    }
    state["market_analysis"] = {"tam_sam_som": {"TAM": 100}}

    analyzer = CompetitorAnalyzer()
    result = analyzer.run(state)

    print("\n" + "=" * 80)
    print("📊 최종 결과")
    print("=" * 80)
    print(f"경쟁사: {len(result.get('competitors', []))}개")
    print(result.get("comparison", {}).get("narrative", ""))


if __name__ == "__main__":
    _demo()
