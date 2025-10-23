"""
LangGraph 기반 투자 평가 Workflow

플로우:
1. 후보 선택
2. 1차 분석 (기술/시장/생존성 병렬)
3. 성장성 분석
4. 경쟁사 분석
5. 점수 산출
6. 투자 판단
7. 보고서 생성
"""

from __future__ import annotations

from typing import Any, Dict

import time
from langgraph.graph import StateGraph, END

from graph.state import InvestmentState, create_initial_state
from agents.candidate_selector import CandidateSelector
from agents.tech_analyzer import TechAnalyzer
from agents.market_analyzer import MarketAnalyzer
# from agents.survival_analyzer import SurvivalAnalyzer  # 제거: 정보 수집 불충분
from agents.growth_agent import GrowthAgent
from agents.competitor_analyzer import CompetitorAnalyzer
from agents.scorer import Scorer
from agents.decision_maker import DecisionMaker
from agents.report_generator import ReportGenerator


# Agent 인스턴스 생성
candidate_selector = CandidateSelector()
tech_analyzer = TechAnalyzer(use_crawler=True)  # WebCrawler 활성화 + 팀 평가 추가
market_analyzer = MarketAnalyzer(use_crawler=True)  # WebCrawler + ECOS API 활성화
# survival_analyzer = SurvivalAnalyzer()  # 제거
growth_agent = GrowthAgent()
competitor_analyzer = CompetitorAnalyzer()
scorer = Scorer()
decision_maker = DecisionMaker()
report_generator = ReportGenerator()


# Node 함수 정의
def node_candidate_selection(state: InvestmentState) -> InvestmentState:
    """후보 선택"""
    result = candidate_selector.run(state)
    state.update(result)
    time.sleep(0.5)  # Rate limit 방지

    # 첫 번째 후보를 profile에 복사
    if result.get("candidates"):
        candidate = result["candidates"][0]
        state.setdefault("profile", {}).update(
            {
                "name": candidate.get("name"),
                "business_description": candidate.get("description"),
            }
        )

    return state


def node_tech_analysis(state: InvestmentState) -> InvestmentState:
    """기술 분석"""
    result = tech_analyzer.run(state)
    state.update(result)
    time.sleep(0.5)  # Rate limit 방지
    return state


def node_market_analysis(state: InvestmentState) -> InvestmentState:
    """시장 분석"""
    result = market_analyzer.run(state)
    state.update(result)
    time.sleep(0.5)  # Rate limit 방지
    return state


# def node_survival_analysis(state: InvestmentState) -> InvestmentState:
#     """생존성 분석 - 제거됨"""
#     result = survival_analyzer.run(state)
#     state.update(result)
#     time.sleep(0.5)  # Rate limit 방지
#     return state


def node_growth_analysis(state: InvestmentState) -> InvestmentState:
    """성장성 분석"""
    result = growth_agent.run(state)
    state.update(result)
    return state


def node_competitor_analysis(state: InvestmentState) -> InvestmentState:
    """경쟁사 분석"""
    result = competitor_analyzer.run(state)
    state.update(result)
    time.sleep(0.5)  # Rate limit 방지
    return state


def node_scoring(state: InvestmentState) -> InvestmentState:
    """점수 산출"""
    result = scorer.run(state)
    state.update(result)
    return state


def node_decision(state: InvestmentState) -> InvestmentState:
    """투자 판단"""
    result = decision_maker.run(state)
    state.update(result)
    return state


def node_report_generation(state: InvestmentState) -> InvestmentState:
    """보고서 생성"""
    # 디버깅: state 키 확인
    print(f"\n[DEBUG] node_report_generation - state keys: {list(state.keys())}")
    print(f"[DEBUG] market_analysis in state: {'market_analysis' in state}")

    result = report_generator.run(state)
    state.update(result)
    return state


# Workflow 구성
def create_workflow() -> StateGraph:
    """LangGraph Workflow 생성"""
    workflow = StateGraph(InvestmentState)

    # 노드 추가
    workflow.add_node("candidate_selection", node_candidate_selection)
    workflow.add_node("tech_analysis", node_tech_analysis)
    workflow.add_node("market_analysis", node_market_analysis)
    # workflow.add_node("survival_analysis", node_survival_analysis)  # 제거
    workflow.add_node("growth_analysis", node_growth_analysis)
    workflow.add_node("competitor_analysis", node_competitor_analysis)
    workflow.add_node("scoring", node_scoring)
    workflow.add_node("decision", node_decision)
    workflow.add_node("report_generation", node_report_generation)

    # 엣지 추가 (순차 실행) - survival_analysis 제거됨
    workflow.set_entry_point("candidate_selection")
    workflow.add_edge("candidate_selection", "tech_analysis")
    workflow.add_edge("tech_analysis", "market_analysis")
    workflow.add_edge("market_analysis", "growth_analysis")  # survival_analysis 건너뜀
    workflow.add_edge("growth_analysis", "competitor_analysis")
    workflow.add_edge("competitor_analysis", "scoring")
    workflow.add_edge("scoring", "decision")
    workflow.add_edge("decision", "report_generation")
    workflow.add_edge("report_generation", END)

    return workflow


def run_workflow() -> InvestmentState:
    """Workflow 실행"""
    print("\n" + "=" * 80)
    print("🚀 AI 스타트업 투자 평가 시스템 시작")
    print("=" * 80)

    # 초기 상태 생성
    initial_state = create_initial_state()

    # Workflow 컴파일
    workflow = create_workflow()
    app = workflow.compile()

    # 실행
    final_state = app.invoke(initial_state)

    print("\n" + "=" * 80)
    print("✅ 분석 완료!")
    print("=" * 80)

    return final_state


if __name__ == "__main__":
    final_state = run_workflow()

    # 결과 요약
    print("\n" + "=" * 80)
    print("📊 최종 결과 요약")
    print("=" * 80)

    company = final_state.get("profile", {}).get("name", "Unknown")
    decision = final_state.get("decision", {})
    score = decision.get("final_score", 0)
    grade = decision.get("grade", "N/A")
    recommendation = decision.get("decision", "N/A")
    risk = decision.get("risk_level", "N/A")
    report_path = final_state.get("report", {}).get("path", "N/A")

    print(f"\n기업명: {company}")
    print(f"최종 점수: {score}/100")
    print(f"등급: {grade}")
    print(f"투자 추천: {recommendation}")
    print(f"위험도: {risk}")
    print(f"보고서: {report_path}")

    print("\n" + "=" * 80)
