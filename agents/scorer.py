"""
Agent: 점수 산출 (Scorer)

Berkus Method와 Scorecard Method를 기반으로 최종 점수를 계산합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# .env 로드
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")

try:
    from rag.evaluation_rag import EvaluationRAG
except ImportError:  # pragma: no cover
    EvaluationRAG = None  # type: ignore[assignment]


@dataclass
class ScorerConfig:
    """점수 산출 설정"""

    berkus_weight: float = 0.4
    scorecard_weight: float = 0.6


class Scorer:
    """점수 산출 에이전트"""

    def __init__(self, config: Optional[ScorerConfig] = None):
        self.config = config or ScorerConfig()
        self.rag_knowledge = self._load_rag_knowledge()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """점수 산출 실행"""
        company = state.get("profile", {}).get("name", "Unknown")

        print(f"\n{'='*80}")
        print(f"📊 [점수 산출] {company}")
        print(f"{'='*80}")

        # 1. Berkus Method 점수
        berkus_score = self._calculate_berkus(state)

        # 2. Scorecard Method 점수
        scorecard_score = self._calculate_scorecard(state)

        # 3. 최종 점수 (가중평균)
        final_score = (
            berkus_score * self.config.berkus_weight
            + scorecard_score * self.config.scorecard_weight
        )

        # 4. 세부 점수
        breakdown = {
            "berkus": berkus_score,
            "scorecard": scorecard_score,
            "final": round(final_score, 2),
        }

        # 결과 출력
        print(f"\n✅ 점수 산출 완료")
        print(f"   Berkus: {berkus_score}/100")
        print(f"   Scorecard: {scorecard_score}/100")
        print(f"   최종: {final_score:.2f}/100")

        # State 업데이트
        result = {
            "score": round(final_score, 2),
            "score_breakdown": breakdown,
        }

        return result

    def _calculate_berkus(self, state: Dict[str, Any]) -> float:
        """Berkus Method 점수 계산"""
        # RAG에서 Berkus 기준 가져오기
        berkus_criteria = self.rag_knowledge.get("berkus_criteria", {})

        # 기본 배점 (총 $2.5M → 100점 환산)
        max_score = 2500000
        total_value = 0

        # 1. 아이디어 품질 (sound idea) - $500K
        # tech_analysis 또는 space 키에서 데이터 읽기
        tech_analysis = state.get("tech_analysis", {}) or state.get("space", {})
        if tech_analysis.get("trl_level"):
            trl = tech_analysis["trl_level"]
            if trl >= 7:
                total_value += 500000
            elif trl >= 4:
                total_value += 300000
            else:
                total_value += 100000

        # 2. 프로토타입 (prototype) - $500K
        trl = tech_analysis.get("trl_level")
        if trl is not None and trl >= 6:
            total_value += 500000
        elif tech_analysis.get("core_technology"):
            total_value += 250000

        # 3. 경영진 (quality team) - $500K
        # survival_analysis 제거됨, funding에서 데이터 읽기
        funding = state.get("funding", {})
        team_info = {}  # 팀 정보는 현재 수집하지 않음
        if team_info.get("team_size", 0) >= 20:
            total_value += 500000
        elif team_info.get("team_size", 0) >= 10:
            total_value += 300000
        elif team_info.get("key_people"):
            total_value += 200000

        # 4. 전략적 관계 (strategic relationships) - $500K
        # funding에서 투자 정보 확인
        total_funding = funding.get("total_funding_krw", 0)
        funding_history = [1] if total_funding > 0 else []
        if len(funding_history) >= 2:
            total_value += 500000
        elif len(funding_history) >= 1:
            total_value += 300000

        # 5. 제품 출시 (product rollout) - $500K
        # market_analysis 또는 market 키에서 데이터 읽기
        market_analysis = state.get("market_analysis", {}) or state.get("market", {})
        pmf_signals = market_analysis.get("pmf_signals", [])
        if len(pmf_signals) >= 3:
            total_value += 500000
        elif len(pmf_signals) >= 1:
            total_value += 300000

        # 100점 환산
        score = (total_value / max_score) * 100
        return round(score, 2)

    def _calculate_scorecard(self, state: Dict[str, Any]) -> float:
        """Scorecard Method 점수 계산"""
        # RAG에서 Scorecard 가중치 가져오기
        scorecard_weights = self.rag_knowledge.get("scorecard_weights", {})

        # 기본 가중치 (총 100%)
        default_weights = {
            "management": 30,
            "opportunity": 25,
            "product": 15,
            "competitive_environment": 10,
            "marketing": 10,
            "need_for_funding": 5,
            "other": 5,
        }

        weights = scorecard_weights if scorecard_weights else default_weights

        total_score = 0.0

        # 1. 경영진 (management) - 30%
        # survival_analysis 제거됨, funding에서 데이터 읽기
        funding = state.get("funding", {})
        team_info = {}  # 팀 정보는 현재 수집하지 않음
        management_score = 0
        if team_info.get("team_size", 0) >= 20:
            management_score = 100
        elif team_info.get("team_size", 0) >= 10:
            management_score = 70
        elif team_info.get("key_people"):
            management_score = 50
        else:
            management_score = 30
        total_score += (management_score / 100) * weights.get("management", 30)

        # 2. 기회 (opportunity) - 25%
        # market_analysis 또는 market 키에서 데이터 읽기
        market_analysis = state.get("market_analysis", {}) or state.get("market", {})
        tam = market_analysis.get("tam_sam_som", {}).get("TAM", 0)
        opportunity_score = 0
        if tam >= 100:
            opportunity_score = 100
        elif tam >= 50:
            opportunity_score = 80
        elif tam >= 10:
            opportunity_score = 60
        else:
            opportunity_score = 40
        total_score += (opportunity_score / 100) * weights.get("opportunity", 25)

        # 3. 제품/기술 (product) - 15%
        # tech_analysis 또는 space 키에서 데이터 읽기
        tech_analysis = state.get("tech_analysis", {}) or state.get("space", {})
        product_score = tech_analysis.get("score", 0)
        total_score += (product_score / 100) * weights.get("product", 15)

        # 4. 경쟁 환경 (competitive_environment) - 10%
        comparison = state.get("comparison", {})
        our_strengths = comparison.get("our_strengths", [])
        competitive_score = min(len(our_strengths) * 30, 100)
        total_score += (competitive_score / 100) * weights.get(
            "competitive_environment", 10
        )

        # 5. 마케팅/판매 (marketing) - 10%
        # market에서 PMF 신호 읽기
        market = state.get("market", {}) or market_analysis
        pmf_signals = market.get("pmf_signals", [])
        marketing_score = min(len(pmf_signals) * 30, 100)
        total_score += (marketing_score / 100) * weights.get("marketing", 10)

        # 6. 자금 조달 필요성 (need_for_funding) - 5%
        # funding에서 투자 정보 확인
        total_funding = funding.get("total_funding_krw", 0)
        funding_history = [1] if total_funding > 0 else []
        funding_score = min(len(funding_history) * 30, 100)
        total_score += (funding_score / 100) * weights.get("need_for_funding", 5)

        # 7. 기타 (other) - 5%
        growth_analysis = state.get("growth", {})
        other_score = growth_analysis.get("score", 0)
        total_score += (other_score / 100) * weights.get("other", 5)

        return round(total_score, 2)

    def _load_rag_knowledge(self) -> Dict[str, Any]:
        """RAG에서 평가 기준 로드"""
        if not EvaluationRAG:
            return {}

        try:
            rag = EvaluationRAG()
            return {
                "berkus_criteria": rag.get_berkus_criteria(),
                "scorecard_weights": rag.get_scorecard_weights(),
            }
        except Exception as e:
            print(f"⚠️ RAG 로드 실패: {e}")
            return {}


def _demo():
    """데모 실행"""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from graph.state import create_initial_state

    state = create_initial_state()
    state["profile"] = {"name": "나라스페이스"}
    state["tech_analysis"] = {
        "trl_level": 9,
        "score": 70,
        "core_technology": ["AI", "위성"],
    }
    state["market_analysis"] = {
        "tam_sam_som": {"TAM": 100},
        "pmf_signals": ["신호1", "신호2"],
    }
    state["survival_analysis"] = {
        "team_info": {"team_size": 25},
        "funding_history": [{"stage": "Series A"}],
    }
    state["comparison"] = {"our_strengths": ["강점1", "강점2", "강점3"]}
    state["growth"] = {"score": 65}

    scorer = Scorer()
    result = scorer.run(state)

    print("\n" + "=" * 80)
    print("📊 최종 결과")
    print("=" * 80)
    print(f"최종 점수: {result['score']}/100")
    print(f"세부: {result['score_breakdown']}")


if __name__ == "__main__":
    _demo()
