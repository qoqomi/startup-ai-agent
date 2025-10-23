"""
한국 우주산업 스타트업 투자 평가 시스템
상태(State) 정의 모듈
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict


# ═══════════════════════════════════════════════════════════════════════════
# Agent 0 ─ 기업 탐색 및 기본 정보
# ═══════════════════════════════════════════════════════════════════════════


class CandidateProfile(TypedDict, total=False):
    """기업 기본 정보"""

    name: str
    tagline: str
    summary: str
    founded_year: int
    ceo_name: str
    headquarters: str
    employee_count: int
    website: str
    business_description: str


class SpaceOperations(TypedDict, total=False):
    """우주산업 특화 정보"""

    satellites_deployed: int
    satellites_planned: int
    satellite_names: List[str]
    payload_type: str
    orbit_type: str
    launch_status: str
    ground_stations: int
    main_technology: List[str]
    industry_sector: str


class FundingSnapshot(TypedDict, total=False):
    """투자 및 파트너십"""

    stage: str
    total_funding_krw: float
    last_funding_date: str
    major_investors: List[str]
    partners: List[str]
    products: List[str]
    customers: List[str]


# ═══════════════════════════════════════════════════════════════════════════
# Agent 1 ─ 성장성 분석
# ═══════════════════════════════════════════════════════════════════════════


class GrowthSignals(TypedDict, total=False):
    revenue_2023: float
    revenue_2024: float
    growth_rate: float
    government_dependency: float
    commercial_ratio: float
    trl_level: int
    contracts: List[str]
    score_breakdown: Dict[str, float]
    summary: str


class GrowthOutcome(TypedDict, total=False):
    score: float
    analysis: GrowthSignals


# ═══════════════════════════════════════════════════════════════════════════
# Agent 2 ─ 시장·경쟁 분석
# ═══════════════════════════════════════════════════════════════════════════


class MarketInsights(TypedDict, total=False):
    global_tam_usd: float
    korea_market_krw: float
    market_growth_rate: float
    pmf_signals: Dict[str, Any]
    summary: str


class MarketOutcome(TypedDict, total=False):
    score: float
    analysis: MarketInsights


class CompetitorProfile(TypedDict, total=False):
    name: str
    founded_year: int
    employees: int
    funding_krw: float
    satellites: int
    technology: str
    strengths: List[str]
    weaknesses: List[str]


class ComparisonSummary(TypedDict, total=False):
    our_strengths: List[str]
    our_weaknesses: List[str]
    competitor_strengths: List[str]
    competitor_weaknesses: List[str]
    narrative: str


# ═══════════════════════════════════════════════════════════════════════════
# Agent 3 ─ 생존성 분석
# ═══════════════════════════════════════════════════════════════════════════


class SurvivalMetrics(TypedDict, total=False):
    cash_krw: float
    burn_rate_monthly: float
    runway_months: int
    funding_rounds: List[Dict[str, Any]]
    government_grants: float
    risks: List[Dict[str, Any]]
    summary: str


class SurvivalOutcome(TypedDict, total=False):
    score: float
    analysis: SurvivalMetrics


# ═══════════════════════════════════════════════════════════════════════════
# 최종 의사결정 및 보고서
# ═══════════════════════════════════════════════════════════════════════════


class DecisionSummary(TypedDict, total=False):
    final_score: float
    recommendation: str
    confidence: float
    key_insights: List[str]
    risk_factors: List[str]


class ReportSection(TypedDict, total=False):
    title: str
    body: str


class ReportBundle(TypedDict, total=False):
    markdown: str
    path: str
    sections: List[ReportSection]


class PipelineMeta(TypedDict, total=False):
    current_agent: str
    stage: str
    timestamp: str
    processing_time: float
    data_quality: str
    history: List[str]


# ═══════════════════════════════════════════════════════════════════════════
# 전체 State
# ═══════════════════════════════════════════════════════════════════════════


class InvestmentState(TypedDict, total=False):
    """LangGraph/Agent 파이프라인 전체에서 공유하는 상태."""

    profile: CandidateProfile
    space: SpaceOperations
    funding: FundingSnapshot
    growth: GrowthOutcome
    market: MarketOutcome
    competitor: CompetitorProfile
    comparison: ComparisonSummary
    survival: SurvivalOutcome
    decision: DecisionSummary
    report: ReportBundle
    meta: PipelineMeta


# ═══════════════════════════════════════════════════════════════════════════
# 초기 State 생성
# ═══════════════════════════════════════════════════════════════════════════


def create_initial_state(timestamp: Optional[str] = None) -> InvestmentState:
    """워크플로우 초기 상태."""

    return InvestmentState(
        profile={},
        space={},
        funding={},
        growth={},
        market={},
        competitor={},
        comparison={},
        survival={},
        decision={},
        report={},
        meta={
            "current_agent": "agent_0",
            "stage": "startup_search",
            "timestamp": timestamp or datetime.utcnow().isoformat(),
            "history": [],
        },
    )
