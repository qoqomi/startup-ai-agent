from typing import TypedDict, List, Dict, Optional, Annotated
from operator import add


class AgentState(TypedDict):
    """투자 분석 에이전트 상태"""

    # 입력
    query: str  # 사용자 검색 쿼리 (예: "AI 핀테크 스타트업")

    # 1단계: 탐색
    candidates: List[Dict]  # 후보 스타트업 리스트
    competitors: List[Dict]  # 경쟁사 리스트

    # 2단계: 검증
    validation: Dict  # 비교 가능성 검증 결과
    comparison_mode: str  # "absolute" or "relative"

    # 3단계: 분석 (병렬)
    tech_summary: Dict  # 기술력 분석
    market_analysis: Dict  # 시장/고객 분석
    survival_analysis: Dict  # 생존성 분석

    # 4단계: 종합
    final_score: Dict  # 점수 산출 결과
    investment_decision: Dict  # 투자 판단
    report: str  # 최종 보고서
    document_path: str  # Word/PDF 문서 경로

    # 추가: 에러 처리 & 메타데이터
    errors: Annotated[List[str], add]  # 누적 에러 메시지
    search_results: List[Dict]  # 웹 검색 원본 결과 (캐싱용)
    documents: List[Dict]  # RAG 문서 (검증용)


# 초기 상태 정의
def create_initial_state(query: str) -> AgentState:
    """초기 상태 생성"""
    return {
        "query": query,
        "candidates": [],
        "competitors": [],
        "validation": {},
        "comparison_mode": "relative",
        "tech_summary": {},
        "market_analysis": {},
        "survival_analysis": {},
        "final_score": {},
        "investment_decision": {},
        "report": "",
        "document_path": "",
        "errors": [],
        "search_results": [],
        "documents": [],
    }
