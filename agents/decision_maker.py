# agents/decision_maker.py
from graph.state import AgentState


def run(state: AgentState) -> AgentState:
    """투자 판단 에이전트 - 정교한 평가 기준 적용"""
    print("\n[투자 판단] 시작")

    scores = state["final_score"]["scores"]

    # 각 기업별 상세 평가
    evaluations = []
    for company_score in scores:
        evaluation = evaluate_investment(company_score)
        evaluations.append(evaluation)

    # 최고 점수 기업 선정
    best = max(evaluations, key=lambda x: x["점수"])

    decision = {
        "추천기업": best["기업명"],
        "점수": best["점수"],
        "판정": best["판정"],
        "판정등급": best["판정등급"],
        "위험도": best["위험도"],
        "투자사유": best["투자사유"],
        "주의사항": best["주의사항"],
        "전체평가": evaluations,  # 모든 기업 평가 결과
    }

    print(f"  추천: {decision['추천기업']} ({decision['점수']}점)")
    print(f"  판정: {decision['판정등급']} - {decision['판정']}")
    print(f"  위험도: {decision['위험도']}")

    return {**state, "investment_decision": decision}


def evaluate_investment(company_score: dict) -> dict:
    """
    개별 기업 투자 평가

    Args:
        company_score: scorer에서 산출된 기업 점수

    Returns:
        상세 평가 결과
    """
    name = company_score["name"]
    total = company_score["total"]
    berkus = company_score["berkus"]
    scorecard = company_score["scorecard"]
    growth = company_score["growth"]
    survival = company_score["survival"]
    pmf = company_score["pmf"]

    # 1. 종합 점수 기반 기본 판정
    if total >= 90:
        grade = "S"
        decision = "적극 투자 권장"
    elif total >= 75:
        grade = "A"
        decision = "투자 권장"
    elif total >= 60:
        grade = "B"
        decision = "조건부 투자"
    elif total >= 45:
        grade = "C"
        decision = "투자 보류"
    else:
        grade = "D"
        decision = "투자 부적합"

    # 2. 세부 기준 체크 (필수 조건)
    warnings = []
    risk_level = "낮음"

    # Berkus 최소 기준 ($1.5M)
    if berkus["총점"] < 1500000:
        warnings.append("Berkus 평가 미달 (최소 $1.5M 필요)")
        risk_level = "중간"

    # 성장성 체크
    if growth["판정"] == "경고":
        warnings.append("성장률 부족 (주간 1% 미만)")
        risk_level = "높음" if risk_level == "중간" else "중간"

    # 생존성 체크
    if survival["판정"] != "Default Alive":
        warnings.append("생존성 우려 (Default Dead)")
        risk_level = "높음"

    # PMF 체크
    if pmf["달성"] != "APMF":
        warnings.append("Product-Market Fit 미달성")
        risk_level = "중간" if risk_level == "낮음" else risk_level

    # Scorecard 낮은 점수 체크
    if scorecard["점수"] < 90:
        warnings.append(f"시장 경쟁력 약함 (Scorecard {scorecard['점수']}점)")

    # 3. 위험도 조정
    if len(warnings) >= 3:
        risk_level = "높음"
        # 판정 등급 하향 조정
        if grade in ["S", "A"]:
            grade = "B"
            decision = "조건부 투자"
        elif grade == "B":
            grade = "C"
            decision = "투자 보류"

    # 4. 투자 사유 생성
    reasons = []

    # 긍정적 요인
    if berkus["총점"] >= 2000000:
        reasons.append(f"✅ 우수한 Berkus 평가 (${berkus['총점']:,})")

    if scorecard["점수"] >= 100:
        reasons.append(f"✅ 강력한 시장 경쟁력 (Scorecard {scorecard['점수']}점)")

    if growth["판정"] in ["우수", "양호"]:
        reasons.append(
            f"✅ 견고한 성장성 ({growth['판정']}, 주간 {growth['주간성장률']*100:.1f}%)"
        )

    if survival["판정"] == "Default Alive":
        reasons.append(f"✅ 안정적 생존성 (런웨이 {survival['런웨이']}개월)")

    if pmf["달성"] == "APMF":
        reasons.append(f"✅ Product-Market Fit 달성 ({pmf['신호개수']})")

    if not reasons:
        reasons.append("⚠️ 두드러진 강점 없음")

    # 5. 최종 결과
    return {
        "기업명": name,
        "점수": total,
        "판정등급": grade,
        "판정": decision,
        "위험도": risk_level,
        "투자사유": reasons,
        "주의사항": warnings if warnings else ["없음"],
        "세부점수": {
            "Berkus": f"${berkus['총점']:,}",
            "Scorecard": f"{scorecard['점수']}점",
            "성장성": f"{growth['판정']} ({growth['점수']}점)",
            "생존성": f"{survival['판정']} ({survival['점수']}점)",
            "PMF": f"{pmf['달성']} ({pmf['점수']}점)",
        },
    }
