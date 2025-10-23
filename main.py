"""
AI 스타트업 투자 평가 시스템 - 메인 엔트리 포인트

전체 파이프라인을 실행합니다.
"""

from __future__ import annotations

from graph.workflow import run_workflow


def main():
    """메인 실행 함수"""
    print("\n" + "🌟" * 40)
    print("\n    AI 스타트업 투자 평가 시스템")
    print("    AI Startup Investment Evaluation System")
    print("\n" + "🌟" * 40 + "\n")

    try:
        # Workflow 실행
        final_state = run_workflow()

        # 결과 출력
        print("\n" + "=" * 80)
        print("📊 최종 결과 요약")
        print("=" * 80)

        company = final_state.get("profile", {}).get("name", "Unknown")
        decision = final_state.get("decision", {})

        # 점수: decision.final_score → score_breakdown.final → score 순으로 fallback
        # 0.0도 유효한 점수이므로 None 체크 필요
        score = decision.get("final_score")
        if score is None or score == 0:
            score = final_state.get("score_breakdown", {}).get("final")
        if score is None or score == 0:
            score = final_state.get("score", 0)

        grade = decision.get("grade", "N/A")
        recommendation = decision.get("decision", "N/A")
        risk = decision.get("risk_level", "N/A")
        report_path = final_state.get("report", {}).get("path", "N/A")

        print(f"\n🏢 기업명: {company}")
        print(f"📊 최종 점수: {score}/100")
        print(f"🏆 등급: {grade}")
        print(f"💡 투자 추천: {recommendation}")
        print(f"⚠️  위험도: {risk}")
        print(f"📄 보고서: {report_path}")

        # 투자 사유
        reasons = decision.get("reasons", [])
        if reasons:
            print(f"\n✅ 투자 사유:")
            for idx, reason in enumerate(reasons[:5], 1):
                print(f"   {idx}. {reason}")

        # 주의사항
        warnings = decision.get("warnings", [])
        if warnings:
            print(f"\n⚠️  주의사항:")
            for idx, warning in enumerate(warnings[:5], 1):
                print(f"   {idx}. {warning}")

        print("\n" + "=" * 80)
        print("✅ 분석 완료! 보고서를 확인하세요.")
        print("=" * 80 + "\n")

    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n❌ 오류 발생: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
