"""
Agent: 생존성 분석 (Survival Analyzer)

후보 기업의 생존 가능성을 분석합니다.
- 재무 안정성 (현금, Burn Rate, Runway)
- 투자 이력
- 팀 역량
- 리스크 요인
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# .env 로드
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")

try:
    from tavily import TavilyClient
except ImportError:  # pragma: no cover
    TavilyClient = None  # type: ignore[assignment]


@dataclass
class SurvivalAnalyzerConfig:
    """생존성 분석 설정"""

    max_results: int = 3  # Rate limit 방지
    search_queries_template: List[str] = None

    def __post_init__(self):
        if self.search_queries_template is None:
            self.search_queries_template = [
                "{company} 투자 유치",
                "{company} 재무 상태",
                "{company} 팀 구성",
                "{company} 임직원",
                "{company} 리스크 이슈",
            ]


class SurvivalAnalyzer:
    """생존성 분석 에이전트"""

    def __init__(
        self,
        config: Optional[SurvivalAnalyzerConfig] = None,
        tavily_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        self.config = config or SurvivalAnalyzerConfig()
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        self.tavily_client = (
            TavilyClient(api_key=self.tavily_api_key)
            if TavilyClient and self.tavily_api_key
            else None
        )
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
        """생존성 분석 실행"""
        company = state.get("profile", {}).get("name")
        if not company:
            candidates = state.get("candidates", [])
            if candidates:
                company = candidates[0].get("name")

        if not company:
            raise ValueError("기업명이 필요합니다")

        print(f"\n{'='*80}")
        print(f"💊 [생존성 분석] {company}")
        print(f"{'='*80}")

        # 1. 검색 수집
        corpus = self._collect_corpus(company)

        # 2. 재무 정보 추출
        financial = self._extract_financial(corpus)

        # 3. 투자 이력 추출
        funding_history = self._extract_funding_history(corpus)

        # 4. 팀 정보 추출
        team_info = self._extract_team_info(corpus)

        # 5. 리스크 추출
        risks = self._extract_risks(corpus)

        # 6. LLM 종합 분석
        summary = self._generate_summary(
            company, financial, funding_history, team_info, risks, corpus
        )

        # 7. 점수 계산
        score = self._calculate_score(financial, funding_history, team_info, risks)

        # 결과 출력
        print(f"\n✅ 생존성 분석 완료")
        if financial.get("runway_months"):
            print(f"   Runway: {financial['runway_months']}개월")
        if funding_history:
            print(f"   투자: {len(funding_history)}건")
        if team_info.get("team_size"):
            print(f"   팀: {team_info['team_size']}명")
        print(f"   리스크: {len(risks)}개")
        print(f"   점수: {score}/100")

        # State 업데이트
        result = {
            "survival_analysis": {
                "financial": financial,
                "funding_history": funding_history,
                "team_info": team_info,
                "risks": risks,
                "summary": summary,
                "score": score,
            }
        }

        return result

    def _collect_corpus(self, company: str) -> str:
        """검색으로 코퍼스 수집"""
        if not self.tavily_client:
            print("⚠️ Tavily 클라이언트 없음")
            return ""

        corpus_parts = []

        for query_template in self.config.search_queries_template:
            query = query_template.format(company=company)
            print(f"📡 검색: {query}")

            try:
                response = self.tavily_client.search(
                    query=query,
                    max_results=self.config.max_results,
                    search_depth="basic",
                )

                for result in response.get("results", []):
                    title = result.get("title", "")
                    content = result.get("content", "")
                    corpus_parts.append(f"{title}\n{content}")

            except Exception as e:
                print(f"⚠️ 검색 실패: {e}")
                continue

        return "\n\n".join(corpus_parts)

    def _extract_financial(self, corpus: str) -> Dict[str, Any]:
        """재무 정보 추출"""
        financial = {}

        # Runway 추출
        runway_pattern = re.compile(
            r"(런웨이|runway)[^\d]{0,10}(\d+)\s*(개월|month)", re.IGNORECASE
        )
        runway_match = runway_pattern.search(corpus)
        if runway_match:
            financial["runway_months"] = int(runway_match.group(2))

        # Burn Rate 추출
        burn_pattern = re.compile(
            r"(burn rate|소진율)[^\d]{0,10}(\d+(?:\.\d+)?)\s*(억|million)",
            re.IGNORECASE,
        )
        burn_match = burn_pattern.search(corpus)
        if burn_match:
            value = float(burn_match.group(2))
            unit = burn_match.group(3).lower()
            if "million" in unit:
                value *= 0.13  # 백만달러 → 억원
            financial["burn_rate_monthly"] = round(value, 2)

        return financial

    def _extract_funding_history(self, corpus: str) -> List[Dict[str, Any]]:
        """투자 이력 추출"""
        funding_list = []

        # 투자 키워드
        funding_keywords = [
            "시드",
            "시리즈 A",
            "시리즈 B",
            "시리즈 C",
            "프리 시리즈 A",
            "브리지",
            "Seed",
            "Series A",
            "Series B",
            "Pre-Series A",
            "Bridge",
        ]

        for keyword in funding_keywords:
            if keyword in corpus:
                # 금액 추출
                pattern = re.compile(
                    rf"{keyword}[^\d]{{0,20}}(\d+(?:\.\d+)?)\s*(억|만|달러|USD|원|million)",
                    re.IGNORECASE,
                )
                match = pattern.search(corpus)
                if match:
                    amount = float(match.group(1))
                    unit = match.group(2)

                    # 억원으로 통일
                    if "만" in unit:
                        amount /= 10000
                    elif (
                        "million" in unit.lower()
                        or "usd" in unit.lower()
                        or "달러" in unit
                    ):
                        amount *= 0.13

                    funding_list.append(
                        {
                            "stage": keyword,
                            "amount_krw": round(amount, 2),
                        }
                    )

        return funding_list

    def _extract_team_info(self, corpus: str) -> Dict[str, Any]:
        """팀 정보 추출"""
        team = {}

        # 팀 규모 추출
        size_pattern = re.compile(r"(임직원|직원|팀)\s*(\d+)\s*명", re.IGNORECASE)
        size_match = size_pattern.search(corpus)
        if size_match:
            team["team_size"] = int(size_match.group(2))

        # 핵심 인물 추출 (CEO, CTO 등)
        key_people = []
        people_pattern = re.compile(
            r"(CEO|CTO|CFO|대표|이사|창업자)[:\s]*([가-힣a-zA-Z\s]+)",
            re.IGNORECASE,
        )
        for match in people_pattern.finditer(corpus):
            role = match.group(1)
            name = match.group(2).strip()
            if name and len(name) < 20:
                key_people.append({"role": role, "name": name})

        if key_people:
            team["key_people"] = key_people[:5]

        return team

    def _extract_risks(self, corpus: str) -> List[str]:
        """리스크 요인 추출"""
        risks = []

        # 리스크 키워드
        risk_keywords = [
            "적자",
            "손실",
            "부채",
            "이슈",
            "문제",
            "논란",
            "소송",
            "규제",
            "경쟁",
            "지연",
            "실패",
        ]

        for keyword in risk_keywords:
            if keyword in corpus:
                # 주변 문맥 추출
                pattern = re.compile(
                    rf"([^.!?]{0,50}{keyword}[^.!?]{{0,50}})", re.IGNORECASE
                )
                match = pattern.search(corpus)
                if match:
                    context = match.group(1).strip()
                    if context and context not in risks:
                        risks.append(context)

        return risks[:5]

    def _generate_summary(
        self,
        company: str,
        financial: Dict[str, Any],
        funding_history: List[Dict[str, Any]],
        team_info: Dict[str, Any],
        risks: List[str],
        corpus: str,
    ) -> str:
        """종합 요약 생성"""
        if not self.llm:
            return f"{company} 생존성 분석 완료"

        prompt = f"""당신은 스타트업 투자 전문가입니다. {company}의 생존 가능성을 평가하세요.

