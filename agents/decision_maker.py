"""
Agent: 투자 판단 (Decision Maker)

최종 점수와 분석 결과를 바탕으로 투자 의사결정을 수행합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# .env 로드
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")


@dataclass
class DecisionMakerConfig:
    """투자 판단 설정"""

    grade_thresholds: Dict[str, float] = None

    def __post_init__(self):
        if self.grade_thresholds is None:
            self.grade_thresholds = {
                "S": 90.0,  # 최우선 투자
                "A": 75.0,  # 적극 투자
                "B": 60.0,  # 조건부 투자
                "C": 45.0,  # 투자 보류
                "D": 0.0,  # 투자 불가
            }


class DecisionMaker:
    """투자 판단 에이전트"""

    def __init__(self, config: Optional[DecisionMakerConfig] = None):
        self.config = config or DecisionMakerConfig()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """투자 판단 실행"""
        company = state.get("profile", {}).get("name", "Unknown")
        # score_breakdown.final에서 점수 가져오기 (fallback: state.score)
        final_score = state.get("score_breakdown", {}).get("final") or state.get(
            "score", 0.0
        )

        print(f"\n{'='*80}")
        print(f"⚖️ [투자 판단] {company}")
        print(f"{'='*80}")

        # 1. 등급 판정
        grade = self._determine_grade(final_score)

        # 2. 투자 결정
        decision = self._make_decision(grade)

        # 3. 위험도 평가
        risk_level = self._assess_risk(state, grade)

        # 4. 투자 사유 생성
        reasons = self._generate_reasons(state, grade)

        # 5. 주의사항 생성
        warnings = self._generate_warnings(state, risk_level)

        # 결과 출력
        print(f"\n✅ 투자 판단 완료")
        print(f"   등급: {grade}")
        print(f"   결정: {decision}")
        print(f"   위험도: {risk_level}")
        print(f"   점수: {final_score:.2f}/100")

        # State 업데이트
        result = {
            "decision": {
                "grade": grade,
                "decision": decision,
                "risk_level": risk_level,
                "reasons": reasons,
                "warnings": warnings,
                "final_score": final_score,
            }
        }

        return result

    def _determine_grade(self, score: float) -> str:
        """점수를 바탕으로 등급 판정"""
        for grade, threshold in sorted(
            self.config.grade_thresholds.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if score >= threshold:
                return grade
        return "D"

    def _make_decision(self, grade: str) -> str:
        """등급에 따른 투자 결정"""
        decision_map = {
            "S": "최우선 투자 추천",
            "A": "적극 투자 추천",
            "B": "조건부 투자 추천",
            "C": "투자 보류",
            "D": "투자 불가",
        }
        return decision_map.get(grade, "판단 보류")

    def _assess_risk(self, state: Dict[str, Any], grade: str) -> str:
        """위험도 평가"""
        risk_factors = 0

        # 1. 기술 리스크 (InvestmentState의 'space' 키 사용)
        tech = state.get("space", {}) or state.get("tech_analysis", {})
        trl_level = tech.get("trl_level")
        if trl_level is not None and trl_level < 7:
            risk_factors += 1
        elif trl_level is None:
            risk_factors += 1  # TRL 정보 없음도 리스크
        if len(tech.get("patents", [])) == 0:
            risk_factors += 1

        # 2. 시장 리스크 (InvestmentState의 'market' 키 사용)
        market = state.get("market", {}) or state.get("market_analysis", {})
        # MarketAnalyzer는 score와 analysis를 구분하지 않고 직접 데이터 저장
        tam = market.get("tam_sam_som", {}).get("TAM", 0)
        if tam < 10:
            risk_factors += 1
        if len(market.get("pmf_signals", [])) < 2:
            risk_factors += 1

        # 3. 생존 리스크 - SurvivalAnalyzer 제거됨, funding에서 데이터 읽기
        funding = state.get("funding", {})
        # 투자 단계로 리스크 평가
        stage = funding.get("stage", "")
        if stage and stage not in [
            "Series A",
            "Series B",
            "Series C",
            "시리즈 A",
            "시리즈 B",
        ]:
            risk_factors += 1  # 초기 단계는 리스크

        total_funding = funding.get("total_funding_krw", 0)
        if total_funding < 10:  # 10억원 미만
            risk_factors += 1

        # 4. 경쟁 리스크
        comparison = state.get("comparison", {})
        if len(comparison.get("our_weaknesses", [])) > len(
            comparison.get("our_strengths", [])
        ):
            risk_factors += 1

        # 위험도 판정
        if risk_factors >= 5:
            return "높음"
        elif risk_factors >= 3:
            return "중간"
        else:
            return "낮음"

    def _generate_reasons(self, state: Dict[str, Any], grade: str) -> List[str]:
        """투자 사유 생성"""
        reasons = []

        # InvestmentState의 올바른 키 사용 (fallback 포함)
        tech = state.get("space", {}) or state.get("tech_analysis", {})
        market = state.get("market", {}) or state.get("market_analysis", {})
        funding = state.get("funding", {})
        comparison = state.get("comparison", {})

        # 긍정적 사유
        trl_level = tech.get("trl_level")
        if trl_level is not None and trl_level >= 7:
            reasons.append(f"높은 기술 성숙도 (TRL {trl_level})")

        if len(tech.get("patents", [])) >= 3:
            reasons.append(
                f"강력한 IP 포트폴리오 (특허 {len(tech.get('patents', []))}건)"
            )

        tam = market.get("tam_sam_som", {}).get("TAM", 0)
        if tam >= 50:
            reasons.append(f"대규모 시장 기회 (TAM ${tam}B)")

        growth_rate = market.get("growth_rate", 0)
        if growth_rate and growth_rate >= 0.15:
            reasons.append(f"높은 시장 성장률 ({growth_rate*100:.1f}%)")

        if len(market.get("pmf_signals", [])) >= 3:
            reasons.append("강력한 PMF 검증")

        # funding에서 투자 정보 확인
        total_funding = funding.get("total_funding_krw", 0)
        if total_funding >= 50:  # 50억원 이상
            reasons.append(f"안정적 자금 확보 ({total_funding}억원)")

        our_strengths = comparison.get("our_strengths", [])
        if len(our_strengths) >= 3:
            reasons.append(f"경쟁 우위 확보 ({len(our_strengths)}개 강점)")

        # 등급별 기본 사유
        if grade == "S":
            reasons.insert(0, "모든 평가 지표에서 우수한 성과")
        elif grade == "A":
            reasons.insert(0, "대부분의 평가 지표에서 양호한 성과")
        elif grade == "B":
            reasons.insert(0, "일부 개선이 필요하나 잠재력 있음")

        return reasons[:5]

    def _generate_warnings(self, state: Dict[str, Any], risk_level: str) -> List[str]:
        """주의사항 생성"""
        warnings = []

        # InvestmentState의 올바른 키 사용 (fallback 포함)
        tech = state.get("space", {}) or state.get("tech_analysis", {})
        market = state.get("market", {}) or state.get("market_analysis", {})
        funding = state.get("funding", {})
        comparison = state.get("comparison", {})

        # 기술 관련 주의사항
        trl_level = tech.get("trl_level")
        if trl_level is None or trl_level < 7:
            warnings.append(f"기술 성숙도 낮음 (TRL {trl_level if trl_level is not None else 'N/A'})")

        if len(tech.get("patents", [])) == 0:
            warnings.append("특허 보호 없음 - IP 전략 필요")

        # 시장 관련 주의사항
        tam = market.get("tam_sam_som", {}).get("TAM", 0)
        if tam < 10:
            warnings.append(f"제한적 시장 규모 (TAM ${tam}B)")

        if len(market.get("pmf_signals", [])) < 2:
            warnings.append("PMF 검증 부족")

        # 투자 관련 주의사항 (SurvivalAnalyzer 제거됨)
        total_funding = funding.get("total_funding_krw", 0)
        if total_funding < 10:  # 10억원 미만
            warnings.append(f"제한적 투자 유치 ({total_funding}억원)")

        stage = funding.get("stage", "")
        if not stage or stage in ["Seed", "Pre-Seed", "시드", "프리시드"]:
            warnings.append("초기 투자 단계 - 추가 자금 확보 필요")

        # 경쟁 관련 주의사항
        our_weaknesses = comparison.get("our_weaknesses", [])
        if len(our_weaknesses) >= 3:
            warnings.append(f"경쟁 약점 {len(our_weaknesses)}개 존재")

        # 위험도별 경고
        if risk_level == "높음":
            warnings.insert(0, "⚠️ 높은 투자 리스크 - 신중한 검토 필요")
        elif risk_level == "중간":
            warnings.insert(0, "⚠️ 중간 수준 리스크 - 모니터링 필요")

        return warnings[:5]


def _demo():
    """데모 실행"""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from graph.state import create_initial_state

    state = create_initial_state()
    state["profile"] = {"name": "나라스페이스"}
    state["score"] = 78.5
    state["tech_analysis"] = {
        "trl_level": 9,
        "patents": [{"type": "특허"}],
        "core_technology": ["AI"],
    }
    state["market_analysis"] = {
        "tam_sam_som": {"TAM": 100},
        "growth_rate": 0.18,
        "pmf_signals": ["신호1", "신호2", "신호3"],
    }
    state["survival_analysis"] = {
        "financial": {"runway_months": 18},
        "funding_history": [{"stage": "Series A"}, {"stage": "Seed"}],
        "team_info": {"team_size": 25},
        "risks": [],
    }
    state["comparison"] = {
        "our_strengths": ["강점1", "강점2", "강점3"],
        "our_weaknesses": ["약점1"],
    }

    decision_maker = DecisionMaker()
    result = decision_maker.run(state)

    print("\n" + "=" * 80)
    print("📊 최종 결과")
    print("=" * 80)
    print(f"등급: {result['decision']['grade']}")
    print(f"결정: {result['decision']['decision']}")
    print(f"위험도: {result['decision']['risk_level']}")
    print("\n투자 사유:")
    for reason in result["decision"]["reasons"]:
        print(f"  - {reason}")
    print("\n주의사항:")
    for warning in result["decision"]["warnings"]:
        print(f"  - {warning}")


if __name__ == "__main__":
    _demo()
