"""Startup evaluation pipeline entry point.

현재는 Agent 0 결과(JSON)를 읽어 GrowthAgent를 실행하는 최소 예시만 포함한다.
추가 에이전트가 준비되면 `run_pipeline` 내 단계들을 확장해 연결한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from agents.growth_agent import GrowthAgent
from graph.state import InvestmentState, create_initial_state


def load_agent0_result(path: Path) -> Dict[str, Any]:
    """Agent 0 실행 결과(JSON)를 로드한다."""

    if not path.exists():
        raise FileNotFoundError(f"Agent0 결과 파일을 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def hydrate_state(agent0_payload: Dict[str, Any]) -> InvestmentState:
    """Agent 0 결과를 LangGraph 상태 구조에 맞춰 채워 넣는다."""

    state = create_initial_state()

    # 최신 Agent0 포맷(profile/space/funding 등) 지원
    if "profile" in agent0_payload:
        state.setdefault("profile", {}).update(agent0_payload["profile"] or {})
    else:
        profile = state.setdefault("profile", {})
        profile["name"] = agent0_payload.get("candidate_name", "")
        profile["founded_year"] = agent0_payload.get("founded_year")
        profile["ceo_name"] = agent0_payload.get("ceo_name")
        profile["headquarters"] = agent0_payload.get("headquarters")
        profile["business_description"] = agent0_payload.get("business_description", "")

    if "space" in agent0_payload:
        state.setdefault("space", {}).update(agent0_payload["space"] or {})
    else:
        space = state.setdefault("space", {})
        space["satellites_deployed"] = agent0_payload.get("satellites_deployed")
        space["satellites_planned"] = agent0_payload.get("satellites_planned")
        space["satellite_names"] = agent0_payload.get("satellite_names", [])
        space["main_technology"] = agent0_payload.get("main_technology", [])
        space["industry_sector"] = agent0_payload.get("industry_sector")

    if "funding" in agent0_payload:
        state.setdefault("funding", {}).update(agent0_payload["funding"] or {})
    else:
        funding = state.setdefault("funding", {})
        funding["stage"] = agent0_payload.get("investment_stage")
        funding["total_funding_krw"] = agent0_payload.get("total_funding_krw")
        funding["last_funding_date"] = agent0_payload.get("last_funding_date")
        funding["major_investors"] = agent0_payload.get("major_investors", [])
        funding["partners"] = agent0_payload.get("partners", [])
        funding["products"] = agent0_payload.get("products", [])
        funding["customers"] = agent0_payload.get("customers", [])

    meta = state.setdefault("meta", {})
    if "meta" in agent0_payload:
        meta.update({k: v for k, v in agent0_payload["meta"].items() if k != "history"})
    meta.setdefault("history", []).append("agent_0_ingested")

    return state


def run_pipeline(agent0_path: Path) -> InvestmentState:
    """Pipeline orchestrator. 필요에 따라 Agent 2/3 등을 이어 붙인다."""

    agent0_payload = load_agent0_result(agent0_path)
    state = hydrate_state(agent0_payload)

    growth_agent = GrowthAgent()
    state = growth_agent.run(state)

    return state


def main() -> None:
    """CLI entry."""

    state = run_pipeline(Path("agents/agent0_result.json"))
    growth = state.get("growth", {})
    score = growth.get("score", 0.0)
    summary = growth.get("analysis", {}).get("summary", "")

    print("=" * 80)
    print(f"Growth Score: {score}")
    print("-" * 80)
    print(summary)
    print("=" * 80)


if __name__ == "__main__":
    main()
