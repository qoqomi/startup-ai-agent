"""
후보 선택 에이전트
사용자 query를 기반으로 투자 평가할 스타트업 후보를 선택합니다.
"""

from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from tavily import TavilyClient
from dotenv import load_dotenv
import os

# 환경변수 로드
load_dotenv()


class StartupCandidate(BaseModel):
    """스타트업 후보 모델"""

    name: str = Field(description="스타트업 이름")
    description: str = Field(description="스타트업 설명")
    website: str = Field(description="웹사이트 URL", default="")
    founded_year: str = Field(description="설립 연도", default="")
    country: str = Field(
        description="본사 위치 국가 (예: South Korea, USA)", default=""
    )
    category: str = Field(description="산업 분야/카테고리")
    relevance_score: float = Field(
        description="검색 쿼리와의 관련성 점수 (0-1)", ge=0, le=1
    )
    reasoning: str = Field(description="선택 이유")


class CandidateList(BaseModel):
    """후보 리스트 모델"""

    candidates: List[StartupCandidate] = Field(description="스타트업 후보 리스트")
    total_found: int = Field(description="검색된 총 후보 수")
    search_summary: str = Field(description="검색 요약")


def search_startups(query: str, max_results: int = 10) -> List[Dict]:
    """
    Tavily API를 사용하여 스타트업 검색

    Args:
        query: 검색 쿼리
        max_results: 최대 검색 결과 수

    Returns:
        검색 결과 리스트
    """
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        print("⚠️ TAVILY_API_KEY가 설정되지 않았습니다. 더미 데이터를 반환합니다.")
        # 개발용 더미 데이터
        return [
            {
                "title": f"스타트업 예시 {i+1}",
                "url": f"https://example.com/startup{i+1}",
                "content": f"{query}와 관련된 스타트업 {i+1}입니다.",
                "score": 0.9 - (i * 0.1),
            }
            for i in range(3)
        ]

    try:
        client = TavilyClient(api_key=tavily_api_key)
        search_result = client.search(
            query=f"{query} 한국 스타트업 투자 유치 Korea startup funding",
            max_results=max_results,
            search_depth="advanced",
            days=720,
            include_domains=[
                "crunchbase.com",  # 스타트업 데이터베이스
                "techcrunch.com",  # 테크 뉴스
                "platum.kr",  # 한국 스타트업 뉴스
                "startuptoday.kr",  # 한국 스타트업 투데이
                "venturesquare.net",  # 벤처스퀘어
                "beSUCCESS.com",  # 비석세스
                "zdnet.co.kr",  # 한국 IT 뉴스
                "mk.co.kr",  # 매일경제
                "hankyung.com",  # 한국경제
                "forbes.com",  # 비즈니스 뉴스
            ],
        )
        return search_result.get("results", [])
    except Exception as e:
        print(f"⚠️ 검색 중 오류 발생: {e}")
        return []


def analyze_candidates(query: str, search_results: List[Dict]) -> CandidateList:
    """
    검색 결과를 분석하여 투자 후보 선택

    Args:
        query: 사용자 검색 쿼리
        search_results: 웹 검색 결과

    Returns:
        선택된 후보 리스트
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    parser = JsonOutputParser(pydantic_object=CandidateList)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """당신은 벤처 투자 전문가입니다.
검색 결과를 분석하여 투자 가치가 있는 스타트업 후보를 선택하세요.

🚨 **필수 조건**:
1. **반드시 한국(South Korea)에 본사를 둔 스타트업만 선택**
2. **정확히 1개만 선택** (가장 투자 가치가 높은 후보)
3. 검색 결과에서 "South Korea", "Seoul", "한국", "대한민국" 등의 키워드 확인
4. country 필드에 반드시 국가 정보 기입
5. 선택 이유와 설명에 대해서는 한국말로 작성하세요.

선택 기준:
1. **한국 기업 필수**: 한국에 본사를 둔 스타트업만 선택 (외국 기업 제외)
2. 혁신성: 새로운 기술이나 비즈니스 모델
3. 시장성: 명확한 타겟 시장과 성장 가능성
4. 정보 가용성: 투자 분석에 필요한 정보가 충분한지
5. 투자 가치: 최고의 투자 후보 1개 선정


