"""
Agent 1: 성장성 분석 에이전트.

검색 결과와 기본 휴리스틱을 바탕으로 매출, 성장률, 정부 의존도 등을 추정하고
`graph.state.InvestmentState`의 `growth` 섹션을 채운다.
"""

from __future__ import annotations

import math
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from graph.state import GrowthOutcome, GrowthSignals, InvestmentState, create_initial_state

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

    def __call__(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        ...


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
    ) -> None:
        self.config = config or GrowthAgentConfig()
        self.search = search or self._default_search
        self.knowledge = knowledge or self._load_knowledge()

        default_thresholds = {"우수": 0.10, "양호": 0.05, "경고": 0.01}
        self.growth_thresholds = (
            (self.knowledge or {}).get("growth_thresholds") or default_thresholds
        )
        self.pmf_signals = (
            (self.knowledge or {}).get("pmf_signals")
            or [
                "고객이 제품을 찾아옴",
                "언론이 연락함",
                "입소문이 발생함",
                "채용 수요 급증",
                "주문 폭주",
            ]
        )

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
        if commercial_ratio is not None or signals.get("government_dependency") is not None:
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
            lines.append(
                "- PMF 신호 체크 포인트: "
                + ", ".join(self.pmf_signals[:3])
            )

        lines.append(
            "- 세부 점수: "
            + ", ".join(f"{k.replace('_score', '')} {v:.1f}" for k, v in breakdown.items())
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


# ────────────────────────────── 실행 예시 ──────────────────────────────

def _demo() -> None:
    state = create_initial_state()
    state.setdefault("profile", {})["name"] = "나라스페이스"
    agent = GrowthAgent()
    updated = agent.run(state)
    print(updated["growth"])


if __name__ == "__main__":  # pragma: no cover
    _demo()