## 수집된 정보:
- 재무: {financial}
- 투자: {len(funding_history)}건, {funding_history[:2]}
- 팀: {team_info}
- 리스크: {len(risks)}개

## 추가 정보:
{corpus[:1500]}

## 출력 형식:
**재무 안정성**: [평가]
**자금 조달 능력**: [평가]
**팀 역량**: [평가]
**주요 리스크**: [평가]
**종합**: [2-3줄 요약]"""

        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            print(f"⚠️ LLM 요약 실패: {e}")
            return f"{company} 생존성 분석: 투자 {len(funding_history)}건, 팀 {team_info.get('team_size', 'N/A')}명"

    def _calculate_score(
        self,
        financial: Dict[str, Any],
        funding_history: List[Dict[str, Any]],
        team_info: Dict[str, Any],
        risks: List[str],
    ) -> float:
        """생존성 점수 계산"""
        score = 0.0

        # Runway 점수 (30점)
        runway = financial.get("runway_months", 0)
        if runway >= 18:
            score += 30
        elif runway >= 12:
            score += 25
        elif runway >= 6:
            score += 20
        elif runway > 0:
            score += 10

        # 투자 이력 점수 (40점)
        funding_score = min(len(funding_history) * 10, 40)
        score += funding_score

        # 팀 규모 점수 (20점)
        team_size = team_info.get("team_size", 0)
        if team_size >= 50:
            score += 20
        elif team_size >= 20:
            score += 15
        elif team_size >= 10:
            score += 10
        elif team_size > 0:
            score += 5

        # 리스크 감점 (-10점)
        risk_penalty = min(len(risks) * 2, 10)
        score -= risk_penalty

        return round(max(score, 0), 2)


def _demo():
    """데모 실행"""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from graph.state import create_initial_state

    state = create_initial_state()
    state["profile"] = {"name": "나라스페이스"}

    analyzer = SurvivalAnalyzer()
    result = analyzer.run(state)

    print("\n" + "=" * 80)
    print("📊 최종 결과")
    print("=" * 80)
    print(result["survival_analysis"]["summary"])


if __name__ == "__main__":
    _demo()
