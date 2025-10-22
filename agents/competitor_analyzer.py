"""
경쟁사 분석 에이전트
선택된 후보의 경쟁사를 찾고, 비교 가능성을 검증하여 평가 모드를 결정합니다.
"""

from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from tavily import TavilyClient
import os


class Competitor(BaseModel):
    """경쟁사 모델"""

    name: str = Field(description="경쟁사 이름")
    description: str = Field(description="경쟁사 설명")
    website: str = Field(description="웹사이트 URL", default="")
    similarity_score: float = Field(description="후보와의 유사도 (0-1)", ge=0, le=1)
    competitive_advantage: str = Field(description="경쟁 우위 요소", default="")


class CompetitorAnalysis(BaseModel):
    """경쟁사 분석 결과"""

    competitors: List[Competitor] = Field(description="경쟁사 리스트")
    comparison_mode: str = Field(
        description="평가 모드: 'relative' (상대평가) 또는 'absolute' (절대평가)"
    )
    validation_status: str = Field(
        description="검증 상태: 'validated', 'no_competitors', 'insufficient_data'"
    )
    reasoning: str = Field(description="평가 모드 선택 이유")


def search_competitors(candidate: Dict, max_results: int = 10) -> List[Dict]:
    """
    후보의 경쟁사 검색

    Args:
        candidate: 후보 스타트업 정보
        max_results: 최대 검색 결과 수

    Returns:
        검색 결과 리스트
    """
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    candidate_name = candidate.get("name", "")
    candidate_category = candidate.get("category", "")

    if not tavily_api_key:
        print("⚠️ TAVILY_API_KEY가 설정되지 않았습니다. 더미 데이터를 반환합니다.")
        return [
            {
                "title": f"{candidate_name} 경쟁사 {i+1}",
                "url": f"https://example.com/competitor{i+1}",
                "content": f"{candidate_category} 분야의 경쟁사입니다.",
                "score": 0.8 - (i * 0.1),
            }
            for i in range(2)
        ]

    try:
        client = TavilyClient(api_key=tavily_api_key)

        # 경쟁사 검색 쿼리 생성
        search_query = f"{candidate_name} competitors {candidate_category} startup"

        search_result = client.search(
            query=search_query,
            max_results=max_results,
            search_depth="advanced",
        )
        return search_result.get("results", [])
    except Exception as e:
        print(f"⚠️ 경쟁사 검색 중 오류 발생: {e}")
        return []


def analyze_competitors_and_validate(
    candidate: Dict,
    search_results: List[Dict],
    tech_analysis: Dict = None,
    market_analysis: Dict = None,
    survival_analysis: Dict = None,
) -> CompetitorAnalysis:
    """
    경쟁사를 분석하고 비교 가능성을 검증

    1차 분석 결과(기술/시장/생존성)를 활용하여 더 정확한 경쟁사를 선택합니다.

    Args:
        candidate: 후보 스타트업 정보
        search_results: 경쟁사 검색 결과
        tech_analysis: 1차 기술 분석 결과 (optional)
        market_analysis: 1차 시장 분석 결과 (optional)
        survival_analysis: 1차 생존성 분석 결과 (optional)

    Returns:
        경쟁사 분석 결과 (경쟁사 목록 + 평가 모드)
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    parser = JsonOutputParser(pydantic_object=CompetitorAnalysis)

    # 1차 분석 요약 생성
    candidate_name = candidate.get("name", "")
    analysis_summary = "1차 분석 정보 없음"

    if tech_analysis or market_analysis or survival_analysis:
        analysis_summary = ""

        if tech_analysis and candidate_name in tech_analysis:
            tech_info = tech_analysis[candidate_name]
            analysis_summary += f"\n🔬 기술: {tech_info.get('tech_stack', 'N/A')[:100]}"

        if market_analysis and candidate_name in market_analysis:
            market_info = market_analysis[candidate_name]
            analysis_summary += (
                f"\n📈 시장: {market_info.get('market_size', 'N/A')[:100]}"
            )

        if survival_analysis and candidate_name in survival_analysis:
            survival_info = survival_analysis[candidate_name]
            analysis_summary += (
                f"\n💰 자금: {survival_info.get('funding', 'N/A')[:100]}"
            )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """당신은 벤처 투자 전문가입니다.
