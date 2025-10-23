"""
Agent 0: Space Company Finder
한국 우주산업 스타트업 발굴 및 기본 정보 수집
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 찾기
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
env_path = project_root / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_teddynote.tools import GoogleNews
except ImportError:
    GoogleNews = None

try:
    from langchain.output_parsers import StructuredOutputParser, ResponseSchema
    from langchain.prompts import ChatPromptTemplate
except ImportError:
    StructuredOutputParser = None
    ResponseSchema = None
    ChatPromptTemplate = None


# ═══════════════════════════════════════════════════════════════════════════
# 설정
# ═══════════════════════════════════════════════════════════════════════════


class AgentConfig:
    """Agent 0 설정"""

    DEFAULT_COMPANY = "나라스페이스"
    MAX_SEARCH_RESULTS = 5
    CANDIDATE_LIMIT = 5

    CURRENT_YEAR = datetime.now().year
    MIN_FOUNDING_YEAR = 2010
    MAX_FOUNDING_YEAR = CURRENT_YEAR

    DISCOVERY_QUERIES = [
        "한국 우주산업 스타트업 {year}",
        "AI 위성 스타트업 한국",
        "큐브위성 스타트업 한국",
    ]

    SPACE_TECH_KEYWORDS = [
        "AI",
        "영상분석",
        "큐브위성",
        "데이터",
        "위성",
        "저궤도",
        "LEO",
        "광학위성",
        "SAR",
        "지구관측",
        "소형위성",
        "페이로드",
        "우주통신",
    ]

    PARTNER_KEYWORDS = [
        "항공우주연구원",
        "KARI",
        "KAIST",
        "한화",
        "한화시스템",
        "LG",
        "SK",
        "KT",
        "ETRI",
        "한국천문연구원",
        "과기부",
    ]

    INVESTMENT_STAGES = [
        ("시리즈D", ["Series D", "시리즈D"]),
        ("시리즈C", ["Series C", "시리즈C"]),
        ("시리즈B", ["Series B", "시리즈B"]),
        ("시리즈A", ["Series A", "시리즈A"]),
        ("프리시리즈A", ["Pre-Series A", "프리시리즈A"]),
        ("시드", ["Seed", "시드", "엔젤"]),
    ]

    FUNDING_AMOUNTS = [1000, 500, 400, 300, 200, 150, 100, 50, 30, 20, 10]


class _FallbackTavilyClient:
    """Tavily SDK 없을 때 fallback"""

    def __init__(self, *_, **__):
        pass

    def search(self, query: str, max_results: int = 5):
        print(f"⚠️ tavily 패키지 없음: '{query}' 검색 불가")
        return {"results": []}


# ═══════════════════════════════════════════════════════════════════════════
# Agent 0: Space Company Finder
# ═══════════════════════════════════════════════════════════════════════════


class SpaceCompanyFinder:
    """우주산업 스타트업 발굴 Agent"""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()

        # Tavily 초기화
        if TavilyClient is None:
            self.tavily = _FallbackTavilyClient()
        else:
            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                print("⚠️ TAVILY_API_KEY 없음")
                self.tavily = _FallbackTavilyClient()
            else:
                self.tavily = TavilyClient(api_key=api_key)

        # LLM 초기화
        if ChatOpenAI is None:
            self.llm = None
        else:
            try:
                self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            except Exception as exc:
                print(f"⚠️ LLM 초기화 실패: {exc}")
                self.llm = None

        # GoogleNews 초기화
        if GoogleNews is None:
            self.google_news = None
        else:
            try:
                self.google_news = GoogleNews()
            except Exception as exc:
                print(f"⚠️ GoogleNews 초기화 실패: {exc}")
                self.google_news = None

    # ═══════════════════════════════════════════════════════════════════════
    # 검색 메서드
    # ═══════════════════════════════════════════════════════════════════════

    def search(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        """Tavily 검색"""
        if max_results is None:
            max_results = self.config.MAX_SEARCH_RESULTS

        try:
            result = self.tavily.search(query, max_results=max_results)
            return result.get("results", [])
        except Exception as e:
            print(f"⚠️ 검색 실패 ({query}): {e}")
            return []

    def search_news(self, query: str, k: int = 5) -> List[Dict]:
        """GoogleNews 검색"""
        if self.google_news is None:
            return []

        try:
            results = self.google_news.search_by_keyword(query, k=k)
            return results if results else []
        except Exception as e:
            print(f"⚠️ 뉴스 검색 실패 ({query}): {e}")
            return []

    def search_combined(self, query: str, max_results: int = 5) -> str:
        """Tavily + GoogleNews 통합 검색"""
        all_text = ""

        # Tavily
        tavily_results = self.search(query, max_results=max_results)
        if tavily_results:
            all_text += "[Tavily]\n"
            all_text += self.extract_text(tavily_results) + "\n\n"

        # GoogleNews
        news_results = self.search_news(query, k=max_results)
        if news_results:
            all_text += "[News]\n"
            for item in news_results:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                if title:
                    all_text += f"[제목] {title}\n"
                if snippet:
                    all_text += f"{snippet}\n"
            all_text += "\n"

        return all_text

    def extract_text(self, results: List[Dict]) -> str:
        """검색 결과 텍스트 추출"""
        texts = []
        for r in results:
            title = r.get("title", "")
            content = r.get("content", "")
            if title:
                texts.append(f"[제목] {title}")
            if content:
                texts.append(content)
        return "\n".join(texts)

    # ═══════════════════════════════════════════════════════════════════════
    # Stage 1: 기업 발굴
    # ═══════════════════════════════════════════════════════════════════════

    def find_company(self) -> str:
        """한국 우주산업 스타트업 찾기"""
        print("\n" + "=" * 80)
        print("[Stage 1] 한국 우주산업 스타트업 발굴")
        print("=" * 80)

        # 기본 기업 사용
        company = self.config.DEFAULT_COMPANY
        print(f"\n✓ 대상 기업: {company}")
        return company

    # ═══════════════════════════════════════════════════════════════════════
    # Stage 2: 기본 정보 (profile)
    # ═══════════════════════════════════════════════════════════════════════

    def collect_profile(self, company: str) -> Dict:
        """기업 기본 정보 수집 → profile"""
        print("\n" + "=" * 80)
        print(f"[Stage 2] {company} 기본 정보")
        print("=" * 80)

        profile = {
            "name": company,
            "founded_year": None,
            "business_description": "",
        }

        queries = [
            f"{company} 나무위키",
            f"{company} 회사소개 IR",
            f"{company} 설립 대표 본사",
        ]

        all_text = ""
        for i, q in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] 검색: {q}")
            text = self.search_combined(q, max_results=3)
            all_text += text
            print(f"  → {len(text)}자")

        # LLM 추출 (설립연도만)
        if self.llm and all_text.strip():
            print("\n[LLM] 설립연도 추출...")
            try:
                prompt = f"'{company}'의 설립연도를 찾으세요. 숫자만 출력 (예: 2015):\n\n{all_text[:1500]}"
                response = self.llm.invoke(prompt)
                year_str = response.content.strip()
                match = re.search(r"(\d{4})", year_str)
                if match:
                    year = int(match.group(1))
                    if 2010 <= year <= 2024:
                        profile["founded_year"] = year
                        print(f"  ✓ 설립: {year}")
            except Exception as e:
                print(f"  ⚠️ LLM 실패: {e}")

        # 정규식 fallback (설립연도만)
        if not profile["founded_year"]:
            print("\n[정규식] 설립연도...")
            patterns = [
                r"설립[^\d]*(\d{4})",
                r"(\d{4})\s*년[^\n]{0,5}설립",
                r"창립[^\d]*(\d{4})",
            ]
            for pattern in patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    year = int(match)
                    if 2010 <= year <= 2024:
                        profile["founded_year"] = year
                        print(f"  → {year}년")
                        break
                if profile["founded_year"]:
                    break

        # 사업 설명
        if all_text:
            idx = all_text.find(company)
            if idx != -1:
                profile["business_description"] = all_text[idx : idx + 300].strip()
            else:
                profile["business_description"] = all_text[:250].strip()

        return profile

    # ═══════════════════════════════════════════════════════════════════════
    # Stage 3: 우주산업 정보 (space)
    # ═══════════════════════════════════════════════════════════════════════

    def collect_space_info(self, company: str) -> Dict:
        """우주산업 특화 정보 → space"""
        print("\n" + "=" * 80)
        print(f"[Stage 3] {company} 우주산업 정보")
        print("=" * 80)

        space = {
            "main_technology": [],
        }

        queries = [
            f"{company} 큐브위성 기술",
            f"{company} 위성 영상분석",
            f"{company} 우주산업 기술",
        ]

        all_text = ""
        for i, q in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] 검색: {q}")
            text = self.search_combined(q, max_results=3)
            all_text += text
            print(f"  → {len(text)}자")

        # 기술 키워드 추출
        print("\n[분석] 기술 스택...")
        text_lower = all_text.lower()
        for keyword in self.config.SPACE_TECH_KEYWORDS:
            if keyword.lower() in text_lower or keyword in all_text:
                space["main_technology"].append(keyword)

        if space["main_technology"]:
            print(f"  → {', '.join(space['main_technology'][:5])}")

        return space

    # ═══════════════════════════════════════════════════════════════════════
    # Stage 4: 투자 정보 (funding)
    # ═══════════════════════════════════════════════════════════════════════

    def collect_funding_info(self, company: str) -> Dict:
        """투자 및 파트너십 → funding"""
        print("\n" + "=" * 80)
        print(f"[Stage 4] {company} 투자 정보")
        print("=" * 80)

        funding = {
            "stage": None,
            "total_funding_krw": None,
            "partners": [],
        }

        queries = [
            f"{company} 투자 유치",
            f"{company} 시리즈 펀딩",
            f"{company} 협력사 MOU",
        ]

        all_text = ""
        for i, q in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] 검색: {q}")
            text = self.search_combined(q, max_results=3)
            all_text += text
            print(f"  → {len(text)}자")

        # 투자 단계
        print("\n[분석] 투자 단계...")
        for stage_name, keywords in self.config.INVESTMENT_STAGES:
            if any(kw in all_text for kw in keywords):
                funding["stage"] = stage_name
                print(f"  → {stage_name}")
                break

        # 투자 금액
        print("\n[분석] 투자 금액...")
        for amount in self.config.FUNDING_AMOUNTS:
            if f"{amount}억" in all_text:
                funding["total_funding_krw"] = amount
                print(f"  → {amount}억원")
                break

        # 파트너
        print("\n[분석] 파트너...")
        for keyword in self.config.PARTNER_KEYWORDS:
            if keyword in all_text:
                funding["partners"].append(keyword)

        if funding["partners"]:
            print(f"  → {', '.join(funding['partners'][:3])}")

        return funding

    # ═══════════════════════════════════════════════════════════════════════
    # 통합 실행
    # ═══════════════════════════════════════════════════════════════════════

    def run(self) -> Dict:
        """Agent 0 전체 실행"""
        print("\n" + "=" * 80)
        print("🚀 Agent 0: Space Company Finder 시작")
        print("=" * 80)

        # 1. 기업 발굴
        company = self.find_company()

        # 2. 기본 정보
        profile = self.collect_profile(company)

        # 3. 우주산업 정보
        space = self.collect_space_info(company)

        # 4. 투자 정보
        funding = self.collect_funding_info(company)

        # State 반환 (새로운 구조)
        state = {
            "profile": profile,
            "space": space,
            "funding": funding,
            "meta": {
                "current_agent": "agent_1",
                "stage": "growth_analysis",
                "data_quality": "high" if profile.get("founded_year") else "medium",
            },
        }

        # 최종 요약
        print("\n" + "=" * 80)
        print("✅ Agent 0 완료")
        print("=" * 80)
        print(f"📌 기업: {profile.get('name')}")

        # 정보가 있는 항목만 출력
        if profile.get("founded_year"):
            print(f"📅 설립: {profile.get('founded_year')}년")

        # 투자 정보
        if funding.get("total_funding_krw") and funding.get("stage"):
            print(
                f"💰 투자: {funding.get('total_funding_krw')}억 ({funding.get('stage')})"
            )
        elif funding.get("total_funding_krw"):
            print(f"💰 투자: {funding.get('total_funding_krw')}억")
        elif funding.get("stage"):
            print(f"💰 투자: {funding.get('stage')}")

        if space.get("main_technology"):
            print(f"🔬 기술: {', '.join(space.get('main_technology', [])[:5])}")

        if funding.get("partners"):
            print(f"🤝 파트너: {', '.join(funding.get('partners', [])[:3])}")

        print(f"📊 품질: {state['meta']['data_quality']}")
        print("=" * 80)

        return state


# ═══════════════════════════════════════════════════════════════════════════
# 테스트
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not os.getenv("TAVILY_API_KEY"):
        print("❌ TAVILY_API_KEY 설정 필요")
        exit(1)

    agent = SpaceCompanyFinder()
    result = agent.run()

    # 결과 저장
    output_file = "agent0_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n💾 결과 저장: {output_file}")
