"""
Agent: 시장 분석 (Market Analyzer)

후보 기업의 시장성을 분석합니다.
- TAM/SAM/SOM (벤치마크 데이터 + 검색)
- 시장 성장률
- PMF (Product-Market Fit) 신호
- 경쟁 환경
"""

from __future__ import annotations

import os
import re
import requests
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
class MarketAnalyzerConfig:
    """시장 분석 설정"""

    max_results: int = 3  # Rate limit 방지
    search_queries_template: List[str] = None

    def __post_init__(self):
        if self.search_queries_template is None:
            self.search_queries_template = [
                "{company} 시장 규모",
                "{company} TAM SAM SOM",
                "{company} 시장 성장률",
                "{company} PMF product market fit",
                "우주산업 시장 전망 2024",
                "위성 산업 시장 규모",
            ]


class MarketAnalyzer:
    """시장 분석 에이전트 (벤치마크 데이터 통합)"""

    def __init__(
        self,
        config: Optional[MarketAnalyzerConfig] = None,
        tavily_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        ecos_api_key: Optional[str] = None,
        use_crawler: bool = True,
    ):
        self.config = config or MarketAnalyzerConfig()
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.ecos_api_key = ecos_api_key or os.getenv("ECOS_API_KEY")
        self.use_crawler = use_crawler

        # 한국은행 API 설정
        self.ecos_base_url = "https://ecos.bok.or.kr/api"

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

        # 우주산업 벤치마크 데이터 (market.py에서 가져옴)
        self.market_benchmarks = {
            "global_market_2024": 371.0,  # B USD
            "kr_market_2024": 15.59,  # B USD
            "kr_market_2024_krw": 21700.0,  # B KRW
            "kr_cagr": 6.10,  # %
            "global_market_2040": 1000.0,  # B USD
            "satellite_share": 73.0,  # %
        }

        # 섹터별 데이터
        self.sector_benchmarks = {
            "위성": {
                "market_share": 73.0,
                "growth": "high",
                "kr_companies": 62,
                "global_tam": 271.0,  # 371 * 0.73
            },
            "발사체": {
                "market_share": 15.0,
                "growth": "high",
                "kr_companies": 84,
                "global_tam": 55.65,
            },
            "지상장비": {
                "market_share": 8.0,
                "growth": "medium",
                "kr_companies": 87,
                "global_tam": 29.68,
            },
            "우주이용": {
                "market_share": 4.0,
                "growth": "high",
                "kr_companies": 165,
                "global_tam": 14.84,
            },
        }

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """시장 분석 실행 (벤치마크 + 검색)"""
        company = state.get("profile", {}).get("name")
        if not company:
            candidates = state.get("candidates", [])
            if candidates:
                company = candidates[0].get("name")

        if not company:
            raise ValueError("기업명이 필요합니다")

        print(f"\n{'='*80}")
        print(f"📊 [시장 분석] {company}")
        print(f"{'='*80}")

        # 섹터 판별 (기업명이나 설명에서 추출)
        sector = self._detect_sector(state)
        print(f"   감지된 섹터: {sector}")

        # 1. 벤치마크 데이터 로드
        benchmark_data = self._get_benchmark_data(sector)

        # 2. 한국은행 경제 지표 조회 (실시간 데이터)
        print(f"\n📊 경제 지표 수집 중...")
        economic_indicators = self._get_economic_indicators()

        # 3. 검색으로 추가 데이터 수집
        corpus = self._collect_corpus(company)

        # 4. TAM/SAM/SOM 추출 (벤치마크 + 검색)
        tam_sam_som = self._extract_market_size(corpus, benchmark_data)

        # 5. 시장 성장률 계산 (우선순위: 산업생산지수 > 벤치마크 > 검색)
        actual_growth = self._calculate_actual_growth_rate(
            economic_indicators.get("production_index", [])
        )
        if actual_growth:
            growth_rate = actual_growth
            print(
                f"   ✅ 실제 성장률 반영: {actual_growth*100:.2f}% (산업생산지수 기반)"
            )
        else:
            growth_rate = benchmark_data.get(
                "growth_rate", self._extract_growth_rate(corpus)
            )
            print(
                f"   📌 벤치마크 성장률 사용: {growth_rate*100 if growth_rate else 'N/A'}%"
            )

        # 6. PMF 신호 추출
        pmf_signals = self._extract_pmf_signals(corpus)

        # 7. LLM 종합 분석
        summary = self._generate_summary(
            company, tam_sam_som, growth_rate, pmf_signals, corpus, sector
        )

        # 8. 점수 계산
        score = self._calculate_score(tam_sam_som, growth_rate, pmf_signals)

        # 결과 출력
        print(f"\n✅ 시장 분석 완료")
        if tam_sam_som.get("TAM"):
            print(f"   TAM: ${tam_sam_som['TAM']}B")
        if tam_sam_som.get("SAM"):
            print(f"   SAM: ${tam_sam_som['SAM']}B")
        if tam_sam_som.get("SOM"):
            print(f"   SOM: ${tam_sam_som['SOM']}B")
        if growth_rate:
            print(f"   성장률: {growth_rate*100:.1f}%")
        print(f"   PMF 신호: {len(pmf_signals)}개")
        print(f"   점수: {score}/100")

        # State 업데이트 (InvestmentState의 'market' 키에 맞춤)
        result = {
            "market": {
                "tam_sam_som": tam_sam_som,
                "growth_rate": growth_rate,
                "pmf_signals": pmf_signals,
                "summary": summary,
                "score": score,
                "sector": sector,
            }
        }

        return result

    def _detect_sector(self, state: Dict[str, Any]) -> str:
        """기업 섹터 감지"""
        description = state.get("profile", {}).get("business_description", "")
        industry = state.get("profile", {}).get("industry", "")

        text = f"{description} {industry}".lower()

        # 키워드 매칭
        if any(keyword in text for keyword in ["위성", "satellite", "큐브위성"]):
            return "위성"
        elif any(keyword in text for keyword in ["발사체", "로켓", "launcher"]):
            return "발사체"
        elif any(keyword in text for keyword in ["지상장비", "안테나", "ground"]):
            return "지상장비"
        elif any(
            keyword in text for keyword in ["우주이용", "우주서비스", "space service"]
        ):
            return "우주이용"

        # 기본값: 위성 (가장 큰 시장)
        return "위성"

    def _get_benchmark_data(self, sector: str) -> Dict[str, Any]:
        """섹터별 벤치마크 데이터 반환"""
        sector_info = self.sector_benchmarks.get(sector, self.sector_benchmarks["위성"])

        return {
            "global_tam": sector_info["global_tam"],
            "growth_rate": self.market_benchmarks["kr_cagr"] / 100,  # % to decimal
            "market_share": sector_info["market_share"],
            "kr_companies": sector_info["kr_companies"],
        }

    def _collect_corpus(self, company: str) -> str:
        """검색으로 코퍼스 수집 (크롤러 우선)"""
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

    def _extract_market_size(
        self, corpus: str, benchmark_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """TAM/SAM/SOM 추출 (벤치마크 데이터 활용)"""
        result = {}

        # TAM 추출
        tam_pattern = re.compile(
            r"TAM[^\d]{0,15}(\d+(?:\.\d+)?)\s*(billion|B|조|trillion)",
            re.IGNORECASE,
        )
        tam_match = tam_pattern.search(corpus)
        if tam_match:
            value = float(tam_match.group(1))
            unit = tam_match.group(2).lower()
            if "trillion" in unit:
                value *= 1000
            elif "조" in unit:
                value *= 0.75  # 1조원 ≈ 0.75B USD
            result["TAM"] = round(value, 2)
        elif benchmark_data and "global_tam" in benchmark_data:
            # 벤치마크 데이터에서 TAM 사용
            result["TAM"] = benchmark_data["global_tam"]

        # SAM 추출
        sam_pattern = re.compile(
            r"SAM[^\d]{0,15}(\d+(?:\.\d+)?)\s*(billion|B|조)", re.IGNORECASE
        )
        sam_match = sam_pattern.search(corpus)
        if sam_match:
            value = float(sam_match.group(1))
            unit = sam_match.group(2).lower()
            if "조" in unit:
                value *= 0.75
            result["SAM"] = round(value, 2)
        elif benchmark_data and "kr_market_usd" in benchmark_data and "TAM" in result:
            # 한국 시장을 SAM으로 사용 (TAM의 약 4.2%)
            result["SAM"] = benchmark_data["kr_market_usd"]

        # SOM 추출
        som_pattern = re.compile(
            r"SOM[^\d]{0,15}(\d+(?:\.\d+)?)\s*(billion|B|조|million)",
            re.IGNORECASE,
        )
        som_match = som_pattern.search(corpus)
        if som_match:
            value = float(som_match.group(1))
            unit = som_match.group(2).lower()
            if "million" in unit:
                value /= 1000
            elif "조" in unit:
                value *= 0.75
            result["SOM"] = round(value, 2)
        elif "SAM" in result:
            # SAM의 1~5%를 SOM으로 추정 (스타트업 초기 단계 가정)
            result["SOM"] = round(result["SAM"] * 0.02, 2)

        # LLM으로 추정 (벤치마크로도 채워지지 않은 경우)
        if not result and self.llm:
            prompt = f"""다음 텍스트에서 시장 규모(TAM/SAM/SOM)를 추정하세요.

텍스트:
{corpus[:2000]}

참고: 글로벌 우주산업 시장은 약 $371B, 한국 시장은 약 $16.3B입니다.

TAM (Total Addressable Market): 전체 시장
SAM (Serviceable Addressable Market): 접근 가능 시장
SOM (Serviceable Obtainable Market): 획득 가능 시장

다음 형식으로 출력하세요 (알 수 없으면 "N/A"):
TAM: $XXB
SAM: $XXB
SOM: $XXB"""

            try:
                response = self.llm.invoke(prompt)
                content = response.content.strip()

                for line in content.split("\n"):
                    if "TAM" in line:
                        value = self._parse_money_value(line)
                        if value:
                            result["TAM"] = value
                    elif "SAM" in line:
                        value = self._parse_money_value(line)
                        if value:
                            result["SAM"] = value
                    elif "SOM" in line:
                        value = self._parse_money_value(line)
                        if value:
                            result["SOM"] = value
            except:
                pass

        return result

    def _parse_money_value(self, text: str) -> Optional[float]:
        """텍스트에서 금액 파싱"""
        pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(B|billion|조)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            if "조" in unit:
                value *= 0.75
            return round(value, 2)
        return None

    def _extract_growth_rate(self, corpus: str) -> Optional[float]:
        """시장 성장률 추출"""
        # CAGR 패턴
        pattern = re.compile(
            r"(CAGR|성장률|growth rate)[^\d]{0,10}(\d+(?:\.\d+)?)\s*%",
            re.IGNORECASE,
        )
        match = pattern.search(corpus)
        if match:
            return float(match.group(2)) / 100.0

        # LLM으로 추정
        if self.llm and corpus:
            prompt = f"""다음 텍스트에서 시장 성장률(CAGR)을 추출하세요.

텍스트:
{corpus[:1500]}

성장률을 퍼센트로 출력하세요 (예: 15.5). 알 수 없으면 "N/A"를 출력하세요."""

            try:
                response = self.llm.invoke(prompt)
                content = response.content.strip()

                match = re.search(r"(\d+(?:\.\d+)?)", content)
                if match:
                    return float(match.group(1)) / 100.0
            except:
                pass

        return None

    def _extract_pmf_signals(self, corpus: str) -> List[str]:
        """PMF 신호 추출"""
        signals = []

        # RAG에서 PMF 신호 가져오기
        rag_pmf_signals = self.rag_knowledge.get("pmf_signals", [])

        # 코퍼스에서 PMF 신호 찾기
        for signal in rag_pmf_signals:
            if signal in corpus or self._is_similar_signal(signal, corpus):
                signals.append(signal)

        # 추가 키워드 검색
        pmf_keywords = [
            "고객 재구매",
            "입소문",
            "언론 보도",
            "수주",
            "계약",
            "파트너십",
            "투자 유치",
            "매출 증가",
        ]

        for keyword in pmf_keywords:
            if keyword in corpus and keyword not in signals:
                signals.append(keyword)

        return signals[:5]  # 최대 5개

    def _is_similar_signal(self, signal: str, corpus: str) -> bool:
        """유사한 PMF 신호 찾기"""
        keywords = signal.split()
        return any(keyword in corpus for keyword in keywords if len(keyword) > 2)

    def _generate_summary(
        self,
        company: str,
        tam_sam_som: Dict[str, float],
        growth_rate: Optional[float],
        pmf_signals: List[str],
        corpus: str,
        sector: str = "위성",
    ) -> str:
        """종합 요약 생성"""
        if not self.llm:
            return f"{company} 시장 분석 완료"

        prompt = f"""당신은 우주산업 시장 분석 전문가입니다. {company}의 시장성을 평가하세요.

## 기업 섹터: {sector}

## 수집된 정보:
- TAM/SAM/SOM: {tam_sam_som}
- 성장률: {growth_rate*100 if growth_rate else 'N/A'}%
- PMF 신호: {', '.join(pmf_signals) if pmf_signals else 'N/A'}

## 추가 정보:
{corpus[:1500]}

## 출력 형식:
**시장 규모**: [평가]
**성장 잠재력**: [평가]
**PMF 검증**: [평가]
**종합**: [2-3줄 요약]"""

        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            print(f"⚠️ LLM 요약 실패: {e}")
            return f"{company} 시장 분석: TAM ${tam_sam_som.get('TAM', 'N/A')}B, 성장률 {growth_rate*100 if growth_rate else 'N/A'}%"

    def _calculate_score(
        self,
        tam_sam_som: Dict[str, float],
        growth_rate: Optional[float],
        pmf_signals: List[str],
    ) -> float:
        """시장 점수 계산"""
        score = 0.0

        # TAM 점수 (30점)
        tam = tam_sam_som.get("TAM", 0)
        if tam >= 100:
            score += 30
        elif tam >= 50:
            score += 25
        elif tam >= 10:
            score += 20
        elif tam > 0:
            score += 15

        # 성장률 점수 (40점)
        if growth_rate:
            if growth_rate >= 0.20:  # 20% 이상
                score += 40
            elif growth_rate >= 0.15:  # 15% 이상
                score += 35
            elif growth_rate >= 0.10:  # 10% 이상
                score += 30
            elif growth_rate > 0:
                score += 20

        # PMF 신호 점수 (30점)
        pmf_score = min(len(pmf_signals) * 10, 30)
        score += pmf_score

        return round(score, 2)

    def _load_rag_knowledge(self) -> Dict[str, Any]:
        """RAG에서 평가 기준 로드"""
        if not EvaluationRAG:
            return {"pmf_signals": []}

        try:
            rag = EvaluationRAG()
            pmf_signals = rag.get_pmf_signals()
            return {"pmf_signals": pmf_signals if pmf_signals else []}
        except Exception as e:
            print(f"⚠️ RAG 로드 실패: {e}")
            return {"pmf_signals": []}

    def _get_ecos_data(
        self, stat_code: str, start_period: str, end_period: str
    ) -> Dict[str, Any]:
        """
        한국은행 ECOS API 데이터 조회

        Args:
            stat_code: 통계표 코드 (예: 200Y001=GDP, 901Y009=산업생산지수)
            start_period: 시작 기간 (연간: YYYY, 월간: YYYYMM)
            end_period: 종료 기간

        Returns:
            API 응답 데이터
        """
        if not self.ecos_api_key:
            return {"error": "ECOS API 키가 설정되지 않음"}

        # 기간 형식에 따라 주기 결정
        cycle = "A" if len(start_period) == 4 else "M"

        url = f"{self.ecos_base_url}/StatisticSearch/{self.ecos_api_key}/json/kr/1/100/{stat_code}/{cycle}/{start_period}/{end_period}/"

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()

                # 에러 체크
                if "RESULT" in data:
                    result = data["RESULT"]
                    if result.get("CODE") not in ["INFO-000", "INFO-200"]:
                        return {"error": f"API 오류: {result.get('MESSAGE')}"}

                return data
            else:
                return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def _get_economic_indicators(self) -> Dict[str, Any]:
        """한국은행 API로 경제 지표 조회"""
        if not self.ecos_api_key:
            return {}

        indicators = {}

        # GDP 성장률 조회
        try:
            gdp_data = self._get_ecos_data("200Y001", "2023", "2024")
            if "StatisticSearch" in gdp_data and "row" in gdp_data["StatisticSearch"]:
                rows = gdp_data["StatisticSearch"]["row"]
                if len(rows) >= 2:
                    prev_gdp = float(rows[-2]["DATA_VALUE"])
                    curr_gdp = float(rows[-1]["DATA_VALUE"])
                    indicators["gdp_growth"] = ((curr_gdp - prev_gdp) / prev_gdp) * 100
                    print(f"   📈 GDP 성장률: {indicators['gdp_growth']:.2f}%")
        except Exception as e:
            print(f"   ⚠️ GDP 조회 실패: {e}")

        # 산업생산지수 조회 (최근 12개월)
        try:
            prod_data = self._get_ecos_data("901Y009", "202301", "202412")
            if "StatisticSearch" in prod_data and "row" in prod_data["StatisticSearch"]:
                rows = prod_data["StatisticSearch"]["row"]
                indicators["production_index"] = rows
                print(f"   📊 산업생산지수: {len(rows)}개월 데이터 수집")
        except Exception as e:
            print(f"   ⚠️ 산업생산지수 조회 실패: {e}")

        return indicators

    def _calculate_actual_growth_rate(self, production_index: list) -> Optional[float]:
        """산업생산지수로 실제 성장률 계산"""
        if not production_index or len(production_index) < 12:
            return None

        try:
            # 최근 12개월과 이전 12개월 비교
            recent_12 = production_index[-12:]
            prev_12 = production_index[-24:-12] if len(production_index) >= 24 else None

            if not prev_12:
                return None

            recent_avg = sum(float(x["DATA_VALUE"]) for x in recent_12) / 12
            prev_avg = sum(float(x["DATA_VALUE"]) for x in prev_12) / 12

            growth_rate = ((recent_avg - prev_avg) / prev_avg) * 100
            return growth_rate / 100.0  # 비율로 변환
        except:
            return None


def _demo():
    """데모 실행"""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from graph.state import create_initial_state

    state = create_initial_state()
    state["profile"] = {"name": "나라스페이스"}

    analyzer = MarketAnalyzer()
    result = analyzer.run(state)

    print("\n" + "=" * 80)
    print("📊 최종 결과")
    print("=" * 80)
    print(result["market_analysis"]["summary"])


if __name__ == "__main__":
    _demo()
