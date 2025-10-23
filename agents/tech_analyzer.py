"""
Agent: 기술 분석 (Technology Analyzer)

후보 기업의 기술력을 분석합니다.
- TRL (Technology Readiness Level)
- 특허/IP
- 핵심 기술
- 기술 경쟁력
"""

from __future__ import annotations

import os
import re
from copy import deepcopy
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

try:
    from rag.evaluation_rag import EvaluationRAG
except ImportError:  # pragma: no cover
    EvaluationRAG = None  # type: ignore[assignment]

try:
    from tools.web_crawler import WebCrawler
except ImportError:  # pragma: no cover
    WebCrawler = None  # type: ignore[assignment]


@dataclass
class TechAnalyzerConfig:
    """기술 + 팀 분석 설정"""

    max_results: int = 3  # Rate limit 방지
    search_queries_template: List[str] = None

    def __post_init__(self):
        if self.search_queries_template is None:
            self.search_queries_template = [
                "{company} TRL 기술성숙도",
                "{company} 특허 기술",
                "{company} 핵심 기술",
                "{company} 기술 경쟁력",
                "{company} R&D",
                "{company} 창업자 CEO CTO",
                "{company} 팀 구성 인력",
                "{company} 경쟁사 비교",
            ]


class TechAnalyzer:
    """기술 분석 에이전트"""

    def __init__(
        self,
        config: Optional[TechAnalyzerConfig] = None,
        tavily_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        use_crawler: bool = True,  # 크롤러 우선 사용
    ):
        self.config = config or TechAnalyzerConfig()
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.use_crawler = use_crawler

        # 크롤러 초기화
        self.crawler = WebCrawler(delay=1.0) if WebCrawler and use_crawler else None

        # Tavily 비활성화 (API 한도 초과)
        self.tavily_client = None
        self.llm = (
            ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.0,
                api_key=self.openai_api_key,
            )
            if self.openai_api_key
            else None
        )

        # RAG 로드
        self.rag_knowledge = self._load_rag_knowledge()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """기술 분석 실행"""
        company = state.get("profile", {}).get("name")
        if not company:
            # candidates에서 가져오기
            candidates = state.get("candidates", [])
            if candidates:
                company = candidates[0].get("name")

        if not company:
            raise ValueError("기업명이 필요합니다")

        print(f"\n{'='*80}")
        print(f"🔬 [기술 분석] {company}")
        print(f"{'='*80}")

        # 1. 검색 수집
        corpus = self._collect_corpus(company)

        # 2. TRL 추출
        trl_level = self._extract_trl(corpus)

        # 3. 특허 정보 추출
        patents = self._extract_patents(corpus)

        # 4. 핵심 기술 추출
        core_tech = self._extract_core_technology(corpus)

        # 5. LLM 종합 분석
        summary = self._generate_summary(company, trl_level, patents, core_tech, corpus)

        # 6. 점수 계산
        score = self._calculate_score(trl_level, patents, core_tech)

        # 결과 출력
        print(f"\n✅ 기술 분석 완료")
        print(f"   TRL: {trl_level if trl_level else 'N/A'}")
        print(f"   특허: {len(patents)}건")
        print(f"   핵심기술: {len(core_tech)}개")
        print(f"   점수: {score}/100")

        # State 업데이트 (기존 데이터 보존)
        tech_data = {
            "trl_level": trl_level,
            "patents": patents,
            "core_technology": core_tech,
            "summary": summary,
            "score": score,
        }

        result = {
            "space": tech_data,  # InvestmentState의 올바른 키
            "tech_analysis": tech_data,  # report_generator 호환성 (deprecated)
        }

        return result

    def _collect_corpus(self, company: str) -> str:
        """검색으로 코퍼스 수집 (크롤러 우선, Tavily fallback)"""
        corpus_parts = []

        for query_template in self.config.search_queries_template:
            query = query_template.format(company=company)
            print(f"📡 검색: {query}")

            # 1. 크롤러 시도
            if self.crawler:
                try:
                    results = self.crawler.naver_search(
                        query, max_results=self.config.max_results
                    )
                    if results:
                        print(f"   ✓ 크롤러로 {len(results)}건 수집")
                        for result in results:
                            title = result.get("title", "")
                            content = result.get("content", "")
                            corpus_parts.append(f"{title}\n{content}")
                        continue
                except Exception as e:
                    print(f"   ⚠️ 크롤러 실패: {e}")

            # 2. Tavily fallback
            if self.tavily_client:
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
                    print(f"   ✓ Tavily로 수집")

                except Exception as e:
                    print(f"   ⚠️ Tavily 실패: {e}")
                    continue

        return "\n\n".join(corpus_parts)

    def _extract_trl(self, corpus: str) -> Optional[int]:
        """TRL 수준 추출"""
        # 정규식으로 TRL 찾기
        pattern = re.compile(r"TRL\s*[-:]?\s*(\d)", re.IGNORECASE)
        match = pattern.search(corpus)
        if match:
            return int(match.group(1))

        # LLM으로 추정
        if self.llm and corpus:
            prompt = f"""다음 텍스트에서 기업의 TRL(Technology Readiness Level) 수준을 추정하세요.

TRL 기준:
- TRL 1-3: 기초 연구
- TRL 4-6: 기술 개발 (프로토타입)
- TRL 7-9: 시스템 완성 (상용화)

텍스트:
{corpus[:2000]}

TRL 수준을 1-9 사이의 숫자 하나만 출력하세요. 알 수 없으면 "N/A"를 출력하세요."""

            try:
                response = self.llm.invoke(prompt)
                content = response.content.strip()
                if content.isdigit() and 1 <= int(content) <= 9:
                    return int(content)
            except:
                pass

        return None

    def _extract_patents(self, corpus: str) -> List[Dict[str, str]]:
        """특허 정보 추출"""
        patents = []

        # 정규식으로 특허 번호 찾기
        pattern = re.compile(
            r"(특허|등록번호|출원번호|patent)\s*[:：]?\s*([\w\d-]+)", re.IGNORECASE
        )

        for match in pattern.finditer(corpus):
            patent_type = match.group(1)
            patent_number = match.group(2)
            patents.append({"type": patent_type, "number": patent_number})

        # LLM으로 특허 내용 추출
        if self.llm and corpus and len(patents) < 3:
            prompt = f"""다음 텍스트에서 특허 관련 정보를 추출하세요.

텍스트:
{corpus[:2000]}

특허가 있다면 다음 형식으로 출력하세요:
1. [특허명]: [간단한 설명]
2. [특허명]: [간단한 설명]

특허 정보가 없으면 "없음"을 출력하세요."""

            try:
                response = self.llm.invoke(prompt)
                content = response.content.strip()

                if "없음" not in content:
                    # 라인별로 파싱
                    for line in content.split("\n"):
                        if line.strip() and re.match(r"\d+\.", line):
                            patents.append(
                                {"type": "특허", "description": line.strip()}
                            )
            except:
                pass

        return patents[:5]  # 최대 5개

    def _extract_core_technology(self, corpus: str) -> List[str]:
        """핵심 기술 추출"""
        technologies = []

        # 기술 키워드 찾기
        tech_keywords = [
            "AI",
            "인공지능",
            "머신러닝",
            "딥러닝",
            "위성",
            "큐브위성",
            "영상분석",
            "데이터분석",
            "자율주행",
            "IoT",
            "빅데이터",
            "클라우드",
        ]

        for keyword in tech_keywords:
            if keyword in corpus:
                technologies.append(keyword)

        # LLM으로 핵심 기술 추출
        if self.llm and corpus:
            prompt = f"""다음 텍스트에서 기업의 핵심 기술 3가지를 추출하세요.

텍스트:
{corpus[:2000]}

핵심 기술을 3개 이하로 간단히 나열하세요:
1. [기술명]
2. [기술명]
3. [기술명]"""

            try:
                response = self.llm.invoke(prompt)
                content = response.content.strip()

                for line in content.split("\n"):
                    if line.strip() and re.match(r"\d+\.", line):
                        tech = re.sub(r"^\d+\.\s*", "", line.strip())
                        if tech and tech not in technologies:
                            technologies.append(tech)
            except:
                pass

        return technologies[:5]  # 최대 5개

    def _generate_summary(
        self,
        company: str,
        trl_level: Optional[int],
        patents: List[Dict[str, str]],
        core_tech: List[str],
        corpus: str,
    ) -> str:
        """종합 요약 생성"""
        if not self.llm:
            return f"{company} 기술 분석 완료"

        # RAG 기준 가져오기
        berkus_criteria = self.rag_knowledge.get("berkus_criteria", {})
        tech_criteria = self.rag_knowledge.get("tech_evaluation", {})

        prompt = f"""당신은 벤처캐피탈 평가 전문가입니다. {company}의 기술과 팀을 분석하세요.

## 수집된 정보:
- TRL: {trl_level if trl_level else 'N/A'}
- 특허: {len(patents)}건
- 핵심 기술: {', '.join(core_tech) if core_tech else 'N/A'}

## 평가 기준 (RAG):
{berkus_criteria}
{tech_criteria}

## 검색 결과:
{corpus[:2000]}

## 출력 형식 (간결하게):

### 기술 평가
핵심 기술: [1-2문장]
개발 단계: [프로토타입/베타/상용화]
차별화 요소: [3가지, 각 1줄]
기술 강점: [3가지]
기술 약점: [2가지]
기술 점수: [50-150%]

### 경쟁사 비교
| 항목 | {company} | 경쟁사A | 경쟁사B |
| 기술 수준 | ? | ? | ? |
| 특허 | ? | ? | ? |

### 팀 평가
창업자: CEO [이름/경력 요약], CTO [이름/경력 요약]
팀 규모: [N명 또는 N/A]
핵심 역량: [3가지]
산업 경험: [요약]
팀 점수: [50-150%]

### 종합 리스크
- [리스크 1]
- [리스크 2]

### 종합 요약
[2-3줄로 기술+팀 종합 평가]"""

        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            print(f"⚠️ LLM 요약 실패: {e}")
            return f"{company} 기술 분석: TRL {trl_level}, 특허 {len(patents)}건, 핵심기술 {len(core_tech)}개"

    def _calculate_score(
        self,
        trl_level: Optional[int],
        patents: List[Dict[str, str]],
        core_tech: List[str],
    ) -> float:
        """기술 점수 계산"""
        score = 0.0

        # TRL 점수 (40점)
        if trl_level:
            score += min(trl_level / 9.0 * 40, 40)

        # 특허 점수 (30점)
        patent_score = min(len(patents) * 10, 30)
        score += patent_score

        # 핵심 기술 점수 (30점)
        tech_score = min(len(core_tech) * 10, 30)
        score += tech_score

        return round(score, 2)

    def _load_rag_knowledge(self) -> Dict[str, Any]:
        """RAG에서 평가 기준 로드"""
        if not EvaluationRAG:
            return {}

        try:
            rag = EvaluationRAG()
            return {
                "berkus_criteria": rag.get_berkus_criteria(),
                "tech_evaluation": "TRL 7 이상, 특허 3건 이상, 핵심 기술 명확",
            }
        except Exception as e:
            print(f"⚠️ RAG 로드 실패: {e}")
            return {}


def _demo():
    """데모 실행"""
    from graph.state import create_initial_state

    state = create_initial_state()
    state["profile"] = {"name": "나라스페이스"}

    analyzer = TechAnalyzer()
    result = analyzer.run(state)

    print("\n" + "=" * 80)
    print("📊 최종 결과")
    print("=" * 80)
    print(result["tech_analysis"]["summary"])


if __name__ == "__main__":
    _demo()