후보 스타트업의 1차 분석 결과를 토대로 경쟁사를 선택하고 평가 방식을 결정하세요.

## 평가 모드 결정 기준:

1. **상대평가 (relative)**:
   - 유사한 경쟁사가 2개 이상 존재
   - 경쟁사와 직접 비교 가능한 데이터가 충분함
   - 같은 시장/카테고리에서 경쟁

2. **절대평가 (absolute)**:
   - 경쟁사가 없거나 1개 이하
   - 완전히 새로운 시장/기술
   - 경쟁사 정보가 불충분

## 경쟁사 선택 기준:
- 1차 분석에서 파악된 기술/시장과 유사한 경쟁사
- 동일 또는 유사한 비즈니스 모델
- 같은 타겟 시장/고객층
- 직접적인 경쟁 관계

최대 3개의 주요 경쟁사를 선택하세요.

{format_instructions}
""",
            ),
            (
                "user",
                """
후보 스타트업:
- 이름: {candidate_name}
- 설명: {candidate_description}
- 분야: {candidate_category}

1차 분석 결과:
{analysis_summary}

경쟁사 검색 결과:
{search_results}

위 정보를 바탕으로:
1. 1차 분석 결과를 참고하여 주요 경쟁사를 선택하고
2. 평가 모드(상대평가/절대평가)를 결정하세요.
""",
            ),
        ]
    )

    chain = prompt | llm | parser

    try:
        # 검색 결과 포매팅
        formatted_results = "\n\n".join(
            [
                f"[{i+1}] {r.get('title', 'N/A')}\nURL: {r.get('url', 'N/A')}\n{r.get('content', 'N/A')[:500]}"
                for i, r in enumerate(search_results[:10])
            ]
        )

        result = chain.invoke(
            {
                "candidate_name": candidate.get("name", ""),
                "candidate_description": candidate.get("description", ""),
                "candidate_category": candidate.get("category", ""),
                "analysis_summary": analysis_summary,
                "search_results": formatted_results,
                "format_instructions": parser.get_format_instructions(),
            }
        )

        return CompetitorAnalysis(**result)

    except Exception as e:
        print(f"⚠️ 경쟁사 분석 중 오류 발생: {e}")
        # 폴백: 절대평가 모드
        return CompetitorAnalysis(
            competitors=[],
            comparison_mode="absolute",
            validation_status="insufficient_data",
            reasoning="경쟁사 정보가 불충분하여 절대평가로 진행합니다.",
        )


def run(state: Dict) -> Dict:
    """
    경쟁사 분석 에이전트 실행

    1차 분석 결과(기술/시장/생존성)를 토대로 경쟁사를 탐색합니다.

    Args:
        state: AgentState (candidates, tech_analysis, market_analysis, survival_analysis 포함)

    Returns:
        업데이트된 state (competitors, comparison_mode, validation 포함)
    """
    candidates = state.get("candidates", [])

    if not candidates:
        print("\n⚠️ 분석할 후보가 없습니다.")
        return {
            "competitors": [],
            "comparison_mode": "absolute",
            "validation": {
                "status": "no_candidates",
                "message": "후보가 없어 절대평가로 진행합니다.",
            },
        }

    # 첫 번째 후보를 주요 분석 대상으로 선택
    primary_candidate = candidates[0]

    # 1차 분석 결과 가져오기
    tech_analysis = state.get("tech_analysis", {})
    market_analysis = state.get("market_analysis", {})
    survival_analysis = state.get("survival_analysis", {})

    print(f"\n🔍 경쟁사 탐색 시작: {primary_candidate.get('name', 'N/A')}")
    print(f"  📊 1차 분석 결과를 토대로 경쟁사를 탐색합니다")

    # 1차 분석 요약 출력
    if tech_analysis:
        tech_summary = tech_analysis.get(primary_candidate.get("name"), {})
        print(f"  🔬 기술: {tech_summary.get('tech_stack', 'N/A')[:50]}...")
    if market_analysis:
        market_summary = market_analysis.get(primary_candidate.get("name"), {})
        print(f"  📈 시장: {market_summary.get('market_size', 'N/A')[:50]}...")
    if survival_analysis:
        survival_summary = survival_analysis.get(primary_candidate.get("name"), {})
        print(f"  💰 자금: {survival_summary.get('funding', 'N/A')[:50]}...")

    # 1. 1차 분석 기반 검색 쿼리 강화
    enhanced_query = primary_candidate.get("category", "")
    if tech_analysis:
        tech_info = tech_analysis.get(primary_candidate.get("name"), {})
        tech_keywords = tech_info.get("tech_stack", "")
        if tech_keywords:
            enhanced_query += f" {tech_keywords[:50]}"  # 기술 키워드 추가

    print(f"  🔍 검색 쿼리: {enhanced_query}")

    # 2. 경쟁사 검색
    print("📡 경쟁사 검색 중...")
    search_results = search_competitors(primary_candidate, max_results=10)
    print(f"✅ {len(search_results)}개의 검색 결과 발견")

    # 경쟁사가 없는 경우 처리
    if not search_results or len(search_results) == 0:
        print("\n⚠️ 경쟁사를 찾을 수 없습니다.")
        print("  → 현재 후보만으로 절대평가를 진행합니다.")
        return {
            "competitors": [],
            "comparison_mode": "absolute",
            "validation": {
                "status": "no_competitors",
                "message": f"{primary_candidate.get('name')}의 경쟁사를 찾을 수 없어 절대평가로 진행합니다.",
            },
        }

    # 3. 경쟁사 분석 및 평가 모드 결정 (1차 분석 결과 포함)
    print("🤖 AI 분석 및 검증 중...")
    analysis = analyze_competitors_and_validate(
        primary_candidate,
        search_results,
        tech_analysis=tech_analysis,
        market_analysis=market_analysis,
        survival_analysis=survival_analysis,
    )
    print(f"✅ {len(analysis.competitors)}개의 경쟁사 식별됨")
    print(f"📊 평가 모드: {analysis.comparison_mode}")
    print(f"💡 이유: {analysis.reasoning}")

    # 3. State 업데이트
    competitors = [
        {
            "name": c.name,
            "description": c.description,
            "website": c.website,
            "similarity_score": c.similarity_score,
            "competitive_advantage": c.competitive_advantage,
        }
        for c in analysis.competitors
    ]

    if competitors:
        print("\n✅ 발견된 경쟁사:")
        for i, comp in enumerate(competitors, 1):
            print(f"  {i}. {comp['name']} (유사도: {comp['similarity_score']:.2f})")
        print(
            f"\n  📊 다음 단계: 후보 + 경쟁사 {len(competitors)}개를 포함한 2차 비교 분석"
        )
    else:
        print("\n⚠️ 경쟁사 없음 → 절대평가로 진행")
        print(f"  📊 다음 단계: {primary_candidate.get('name')} 단독 평가")

    return {
        "competitors": competitors,
        "comparison_mode": analysis.comparison_mode,
        "validation": {
            "status": analysis.validation_status,
            "reasoning": analysis.reasoning,
            "competitor_count": len(competitors),
        },
    }


# 테스트용 코드
if __name__ == "__main__":
    test_state = {
        "query": "AI 핀테크 스타트업",
        "candidates": [
            {
                "name": "FinAI",
                "description": "AI 기반 개인 금융 관리 플랫폼",
                "category": "AI 핀테크",
                "website": "https://example.com",
                "relevance_score": 0.9,
            }
        ],
    }

    result = run(test_state)
    print("\n=== 결과 ===")
    print(f"경쟁사 수: {len(result['competitors'])}")
    print(f"평가 모드: {result['comparison_mode']}")
    print(f"검증 상태: {result['validation']}")
