# agents/scorer.py
from graph.state import AgentState
from rag.evaluation_rag import EvaluationRAG

eval_rag = EvaluationRAG()


def run(state: AgentState) -> AgentState:
    """점수 산출"""
    print("\n[점수 산출] 시작")

    candidates = state["candidates"]
    comparison_mode = state["comparison_mode"]

    # 평가 기준 로드
    berkus_criteria = eval_rag.get_berkus_criteria()
    scorecard_weights = eval_rag.get_scorecard_weights()
    growth_thresholds = eval_rag.get_growth_thresholds()

    scores = []

    for company in candidates:
        name = company["name"]
        print(f"  평가 중: {name}")

        # 각 방법론 점수 계산
        berkus = calculate_berkus(company, state, berkus_criteria)
        scorecard = calculate_scorecard(company, state, scorecard_weights)
        growth = calculate_growth(company, state, growth_thresholds)
        survival = calculate_survival(company, state)
        pmf = calculate_pmf(company, state)

        # 종합 점수
        total = (
            berkus["총점"] / 2500000 * 20  # 20%
            + scorecard["점수"] * 30  # 30%
            + growth["점수"] * 20  # 20%
            + survival["점수"] * 15  # 15%
            + pmf["점수"] * 15  # 15%
        )

        scores.append(
            {
                "name": name,
                "berkus": berkus,
                "scorecard": scorecard,
                "growth": growth,
                "survival": survival,
                "pmf": pmf,
                "total": round(total, 2),
            }
        )

    return {**state, "final_score": {"scores": scores}}


def calculate_berkus(company, state, criteria):
    """Berkus Method - RAG 기준 활용"""
    # RAG에서 추출한 기준 (각 항목당 최대 $500,000)
    # 실제 구현에서는 회사 데이터를 분석하여 점수 산정
    # 여기서는 예시로 80% 수준으로 평가

    scores = {}
    for key, max_value in criteria.items():
        # 실제로는 tech_analysis, market_analysis 등을 활용하여 점수 산정
        # 예시: 70-90% 범위로 평가
        score = int(max_value * 0.8)  # 80% 수준
        scores[key] = score

    total = sum(scores.values())
    scores["총점"] = total

    return scores


def calculate_scorecard(company, state, weights):
    """Scorecard Method - RAG 가중치 활용"""
    # 실제 구현에서는 각 영역별 분석 결과를 활용
    # tech_analysis, market_analysis 등의 데이터를 종합

    # 예시 점수 (실제로는 분석 결과 기반)
    scores = {}
    for key in weights.keys():
        # 실제로는 해당 영역의 분석 결과를 점수화 (0-150점 범위)
        if key == "경영진":
            scores[key] = 120  # 우수
        elif key == "시장":
            scores[key] = 110  # 양호
        elif key == "제품":
            scores[key] = 100  # 평균
        else:
            scores[key] = 95  # 평균 이하

    # 가중 평균 계산 (RAG 가중치 활용)
    total = sum(scores[k] * weights[k] for k in scores.keys())

    return {
        "개별점수": scores,
        "가중치": weights,
        "가중합계": round(total, 2),
        "점수": round(total, 2),
    }


def calculate_growth(company, state, thresholds):
    """성장성"""
    weekly_growth = 0.07  # 7% (예시)

    if weekly_growth >= thresholds["우수"]:
        return {"주간성장률": weekly_growth, "판정": "우수", "점수": 100}
    elif weekly_growth >= thresholds["양호"]:
        return {"주간성장률": weekly_growth, "판정": "양호", "점수": 70}
    else:
        return {"주간성장률": weekly_growth, "판정": "경고", "점수": 30}


def calculate_survival(company, state):
    """생존성"""
    return {"런웨이": 18, "손익분기": 15, "판정": "Default Alive", "점수": 100}


def calculate_pmf(company, state):
    """PMF"""
    yes_count = 4

    if yes_count >= 4:
        return {"신호개수": f"{yes_count}/6", "달성": "APMF", "점수": 100}
    else:
        return {"신호개수": f"{yes_count}/6", "달성": "BPMF", "점수": 50}
