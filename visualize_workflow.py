"""
LangGraph Workflow 시각화
"""
from graph.workflow import create_workflow
from IPython.display import Image, display

# Workflow 생성
workflow = create_workflow()
app = workflow.compile()

# 그래프 시각화
try:
    # Mermaid 형식으로 출력
    print("Workflow Graph (Mermaid):")
    print("=" * 80)
    print(app.get_graph().draw_mermaid())
    print("=" * 80)

    # PNG 이미지로 저장 (graphviz 설치 필요)
    try:
        png_data = app.get_graph().draw_mermaid_png()
        with open("workflow_graph.png", "wb") as f:
            f.write(png_data)
        print("\n✅ PNG 이미지 저장: workflow_graph.png")
    except Exception as e:
        print(f"\n⚠️ PNG 생성 실패 (graphviz 필요): {e}")

except Exception as e:
    print(f"❌ 시각화 실패: {e}")

# ASCII 형식으로도 출력
print("\n\nWorkflow Structure:")
print("=" * 80)
print("""
┌─────────────────────┐
│ candidate_selection │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   tech_analysis     │ (기술 + 팀 평가)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  market_analysis    │ (시장 + ECOS API)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  growth_analysis    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ competitor_analysis │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      scoring        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      decision       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ report_generation   │ (ReportLab PDF)
└──────────┬──────────┘
           │
           ▼
         [END]
""")
print("=" * 80)

# State 구조 출력
print("\n\nInvestmentState Structure:")
print("=" * 80)
print("""
InvestmentState {
    profile: CandidateProfile         # 기업 기본 정보
    space: SpaceOperations            # 기술 + 팀 정보 (우주산업 특화)
    funding: FundingSnapshot          # 투자 및 파트너십
    growth: GrowthOutcome             # 성장성 분석
    market: MarketOutcome             # 시장 분석 (ECOS API 포함)
    competitor: CompetitorProfile     # 경쟁사 프로필
    comparison: ComparisonSummary     # 경쟁사 비교
    survival: SurvivalOutcome         # [제거됨 - 사용 안 함]
    decision: DecisionSummary         # 최종 의사결정
    report: ReportBundle              # 보고서 (텍스트 + PDF)
    meta: PipelineMeta                # 파이프라인 메타정보
}
""")
print("=" * 80)

# 각 노드별 입력/출력 키
print("\n\nNode Input/Output Keys:")
print("=" * 80)
print("""
1. candidate_selection
   Input:  -
   Output: candidates[], profile{name, description, founded_year}

2. tech_analysis (개선됨 - 팀 평가 포함)
   Input:  profile{name}
   Output: space{trl_level, patents[], core_technology[], summary, score}
           └─ summary에 팀 정보 포함 (CEO, CTO, 팀 규모, 역량)

3. market_analysis (개선됨 - ECOS API)
   Input:  profile{name}
   Output: market{tam_sam_som, growth_rate, pmf_signals[], summary, score, sector}
           └─ ECOS API로 실제 경제 지표 수집

4. growth_analysis
   Input:  profile{name}
   Output: growth{score, analysis{revenue, growth_rate, summary}}

5. competitor_analysis
   Input:  profile{name}, space, market
   Output: competitor{}, comparison{our_strengths[], our_weaknesses[]}

6. scoring
   Input:  space, market, growth, competitor
   Output: score_breakdown{berkus, scorecard, final}

7. decision
   Input:  score_breakdown, space, market, funding
   Output: decision{grade, decision, risk_level, reasons[], warnings[], final_score}

8. report_generation (개선됨 - ReportLab)
   Input:  모든 state 키
   Output: report{text, path, pdf_path}
           └─ ReportLab으로 전문적인 PDF 생성 (한글 지원)
""")
print("=" * 80)

# 주요 개선사항
print("\n\n주요 개선사항:")
print("=" * 80)
print("""
✅ SurvivalAnalyzer 제거
   - 정보 수집 불충분으로 제거
   - funding 데이터로 리스크 평가 대체

✅ TechAnalyzer 개선
   - 팀 평가 추가 (CEO, CTO, 팀 규모, 핵심 역량, 산업 경험)
   - 검색 쿼리 확장 (기술 + 팀)
   - 경쟁사 비교 테이블 추가

✅ MarketAnalyzer 개선
   - ECOS API 통합 (한국은행 경제 지표)
   - 실제 산업생산지수로 성장률 계산
   - 벤치마크 + 실제 데이터 조합

✅ PDF 생성 개선
   - fpdf2 → ReportLab 교체
   - 한글 지원 (파일명, 내용)
   - 전문적인 디자인 (컬러 테이블, 그리드)
   - 검색 결과 포함 (tech summary, market insights)

✅ State 키 정렬
   - 모든 Agent가 InvestmentState 키 사용
   - space (기술), market (시장) 일관성 유지
   - DecisionMaker에서 올바른 키로 데이터 읽기
""")
print("=" * 80)
