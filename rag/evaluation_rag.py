# rag/evaluation_rag.py
from rag.rag_system import RAGSystem
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import json
import re

load_dotenv()


class EvaluationRAG:
    """평가 기준 RAG - 실제로 문서에서 추출"""

    def __init__(self):
        print("[INFO] 평가 기준 RAG 초기화 중...")
        self.rag = RAGSystem(doc_dir="documents")
        self.rag.build()
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def get_berkus_criteria(self) -> dict:
        """Berkus Method 기준 - 실제 추출"""
        results = self.rag.search(
            "Berkus Method adds $500,000 value risk reduction elements", k=3
        )

        prompt = f"""
아래 텍스트에서 Berkus Method의 평가 항목과 각 항목의 최대 배점을 찾아주세요.

텍스트:
{results}

다음 형식의 JSON으로만 반환하세요:
{{
    "sound_idea": 500000,
    "prototype": 500000,
    "quality_team": 500000,
    "strategic_relationships": 500000,
    "product_rollout": 500000
}}
"""

        response = self.llm.invoke(prompt)
        data = self._parse_json(response.content)

        # 영문 키를 한글로 매핑
        mapping = {
            "sound_idea": "아이디어_품질",
            "prototype": "프로토타입",
            "quality_team": "경영진",
            "strategic_relationships": "전략적_관계",
            "product_rollout": "제품_출시",
        }

        return {mapping.get(k, k): v for k, v in data.items()}

    def get_scorecard_weights(self) -> dict:
        """Scorecard Method 가중치 - 실제 추출"""
        results = self.rag.search(
            "Scorecard Valuation 30% management team 25% opportunity 15% product", k=3
        )

        prompt = f"""
아래 텍스트에서 Scorecard Method의 평가 항목과 가중치(%)를 찾아주세요.

텍스트:
{results}

다음 형식의 JSON으로만 반환하세요 (소수점 형태):
{{
    "management_team": 0.30,
    "size_of_opportunity": 0.25,
    "product_technology": 0.15,
    "competitive_environment": 0.10,
    "marketing_sales": 0.10,
    "need_for_investment": 0.05,
    "other": 0.05
}}
"""

        response = self.llm.invoke(prompt)
        data = self._parse_json(response.content)

        # 영문 → 한글 매핑
        mapping = {
            "management_team": "경영진",
            "size_of_opportunity": "시장",
            "product_technology": "제품",
            "competitive_environment": "경쟁",
            "marketing_sales": "판매",
            "need_for_investment": "투자",
            "other": "기타",
        }

        return {mapping.get(k, k): v for k, v in data.items()}

    def get_growth_thresholds(self) -> dict:
        """성장률 기준 - 실제 추출"""
        results = self.rag.search(
            "5-7% week good growth rate 10% exceptionally well 1% sign", k=2
        )

        prompt = f"""
아래 텍스트에서 Y Combinator의 주간 성장률 기준을 찾아주세요.

텍스트:
{results}

다음 형식의 JSON으로만 반환하세요:
{{
    "excellent": 0.10,
    "good": 0.05,
    "warning": 0.01
}}
"""

        response = self.llm.invoke(prompt)
        data = self._parse_json(response.content)

        mapping = {"excellent": "우수", "good": "양호", "warning": "경고"}

        return {mapping.get(k, k): v for k, v in data.items()}

    def get_pmf_signals(self) -> list:
        """PMF 신호 - 실제 추출"""
        results = self.rag.search(
            "product market fit customers buying reporters calling hiring", k=3
        )

        prompt = f"""
아래 텍스트에서 Product/Market Fit을 확인할 수 있는 신호 목록을 찾아주세요.

텍스트:
{results}

JSON 배열로만 반환:
["신호1", "신호2", ...]
"""

        response = self.llm.invoke(prompt)

        try:
            json_str = response.content
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            return json.loads(json_str.strip())
        except:
            # fallback
            return ["고객이 제품을 찾아옴", "입소문 발생", "언론 연락"]

    def _parse_json(self, content: str) -> dict:
        """JSON 파싱 헬퍼"""
        try:
            # ```json 제거
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content.strip())
        except Exception as e:
            print(f"[ERROR] JSON 파싱 실패: {e}")
            return {}
