# test_rag.py
from rag.evaluation_rag import EvaluationRAG

# RAG 초기화
eval_rag = EvaluationRAG()

# 기준 확인
print("Berkus:", eval_rag.get_berkus_criteria())
print("Scorecard:", eval_rag.get_scorecard_weights())
print("Growth:", eval_rag.get_growth_thresholds())
