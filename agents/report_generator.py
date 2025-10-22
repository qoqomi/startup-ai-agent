# agents/report_generator.py
from graph.state import AgentState


def run(state: AgentState) -> AgentState:
    """보고서 생성"""
    print("\n[보고서 생성] 시작")

    scores = state["final_score"]["scores"]
    decision = state["investment_decision"]

    # 판정 등급별 이모지
    grade_emoji = {"S": "🌟", "A": "⭐", "B": "🔶", "C": "⚠️", "D": "❌"}

    # 위험도별 이모지
    risk_emoji = {"낮음": "🟢", "중간": "🟡", "높음": "🔴"}

    report = f"""
{'='*70}
🚀 AI 스타트업 투자 분석 보고서
{'='*70}

📊 종합 점수 (100점 만점)
{chr(10).join([f"  {'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else '  '} {s['name']}: {s['total']}점" for i, s in enumerate(sorted(scores, key=lambda x: x['total'], reverse=True))])}

{'='*70}
💡 최종 투자 판단
{'='*70}
  🏢 추천 기업: {decision['추천기업']}
  🎯 최종 점수: {decision['점수']}점
  {grade_emoji.get(decision.get('판정등급', 'B'), '🔶')} 판정 등급: {decision.get('판정등급', 'B')}등급
  📋 투자 판정: {decision['판정']}
  {risk_emoji.get(decision.get('위험도', '중간'), '🟡')} 위험도: {decision.get('위험도', '중간')}

📌 투자 사유:
{chr(10).join([f"  {reason}" for reason in decision.get('투자사유', ['정보 없음'])])}

⚠️  주의사항:
{chr(10).join([f"  • {warning}" for warning in decision.get('주의사항', ['없음'])])}

{'='*70}
📋 상세 평가 항목
{'='*70}
"""

    for s in scores:
        report += f"""
### 🏢 {s['name']}
┌─────────────────────────────────────────────────────────────────
│ ✅ Berkus Method (총 ${s['berkus']['총점']:,})
"""
        # Berkus 항목별 점수
        for key, value in s["berkus"].items():
            if key != "총점":
                report += f"│   - {key}: ${value:,}\n"

        report += f"""│
│ ✅ Scorecard Method (총 {s['scorecard']['점수']}점)
"""
        # Scorecard 항목별 점수와 가중치
        if "개별점수" in s["scorecard"]:
            for key, value in s["scorecard"]["개별점수"].items():
                weight = s["scorecard"]["가중치"].get(key, 0)
                report += f"│   - {key}: {value}점 (가중치 {weight*100:.0f}%)\n"

        report += f"""│
│ ✅ 성장성 분석
│   - 판정: {s['growth']['판정']}
│   - 주간 성장률: {s['growth']['주간성장률']*100:.1f}%
│   - 점수: {s['growth']['점수']}점
│
│ ✅ 생존성 분석
│   - 판정: {s['survival']['판정']}
│   - 런웨이: {s['survival']['런웨이']}개월
│   - 손익분기: {s['survival']['손익분기']}개월
│   - 점수: {s['survival']['점수']}점
│
│ ✅ PMF (Product-Market Fit)
│   - 달성 수준: {s['pmf']['달성']}
│   - 신호 개수: {s['pmf']['신호개수']}
│   - 점수: {s['pmf']['점수']}점
│
│ 🎯 종합 점수: {s['total']}점
└─────────────────────────────────────────────────────────────────

"""

    report += f"""
{'='*70}
📌 평가 기준 (RAG 기반)
{'='*70}
- Berkus Method: 각 항목당 최대 $500,000
- Scorecard Method: 경영진(30%), 시장(25%), 제품(15%), 경쟁(10%), 판매(10%), 투자(5%), 기타(5%)
- 성장성: 우수(10% 이상), 양호(5% 이상), 경고(1% 미만)
- 생존성: Default Alive 여부, 런웨이, 손익분기점
- PMF: 6가지 신호 중 4개 이상 충족 시 APMF
{'='*70}
"""

    return {**state, "report": report}
