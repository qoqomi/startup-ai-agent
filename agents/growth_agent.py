"""
Agent 1: 성장성 분석 에이전트.

검색 결과와 기본 휴리스틱을 바탕으로 매출, 성장률, 정부 의존도 등을 추정하고
`graph.state.InvestmentState`의 `growth` 섹션을 채운다.
"""

from __future__ import annotations

import os
import re
import requests
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from dotenv import load_dotenv

from graph.state import (
    GrowthOutcome,
    GrowthSignals,
    InvestmentState,
    create_initial_state,
)

# .env 로드
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

try:  # pragma: no cover - 선택적 의존성
    from tools.news_search import search_keyword as default_search_keyword
except Exception:  # pragma: no cover
    default_search_keyword = None  # type: ignore[assignment]

try:  # pragma: no cover - 선택적 의존성
    from rag.evaluation_rag import EvaluationRAG
except Exception:  # pragma: no cover
    EvaluationRAG = None  # type: ignore[assignment]


class SearchProvider(Protocol):
    """외부 검색 도구 인터페이스."""

    def __call__(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]: ...


@dataclass
class GrowthAgentConfig:
    max_results: int = 5
    max_queries: int = 5
    growth_rate_weight: int = 30
    commercial_weight: int = 15
    trl_weight: int = 15
    contracts_weight: int = 20
    fundamentals_weight: int = 20
    min_year: int = 2018
    max_year: int = 2025

    def discovery_queries(self, company: str) -> List[str]:
        return [
            f"{company} 매출",
            f"{company} 성장률",
            f"{company} 정부 과제",
            f"{company} 상업 매출",
            f"{company} 계약",
        ][: self.max_queries]


