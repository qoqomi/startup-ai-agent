# rag/evaluation_rag.py (개선 버전)
from rag.rag_system import RAGSystem
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import json
import re

load_dotenv()


class EvaluationRAG:
    """평가 기준 RAG - 개선 버전"""

    def __init__(self):
        print("[INFO] 평가 기준 RAG 초기화 중...")
        self.rag = RAGSystem(doc_dir="documents")
        self.rag.build()
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def get_berkus_criteria(self) -> dict:
        """Berkus Method 기준 - 다각도 검색"""
        queries = [
            "Berkus Method adds $500,000 value risk reduction",
            "pre-revenue startup qualitative valuation five elements",
            "sound idea prototype quality team strategic relationships",
        ]

        all_results = []
        for q in queries:
            all_results.append(self.rag.search(q, k=2))

        combined = "\n\n---\n\n".join(all_results)

        # 결과 품질 체크
        if "Berkus" not in combined:
            print("[WARN] Berkus 키워드 미검출, fallback 사용")
            return self._get_berkus_fallback()

        prompt = f"""
아래 텍스트에서 Berkus Method의 평가 항목과 배점을 추출하세요.

텍스트:
{combined}

예시 입력:
"The Berkus Method adds up to $500,000 for each: sound idea, prototype, quality management team..."

예시 출력:
{{
    "sound_idea": 500000,
    "prototype": 500000,
    "quality_team": 500000,
    "strategic_relationships": 500000,
    "product_rollout": 500000
}}

이제 실제 텍스트를 분석하세요. JSON만 반환:
"""

        response = self.llm.invoke(prompt)
        data = self._parse_json(response.content, fallback=self._get_berkus_fallback())

        # 검증
        total = sum(data.values())
        if total != 2500000:
            print(f"[WARN] Berkus 합계 오류: {total}, 정규화 중...")
            factor = 2500000 / total
            data = {k: int(v * factor) for k, v in data.items()}

        # 영문 → 한글
        mapping = {
            "sound_idea": "아이디어_품질",
            "prototype": "프로토타입",
            "quality_team": "경영진",
            "strategic_relationships": "전략적_관계",
            "product_rollout": "제품_출시",
        }

        return {mapping.get(k, k): v for k, v in data.items()}

    def get_scorecard_weights(self) -> dict:
        """Scorecard Method 가중치 - 다각도 검색"""
        queries = [
            "Scorecard Valuation Method 30% management team 25% opportunity",
            "Bill Payne scorecard weighted factors pre-money valuation",
            "management product competitive environment marketing sales",
        ]

        all_results = []
        for q in queries:
            all_results.append(self.rag.search(q, k=2))

        combined = "\n\n---\n\n".join(all_results)

        prompt = f"""
아래 텍스트에서 Scorecard Method의 7개 평가 항목과 가중치(%)를 추출하세요.

텍스트:
{combined}

예시 입력:
"Scorecard: Management team (30%), Size of opportunity (25%), Product/Technology (15%)..."

예시 출력:
{{
    "management_team": 0.30,
    "size_of_opportunity": 0.25,
    "product_technology": 0.15,
    "competitive_environment": 0.10,
    "marketing_sales": 0.10,
    "need_for_investment": 0.05,
    "other": 0.05
}}

실제 텍스트 분석 결과를 JSON으로만 반환:
"""

        response = self.llm.invoke(prompt)
        data = self._parse_json(
            response.content, fallback=self._get_scorecard_fallback()
        )

        # 검증: 합이 1.0인지
        total = sum(data.values())
        if abs(total - 1.0) > 0.01:
            print(f"[WARN] Scorecard 가중치 합 오류: {total}, 정규화 중...")
            data = {k: v / total for k, v in data.items()}

        # 영문 → 한글
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
        """성장률 기준 - Paul Graham 에세이 기반"""
        queries = [
            "5-7% week good growth rate 10% exceptionally",
            "Y Combinator weekly growth benchmark startup",
            "1% weekly growth concerning sign problem",
        ]

        all_results = []
        for q in queries:
            all_results.append(self.rag.search(q, k=2))

        combined = "\n\n---\n\n".join(all_results)

        prompt = f"""
아래 Paul Graham 텍스트에서 주간 성장률 기준을 추출하세요.

텍스트:
{combined}

예시 입력:
"A good growth rate is 5-7% per week. 10% weekly is exceptionally good. 1% is a sign something is wrong."

예시 출력:
{{
    "excellent": 0.10,
    "good": 0.05,
    "warning": 0.01
}}

실제 텍스트 분석 결과를 JSON으로만 반환:
"""

        response = self.llm.invoke(prompt)
        data = self._parse_json(
            response.content,
            fallback={"excellent": 0.10, "good": 0.05, "warning": 0.01},
        )

        mapping = {"excellent": "우수", "good": "양호", "warning": "경고"}
        return {mapping.get(k, k): v for k, v in data.items()}

    def get_pmf_signals(self) -> list:
        """PMF 신호 - 다각도 검색"""
        queries = [
            "product market fit customers buying reporters calling",
            "PMF signals evidence strong demand organic growth",
            "hiring faster can't keep up orders backlog",
        ]

        all_results = []
        for q in queries:
            all_results.append(self.rag.search(q, k=2))

        combined = "\n\n---\n\n".join(all_results)

        prompt = f"""
아래 텍스트에서 Product/Market Fit의 신호 목록을 추출하세요.

텍스트:
{combined}

예시 입력:
"PMF signs: customers are buying, reporters are calling, you're hiring sales and support faster..."

예시 출력:
["고객이 제품을 찾아옴", "언론이 연락함", "채용이 급증함", "주문을 따라가지 못함"]

실제 텍스트 분석 결과를 JSON 배열로만 반환:
"""

        response = self.llm.invoke(prompt)

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            signals = json.loads(content.strip())

            if not signals or len(signals) < 3:
                print("[WARN] PMF 신호 부족, fallback 사용")
                return self._get_pmf_fallback()

            return signals

        except Exception as e:
            print(f"[ERROR] PMF 신호 파싱 실패: {e}")
            return self._get_pmf_fallback()

    def _parse_json(self, content: str, fallback: dict = None) -> dict:
        """JSON 파싱 - 강력한 에러 핸들링"""
        try:
            # 마크다운 제거
            content = re.sub(r"```(?:json)?\n?", "", content)
            content = content.strip()

            # 정규식으로 JSON 추출
            json_match = re.search(
                r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", content, re.DOTALL
            )
            if json_match:
                return json.loads(json_match.group())

            # 직접 파싱 시도
            return json.loads(content)

        except Exception as e:
            print(f"[ERROR] JSON 파싱 실패: {e}")
            if fallback:
                print(f"[WARN] Fallback 사용: {fallback}")
                return fallback
            raise ValueError(f"파싱 불가 & fallback 없음: {content[:200]}")

    # Fallback 메서드들
    def _get_berkus_fallback(self) -> dict:
        """Berkus 기본값"""
        return {
            "sound_idea": 500000,
            "prototype": 500000,
            "quality_team": 500000,
            "strategic_relationships": 500000,
            "product_rollout": 500000,
        }

    def _get_scorecard_fallback(self) -> dict:
        """Scorecard 기본값"""
        return {
            "management_team": 0.30,
            "size_of_opportunity": 0.25,
            "product_technology": 0.15,
            "competitive_environment": 0.10,
            "marketing_sales": 0.10,
            "need_for_investment": 0.05,
            "other": 0.05,
        }

    def _get_pmf_fallback(self) -> list:
        """PMF 신호 기본값"""
        return [
            "고객이 제품을 찾아옴",
            "언론이 연락함",
            "입소문이 발생함",
            "채용 수요 급증",
            "주문 폭주",
        ]