**정확히 1개의 한국 스타트업**을 선택하세요.
이후 경쟁사 탐색 단계에서 비교 대상을 찾습니다.

예시:
- ✅ 좋은 선택: 
  * "Rebellions (South Korea, AI Chip)" - 최고 투자 가치 보유
  * "Toss (South Korea, Fintech)" - 시장 선도 기업
- ❌ 나쁜 선택:
  * "OpenAI (USA)" → 외국 기업
  * 여러 개 선택 → 1개만 선택해야 함

{format_instructions}
""",
            ),
            (
                "user",
                """
검색 쿼리: {query}

검색 결과:
{search_results}

위 결과를 분석하여 투자 후보를 선택하세요.
""",
            ),
        ]
    )

    chain = prompt | llm | parser

    try:
        # 검색 결과를 포매팅
        formatted_results = "\n\n".join(
            [
                f"[{i+1}] {r.get('title', 'N/A')}\nURL: {r.get('url', 'N/A')}\n{r.get('content', 'N/A')[:500]}"
                for i, r in enumerate(search_results[:10])
            ]
        )

        result = chain.invoke(
            {
                "query": query,
                "search_results": formatted_results,
                "format_instructions": parser.get_format_instructions(),
            }
        )

        return CandidateList(**result)

    except Exception as e:
        print(f"⚠️ 후보 분석 중 오류 발생: {e}")
        # 폴백: 기본 후보 반환
        return CandidateList(
            candidates=[
                StartupCandidate(
                    name=f"후보 {i+1}",
                    description=r.get("content", "")[:200],
                    website=r.get("url", ""),
                    category="Unknown",
                    relevance_score=r.get("score", 0.5),
                    reasoning="검색 결과 기반 자동 선택",
                )
                for i, r in enumerate(search_results[:3])
            ],
            total_found=len(search_results),
            search_summary=f"{query}에 대한 검색 완료",
        )


def run(state: Dict) -> Dict:
    """
    후보 선택 에이전트 실행

    Args:
        state: AgentState (query 포함)

    Returns:
        업데이트된 state (candidates 포함)
    """
    query = state.get("query", "")
    print(f"\n🔍 후보 선택 시작: {query}")

    # 1. 웹 검색
    print("📡 웹 검색 중...")
    search_results = search_startups(query, max_results=10)
    print(f"✅ {len(search_results)}개의 검색 결과 발견")

    # 2. AI 분석으로 후보 선택
    print("🤖 AI 분석 중...")
    candidate_analysis = analyze_candidates(query, search_results)
    print(f"✅ {len(candidate_analysis.candidates)}개의 후보 선택됨")

    # 3. State 업데이트
    candidates = [
        {
            "name": c.name,
            "description": c.description,
            "website": c.website,
            "founded_year": c.founded_year,
            "country": c.country,
            "category": c.category,
            "relevance_score": c.relevance_score,
            "reasoning": c.reasoning,
        }
        for c in candidate_analysis.candidates
    ]

    print("\n✅ 선택된 투자 후보:")
    if len(candidates) > 0:
        c = candidates[0]
        country_flag = (
            "🇰🇷"
            if "Korea" in c.get("country", "") or "한국" in c.get("country", "")
            else "🌍"
        )
        print(f"  🎯 {c['name']} {country_flag}")
        print(f"     국가: {c.get('country', 'Unknown')}")
        print(f"     산업: {c.get('category', 'Unknown')}")
        print(f"     관련성: {c.get('relevance_score', 0):.2f}")
        print(f"     설명: {c['description'][:100]}...")
        print(f"\n  💡 선택 이유: {c.get('reasoning', 'N/A')}")
        print(f"\n  📊 다음 단계: 1차 분석 완료 후 이 후보의 경쟁사를 탐색합니다")

    return {
        **state,
        "candidates": candidates,
        "search_results": search_results,  # 캐싱용
    }


# 테스트용 코드
if __name__ == "__main__":
    test_state = {"query": "AI 데이팅 서비스 스타트업"}
    result = run(test_state)
    print("\n=== 결과 ===")
    print(f"후보 수: {len(result['candidates'])}")
    for candidate in result["candidates"]:
        print(f"\n{candidate['name']}")
        print(f"  - {candidate['description']}")
        print(f"  - 관련성: {candidate['relevance_score']}")