class GrowthAgent:
    """성장성 분석을 수행하는 에이전트."""

    _shared_knowledge: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        *,
        search: Optional[SearchProvider] = None,
        config: Optional[GrowthAgentConfig] = None,
        knowledge: Optional[Dict[str, Any]] = None,
        dart_api_key: Optional[str] = None,
    ) -> None:
        self.config = config or GrowthAgentConfig()
        self.search = search or self._default_search
        self.knowledge = knowledge or self._load_knowledge()
        self.dart_api_key = dart_api_key or os.getenv("DART_API_KEY")

        default_thresholds = {"우수": 0.10, "양호": 0.05, "경고": 0.01}
        self.growth_thresholds = (self.knowledge or {}).get(
            "growth_thresholds"
        ) or default_thresholds
        self.pmf_signals = (self.knowledge or {}).get("pmf_signals") or [
            "고객이 제품을 찾아옴",
            "언론이 연락함",
            "입소문이 발생함",
            "채용 수요 급증",
            "주문 폭주",
        ]

    def run(self, state: InvestmentState) -> InvestmentState:
        company = state.get("profile", {}).get("name")
        if not company:
            raise ValueError("profile.name is required for growth analysis")

        aggregated = self._collect_corpus(company)
        signals = self._extract_signals(aggregated)
        score, breakdown = self._score(signals)
        summary = self._summarize(company, signals, score, breakdown)

        signals["summary"] = summary
        signals["score_breakdown"] = {k: float(v) for k, v in breakdown.items()}

        new_state = deepcopy(state)
        new_state.setdefault("growth", {})
        new_state["growth"]["score"] = float(score)
        new_state["growth"]["analysis"] = signals  # type: ignore[assignment]

        meta = new_state.setdefault("meta", {})
        meta["current_agent"] = "agent_1_growth"
        meta["stage"] = "growth_analysis"
        history: List[str] = meta.setdefault("history", [])
        history.append("agent_1_growth:completed")

        return new_state

    # ────────────────────────────── 내부 메서드 ──────────────────────────────

    def _collect_corpus(self, company: str) -> str:
        corpus_parts: List[str] = []

        # 1. DART 직원 정보 우선 시도
        if self.dart_api_key:
            dart_info = self._collect_dart_employee_info(company)
            if dart_info:
                corpus_parts.append(dart_info)

        # 2. 기존 검색
        for query in self.config.discovery_queries(company):
            results = self.search(query, max_results=self.config.max_results) or []
            for item in results:
                title = item.get("title") or ""
                snippet = item.get("content") or item.get("snippet") or ""
                corpus_parts.append(title)
                corpus_parts.append(snippet)

        return "\n".join(part for part in corpus_parts if part)

    def _extract_signals(self, corpus: str) -> GrowthSignals:
        revenue_2023 = self._extract_revenue_for_year(corpus, 2023)
        revenue_2024 = self._extract_revenue_for_year(corpus, 2024)
        growth_rate = self._extract_growth_rate(corpus, revenue_2023, revenue_2024)
        government_dependency = self._extract_percentage(
            corpus,
            ["정부 의존도", "정부 매출 비중", "정부 비중"],
        )
        commercial_ratio = self._extract_percentage(
            corpus,
            ["상업 매출 비중", "상업 비중", "민간 매출 비중"],
        )
        trl_level = self._extract_trl_level(corpus)
        contracts = self._extract_contracts(corpus)

        signals: GrowthSignals = {}
        if revenue_2023 is not None:
            signals["revenue_2023"] = revenue_2023
        if revenue_2024 is not None:
            signals["revenue_2024"] = revenue_2024
        if growth_rate is not None:
            signals["growth_rate"] = growth_rate
        if government_dependency is not None:
            signals["government_dependency"] = government_dependency
        if commercial_ratio is not None:
            signals["commercial_ratio"] = commercial_ratio
        if trl_level is not None:
            signals["trl_level"] = trl_level
        if contracts:
            signals["contracts"] = contracts

        return signals

    def _score(self, signals: GrowthSignals) -> tuple[float, Dict[str, float]]:
        breakdown: Dict[str, float] = {}

        growth_rate = signals.get("growth_rate")
        commercial_ratio = signals.get("commercial_ratio")
        trl_level = signals.get("trl_level")
        contracts = signals.get("contracts", [])
        fundamentals = 0.0

        if signals.get("revenue_2023") and signals.get("revenue_2024"):
            fundamentals += self.config.fundamentals_weight * 0.5
        if (
            commercial_ratio is not None
            or signals.get("government_dependency") is not None
        ):
            fundamentals += self.config.fundamentals_weight * 0.25
        if contracts:
            fundamentals += self.config.fundamentals_weight * 0.25

        growth_rate_score = self._score_growth_rate(growth_rate)
        commercial_score = (
            min(max(commercial_ratio, 0.0), 1.0) * self.config.commercial_weight
            if commercial_ratio is not None
            else 0.0
        )
        trl_score = (
            min(max(float(trl_level), 0.0), 9.0) / 9.0 * self.config.trl_weight
            if trl_level is not None
            else 0.0
        )
        contracts_score = min(len(contracts) * 4.0, float(self.config.contracts_weight))

        breakdown["growth_rate_score"] = round(growth_rate_score, 2)
        breakdown["commercial_score"] = round(commercial_score, 2)
        breakdown["trl_score"] = round(trl_score, 2)
        breakdown["contracts_score"] = round(contracts_score, 2)
        breakdown["fundamentals_score"] = round(fundamentals, 2)

        total = sum(breakdown.values())
        return round(total, 2), breakdown

    def _summarize(
        self,
        company: str,
        signals: GrowthSignals,
        score: float,
        breakdown: Dict[str, float],
    ) -> str:
        lines = [f"{company} 성장 분석 요약 (총점 {score}/100)"]
        if "revenue_2023" in signals and "revenue_2024" in signals:
            lines.append(
                f"- 매출: 2023년 {signals['revenue_2023']}억원 → 2024년 {signals['revenue_2024']}억원"
            )
        if "growth_rate" in signals:
            rate = signals["growth_rate"]
            label = self._label_growth_rate(rate)
            lines.append(f"- 매출 성장률: {rate*100:.1f}% ({label})")
        if "commercial_ratio" in signals:
            lines.append(f"- 상업 매출 비중: {signals['commercial_ratio']*100:.1f}%")
        if "government_dependency" in signals:
            lines.append(f"- 정부 의존도: {signals['government_dependency']*100:.1f}%")
        if "trl_level" in signals:
            lines.append(f"- TRL: {signals['trl_level']}")
        if signals.get("contracts"):
            bullet = "; ".join(signals["contracts"][:3])
            lines.append(f"- 주요 계약: {bullet}")
        if self.pmf_signals:
            lines.append("- PMF 신호 체크 포인트: " + ", ".join(self.pmf_signals[:3]))

        lines.append(
            "- 세부 점수: "
            + ", ".join(
                f"{k.replace('_score', '')} {v:.1f}" for k, v in breakdown.items()
            )
        )
        return "\n".join(lines)

    # ────────────────────────────── 추출 유틸 ──────────────────────────────

    def _extract_revenue_for_year(self, corpus: str, year: int) -> Optional[float]:
        year_pattern = re.compile(
            rf"{year}[^\d]{{0,12}}(?:매출|매출액|Revenue|수익)[^\d]{{0,8}}([\d,.]+)\s*(조|억원|억|억 원|억엔|백만|천만|달러|USD|KRW|b|bn|m|million)",
            re.IGNORECASE,
        )
        for match in year_pattern.finditer(corpus):
            raw_value = match.group(1)
            unit = match.group(2)
            value = self._normalize_numeric(raw_value)
            if value is None:
                continue
            converted = self._convert_currency_to_krw_100m(value, unit)
            if converted is not None:
                return converted
        return None

    def _extract_growth_rate(
        self,
        corpus: str,
        revenue_2023: Optional[float],
        revenue_2024: Optional[float],
    ) -> Optional[float]:
        pattern = re.compile(
            r"(성장률|성장|yo?y)[^\d]{0,6}(\d{1,3}(?:\.\d+)?)\s*%",
            re.IGNORECASE,
        )
        match = pattern.search(corpus)
        if match:
            return float(match.group(2)) / 100.0

        if revenue_2023 and revenue_2024 and revenue_2023 > 0:
            return (revenue_2024 - revenue_2023) / revenue_2023
        return None

    def _extract_percentage(self, corpus: str, keywords: List[str]) -> Optional[float]:
        for keyword in keywords:
            pattern = re.compile(
                rf"{keyword}[^\d]{{0,6}}(\d{{1,3}}(?:\.\d+)?)\s*%",
                re.IGNORECASE,
            )
            match = pattern.search(corpus)
            if match:
                return float(match.group(1)) / 100.0
        return None

    def _extract_trl_level(self, corpus: str) -> Optional[int]:
        match = re.search(r"TRL\s*[-:]?\s*(\d)", corpus, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _extract_contracts(self, corpus: str) -> List[str]:
        lines = [line.strip() for line in corpus.splitlines() if line.strip()]
        keywords = ("계약", "과제", "투자", "프로젝트", "MOU", "공급")
        contracts: List[str] = []
        for line in lines:
            if any(keyword in line for keyword in keywords):
                cleaned = re.sub(r"\s+", " ", line)
                contracts.append(cleaned)
        return contracts[:5]

    # ────────────────────────────── 변환 유틸 ──────────────────────────────

    @staticmethod
    def _normalize_numeric(value: str) -> Optional[float]:
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _convert_currency_to_krw_100m(value: float, unit: str) -> Optional[float]:
        unit = unit.lower()
        if unit in {"억", "억원", "억 원"}:
            return value
        if unit == "조":
            return value * 10000
        if unit in {"천만"}:
            return value / 10
        if unit in {"백만", "million", "m"}:
            return value * 0.1
        if unit in {"달러", "usd"}:
            return value * 0.013  # rough USD->KRW (백만달러≈13억) 변환
        if unit in {"b", "bn"}:
            return value * 133.0  # 1B USD ≈ 13,300억원 → 13300/100
        if unit in {"krw"}:
            return value / 100000000
        return None

    # ────────────────────────────── 기본 검색 ──────────────────────────────

    def _default_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if default_search_keyword is None:
            print(f"검색 불가: tools.news_search.search_keyword 미제공 ({query})")
            return []
        try:
            results = default_search_keyword(query)
            return results[:max_results]
        except Exception as exc:  # pragma: no cover
            print(f"검색 실패: {query} ({exc})")
            return []

    # ────────────────────────────── RAG 통합 ──────────────────────────────

    def _load_knowledge(self) -> Dict[str, Any]:
        if GrowthAgent._shared_knowledge is not None:
            return GrowthAgent._shared_knowledge

        knowledge: Dict[str, Any] = {}

        if EvaluationRAG is None:
            GrowthAgent._shared_knowledge = knowledge
            return knowledge

        try:
            rag = EvaluationRAG()
        except Exception as exc:  # pragma: no cover
            print(f"RAG 초기화 실패: {exc}")
            GrowthAgent._shared_knowledge = knowledge
            return knowledge

        try:
            knowledge["growth_thresholds"] = rag.get_growth_thresholds()
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] RAG 성장 기준 조회 실패: {exc}")
        try:
            knowledge["pmf_signals"] = rag.get_pmf_signals()
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] RAG PMF 신호 조회 실패: {exc}")
        try:
            knowledge["berkus"] = rag.get_berkus_criteria()
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] RAG Berkus 조회 실패: {exc}")
        try:
            knowledge["scorecard"] = rag.get_scorecard_weights()
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] RAG Scorecard 조회 실패: {exc}")

        GrowthAgent._shared_knowledge = knowledge
        return knowledge

    def _score_growth_rate(self, growth_rate: Optional[float]) -> float:
        if growth_rate is None:
            return 0.0

        excellent = self.growth_thresholds.get("우수", 0.10)
        if excellent <= 0:
            excellent = 0.10

        normalized = min(max(growth_rate, 0.0) / excellent, 1.0)
        return normalized * self.config.growth_rate_weight

    def _label_growth_rate(self, growth_rate: Optional[float]) -> str:
        if growth_rate is None:
            return "데이터 없음"

        excellent = self.growth_thresholds.get("우수")
        good = self.growth_thresholds.get("양호")
        warning = self.growth_thresholds.get("경고")

        if excellent and growth_rate >= excellent:
            return "우수"
        if good and growth_rate >= good:
            return "양호"
        if warning and growth_rate >= warning:
            return "경고"
        return "심각"

    # ────────────────────────────── DART API 통합 ──────────────────────────────

    def _get_corp_code(self, company_name: str) -> Optional[str]:
        """기업명으로 DART 고유번호 조회"""
        if not self.dart_api_key:
            return None

        # DART corpCode는 별도 XML 다운로드 필요
        # 여기서는 하드코딩된 매핑 사용 (실제로는 corpCode.xml 파싱 필요)
        corp_code_map = {
            "나라스페이스": None,  # 비상장 스타트업은 없을 가능성
            "나라스페이스테크놀로지": None,
            # 실제 사용 시 corpCode.xml에서 추출한 매핑 사용
        }

        return corp_code_map.get(company_name)

    def _collect_dart_employee_info(self, company: str) -> Optional[str]:
        """DART에서 직원 현황 조회 및 텍스트 생성"""
        if not self.dart_api_key:
            return None

        corp_code = self._get_corp_code(company)
        if not corp_code:
            print(f"[DART] {company} 고유번호 없음 - 검색으로 fallback")
            return None

        # 2024년 사업보고서 조회
        url = "https://opendart.fss.or.kr/api/empSttus.json"
        params = {
            "crtfc_key": self.dart_api_key,
            "corp_code": corp_code,
            "bsns_year": "2024",
            "reprt_code": "11011",  # 사업보고서
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "000":
                print(f"[DART] API 오류: {data.get('message')}")
                return None

            return self._parse_employee_data(company, data)

        except requests.exceptions.RequestException as e:
            print(f"[DART] 직원 현황 조회 실패: {e}")
            return None
        except Exception as e:
            print(f"[DART] 파싱 실패: {e}")
            return None

    def _parse_employee_data(self, company: str, data: dict) -> str:
        """DART 직원 현황 데이터를 텍스트로 변환"""
        items = data.get("list", [])
        if not items:
            return ""

        corpus_parts = []

        # 직원 수 집계
        regular_total = 0
        contract_total = 0
        rd_count = 0
        avg_service_years = None
        avg_salary = None

        for item in items:
            fo_bbm = item.get("fo_bbm", "")  # 사업부문
            rgllbr_co = item.get("rgllbr_co", "0")  # 정규직 수
            cnttk_co = item.get("cnttk_co", "0")  # 계약직 수
            sm = item.get("sm", "0")  # 합계
            avrg_cnwk_sdytrn = item.get("avrg_cnwk_sdytrn", "")  # 평균 근속연수
            jan_salary_am = item.get("jan_salary_am", "")  # 1인평균 급여액

            # 숫자 변환 (쉼표 제거)
            def to_int(s):
                try:
                    return int(str(s).replace(",", "")) if s else 0
                except:
                    return 0

            def to_float(s):
                try:
                    return float(str(s).replace(",", "")) if s else None
                except:
                    return None

            # 사업부문별 집계
            if "연구" in fo_bbm or "R&D" in fo_bbm.upper() or "개발" in fo_bbm:
                rd_count += to_int(sm)
            elif "전체" in fo_bbm or "합계" in fo_bbm or "계" in fo_bbm:
                # 전체 합계 행
                regular_total = to_int(rgllbr_co)
                contract_total = to_int(cnttk_co)
                avg_service_years = to_float(avrg_cnwk_sdytrn)
                avg_salary = to_float(jan_salary_am)

        # 전체가 없으면 수동 합산
        if regular_total == 0 and contract_total == 0:
            for item in items:
                regular_total += to_int(item.get("rgllbr_co", "0"))
                contract_total += to_int(item.get("cnttk_co", "0"))

        total_count = regular_total + contract_total

        # 텍스트 생성
        if total_count > 0:
            corpus_parts.append(f"[DART] {company} 직원 수: {total_count}명")

            if regular_total > 0:
                corpus_parts.append(f"정규직 {regular_total}명")

            if contract_total > 0:
                corpus_parts.append(f"계약직 {contract_total}명")

            if rd_count > 0:
                rd_ratio = rd_count / total_count if total_count > 0 else 0
                corpus_parts.append(
                    f"연구개발 인력 {rd_count}명 (비중 {rd_ratio*100:.1f}%)"
                )

            if avg_service_years:
                corpus_parts.append(f"평균 근속연수: {avg_service_years:.1f}년")

            if avg_salary:
                corpus_parts.append(f"1인 평균 급여: {int(avg_salary/10000)}만원")

        # 전년도 데이터 조회 (성장률 계산용)
        prev_year_data = self._get_employee_count_for_year(
            self._get_corp_code(company), "2023"
        )

        if prev_year_data and total_count > 0:
            growth = (total_count - prev_year_data) / prev_year_data
            corpus_parts.append(
                f"직원 증가율: 전년 대비 {growth*100:.1f}% ({prev_year_data}명 → {total_count}명)"
            )

        if total_count > 0:
            print(
                f"[DART] ✓ 직원 정보: {total_count}명 (정규직 {regular_total}, 계약직 {contract_total})"
            )

        return "\n".join(corpus_parts)

    def _get_employee_count_for_year(
        self, corp_code: Optional[str], year: str
    ) -> Optional[int]:
        """특정 연도의 직원 수 조회"""
        if not self.dart_api_key or not corp_code:
            return None

        url = "https://opendart.fss.or.kr/api/empSttus.json"
        params = {
            "crtfc_key": self.dart_api_key,
            "corp_code": corp_code,
            "bsns_year": year,
            "reprt_code": "11011",
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data.get("status") != "000":
                return None

            regular_total = 0
            contract_total = 0

            for item in data.get("list", []):
                fo_bbm = item.get("fo_bbm", "")
                rgllbr_co = str(item.get("rgllbr_co", "0")).replace(",", "")
                cnttk_co = str(item.get("cnttk_co", "0")).replace(",", "")

                if "전체" in fo_bbm or "합계" in fo_bbm or "계" in fo_bbm:
                    try:
                        regular_total = int(rgllbr_co) if rgllbr_co.isdigit() else 0
                        contract_total = int(cnttk_co) if cnttk_co.isdigit() else 0
                    except:
                        pass
                    break

            # 전체가 없으면 수동 합산
            if regular_total == 0 and contract_total == 0:
                for item in data.get("list", []):
                    try:
                        rgllbr = str(item.get("rgllbr_co", "0")).replace(",", "")
                        cnttk = str(item.get("cnttk_co", "0")).replace(",", "")
                        regular_total += int(rgllbr) if rgllbr.isdigit() else 0
                        contract_total += int(cnttk) if cnttk.isdigit() else 0
                    except:
                        pass

            total = regular_total + contract_total
            return total if total > 0 else None

        except:
            return None


# ────────────────────────────── 실행 예시 ──────────────────────────────


def _demo() -> None:
    state = create_initial_state()
    state.setdefault("profile", {})["name"] = "나라스페이스"
    agent = GrowthAgent()
    updated = agent.run(state)
    print(updated["growth"])


if __name__ == "__main__":  # pragma: no cover
    _demo()
