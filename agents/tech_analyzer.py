# agents/tech_analyzer.py
from graph.state import AgentState


def run(state: AgentState) -> dict:
    """기술 분석"""
    print("\n[기술 분석] 시작")

    analysis = {
        "토스": {"기술점수": 85, "특허": 5},
        "카카오뱅크": {"기술점수": 80, "특허": 3},
    }

    # 병렬 실행 시 충돌 방지: 필요한 필드만 반환
    return {"tech_analysis": analysis}
