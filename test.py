# test.py
from agents.market_analyzer import run
from graph.state import create_initial_state


state = create_initial_state("핀테크 스타트업 투자")
state["candidates"] = [{"name": "토스"}, {"name": "두나무"}]

result = run(state)
print(result["market_analysis"])
