# graph/workflow.py
from langgraph.graph import StateGraph, END
from .state import AgentState
from agents import (
    candidate_selector,
    competitor_analyzer,
    tech_analyzer,
    market_analyzer,
    survival_analyzer,
    scorer,
    decision_maker,
    report_generator,
    professional_document_generator,
)


def create_workflow():
    """
    새로운 워크플로우:
    1. 후보_선택 (2개 한국 스타트업)
    2. 1차 병렬 분석 (기술/시장/생존성)
    3. 1차 점수_산출
    4. 경쟁사_탐색 (후보 각각의 경쟁사 찾기)
    5. 2차 병렬 분석 (경쟁사 포함)
    6. 2차 점수_산출 (최종)
    7. 투자_판단 → 보고서_생성 → 문서_생성
    """
    workflow = StateGraph(AgentState)

    # 노드 추가 - 1차와 2차를 구분
    workflow.add_node("후보_선택", candidate_selector.run)

    # 1차: 후보만 분석
    workflow.add_node("기술_분석_1", tech_analyzer.run)
    workflow.add_node("시장_분석_1", market_analyzer.run)
    workflow.add_node("생존성_분석_1", survival_analyzer.run)
    workflow.add_node("점수_산출_1", scorer.run)

    # 경쟁사 탐색
    workflow.add_node("경쟁사_탐색", competitor_analyzer.run)

    # 2차: 경쟁사 포함 재분석
    workflow.add_node("기술_분석_2", tech_analyzer.run)
    workflow.add_node("시장_분석_2", market_analyzer.run)
    workflow.add_node("생존성_분석_2", survival_analyzer.run)
    workflow.add_node("점수_산출_2", scorer.run)

    # 최종 단계
    workflow.add_node("투자_판단", decision_maker.run)
    workflow.add_node("보고서_생성", report_generator.run)
    workflow.add_node("문서_생성", professional_document_generator.run)

    # 플로우 정의
    workflow.set_entry_point("후보_선택")

    # 1차: 후보 선택 후 병렬 분석
    workflow.add_edge("후보_선택", "기술_분석_1")
    workflow.add_edge("후보_선택", "시장_분석_1")
    workflow.add_edge("후보_선택", "생존성_분석_1")

    # 1차 병렬 분석 → 1차 점수 산출
    workflow.add_edge("기술_분석_1", "점수_산출_1")
    workflow.add_edge("시장_분석_1", "점수_산출_1")
    workflow.add_edge("생존성_분석_1", "점수_산출_1")

    # 1차 점수 → 경쟁사 탐색
    workflow.add_edge("점수_산출_1", "경쟁사_탐색")

    # 2차: 경쟁사 탐색 후 재분석
    workflow.add_edge("경쟁사_탐색", "기술_분석_2")
    workflow.add_edge("경쟁사_탐색", "시장_분석_2")
    workflow.add_edge("경쟁사_탐색", "생존성_분석_2")

    # 2차 병렬 분석 → 2차 최종 점수
    workflow.add_edge("기술_분석_2", "점수_산출_2")
    workflow.add_edge("시장_분석_2", "점수_산출_2")
    workflow.add_edge("생존성_분석_2", "점수_산출_2")

    # 최종: 점수 → 판단 → 보고서
    workflow.add_edge("점수_산출_2", "투자_판단")
    workflow.add_edge("투자_판단", "보고서_생성")
    workflow.add_edge("보고서_생성", "문서_생성")
    workflow.add_edge("문서_생성", END)

    return workflow.compile()
