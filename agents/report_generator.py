"""
Agent: 보고서 생성 (Report Generator)

모든 분석 결과를 종합하여 투자 평가 보고서를 생성합니다.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# .env 로드
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")


class ReportGenerator:
    """보고서 생성 에이전트"""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """보고서 생성 실행"""
        company = state.get("profile", {}).get("name", "Unknown")

        print(f"\n{'='*80}")
        print(f"📝 [보고서 생성] {company}")
        print(f"{'='*80}")

        # 보고서 섹션 생성
        report_text = self._generate_report(state)

        # 텍스트 파일 저장
        report_path = self._save_report(company, report_text)

        print(f"\n✅ 보고서 생성 완료")
        print(f"   텍스트: {report_path}")

        # PDF 파일 생성 (ReportLab)
        pdf_path = None
        if REPORTLAB_AVAILABLE:
            try:
                pdf_path = self._save_report_pdf_reportlab(company, state)
                print(f"   PDF: {pdf_path}")
            except Exception as e:
                print(f"   ⚠️ PDF 생성 실패: {e}")

        # State 업데이트
        result = {
            "report": {
                "text": report_text,
                "path": str(report_path),
                "pdf_path": str(pdf_path) if pdf_path else None,
            }
        }

        return result

    def _generate_report(self, state: Dict[str, Any]) -> str:
        """보고서 텍스트 생성"""
        sections = []

        # 1. 표지
        sections.append(self._section_cover(state))

        # 2. Executive Summary
        sections.append(self._section_summary(state))

        # 3. 기업 개요
        sections.append(self._section_profile(state))

        # 4. 기술 분석 (팀 평가 포함)
        sections.append(self._section_tech(state))

        # 5. 시장 분석
        sections.append(self._section_market(state))

        # 6. 생존성 분석 - 제거됨 (SurvivalAnalyzer 제거)
        # sections.append(self._section_survival(state))

        # 7. 경쟁사 비교
        sections.append(self._section_competition(state))

        # 8. 성장성 분석
        sections.append(self._section_growth(state))

        # 9. 종합 점수
        sections.append(self._section_score(state))

        # 10. 투자 판단
        sections.append(self._section_decision(state))

        return "\n\n".join(sections)

    def _section_cover(self, state: Dict[str, Any]) -> str:
        """표지"""
        company = state.get("profile", {}).get("name", "Unknown")
        now = datetime.now().strftime("%Y년 %m월 %d일")

        return f"""
{'='*80}
투자 평가 보고서
{'='*80}

기업명: {company}
작성일: {now}
평가 시스템: AI 스타트업 투자 평가 에이전트

{'='*80}
"""

    def _section_summary(self, state: Dict[str, Any]) -> str:
        """Executive Summary"""
        decision = state.get("decision", {})
        score = decision.get("final_score", 0)
        grade = decision.get("grade", "N/A")
        recommendation = decision.get("decision", "N/A")

        return f"""
## Executive Summary

**최종 등급**: {grade}
**최종 점수**: {score}/100
**투자 추천**: {recommendation}

### 핵심 요약
{self._get_key_highlights(state)}
"""

    def _get_key_highlights(self, state: Dict[str, Any]) -> str:
        """핵심 하이라이트"""
        highlights = []

        tech = state.get("tech_analysis", {})
        if tech.get("trl_level"):
            highlights.append(f"- 기술 성숙도 TRL {tech['trl_level']}")

        market = state.get("market_analysis", {})
        tam = market.get("tam_sam_som", {}).get("TAM")
        if tam:
            highlights.append(f"- 시장 규모 TAM ${tam}B")

        decision = state.get("decision", {})
        risk = decision.get("risk_level")
        if risk:
            highlights.append(f"- 투자 위험도: {risk}")

        return "\n".join(highlights) if highlights else "- 정보 부족"

    def _section_profile(self, state: Dict[str, Any]) -> str:
        """기업 개요"""
        profile = state.get("profile", {})
        space = state.get("space", {})
        funding = state.get("funding", {})

        name = profile.get("name", "N/A")
        founded = profile.get("founded_year", "N/A")
        description = profile.get("business_description", "N/A")
        tech = ", ".join(space.get("main_technology", [])[:3]) or "N/A"
        stage = funding.get("stage", "N/A")
        total_funding = funding.get("total_funding_krw", "N/A")

        return f"""
## 1. 기업 개요

**기업명**: {name}
**설립연도**: {founded}
**사업 내용**: {description}
**핵심 기술**: {tech}
**투자 단계**: {stage}
**누적 투자**: {total_funding}억원
"""

    def _section_tech(self, state: Dict[str, Any]) -> str:
        """기술 분석"""
        # InvestmentState의 'space' 키에서 읽기 (fallback: tech_analysis)
        tech = state.get("space", {}) or state.get("tech_analysis", {})
        trl = tech.get("trl_level", "N/A")
        patents = len(tech.get("patents", []))
        core_tech = ", ".join(tech.get("core_technology", [])[:3]) or "N/A"
        summary = tech.get("summary", "분석 결과 없음")
        score = tech.get("score", 0)

        return f"""
## 2. 기술 분석

**TRL**: {trl}
**특허**: {patents}건
**핵심 기술**: {core_tech}
**점수**: {score}/100

### 상세 분석
{summary}
"""

    def _section_market(self, state: Dict[str, Any]) -> str:
        """시장 분석"""
        # InvestmentState의 'market' 키에서 읽기
        market = state.get("market", {})

        tam_sam_som = market.get("tam_sam_som", {})
        growth_rate = market.get("growth_rate")
        pmf_signals = market.get("pmf_signals", [])
        summary = market.get("summary", "분석 결과 없음")
        score = market.get("score", 0)

        tam = tam_sam_som.get("TAM", "N/A")
        sam = tam_sam_som.get("SAM", "N/A")
        som = tam_sam_som.get("SOM", "N/A")
        growth = f"{growth_rate*100:.1f}%" if growth_rate else "N/A"
        pmf_count = len(pmf_signals)

        return f"""
## 3. 시장 분석

**TAM**: ${tam}B
**SAM**: ${sam}B
**SOM**: ${som}B
**시장 성장률**: {growth}
**PMF 신호**: {pmf_count}개
**점수**: {score}/100

### 상세 분석
{summary}
"""

    def _section_survival(self, state: Dict[str, Any]) -> str:
        """생존성 분석"""
        survival = state.get("survival_analysis", {})
        financial = survival.get("financial", {})
        funding_history = survival.get("funding_history", [])
        team_info = survival.get("team_info", {})
        risks = survival.get("risks", [])
        summary = survival.get("summary", "분석 결과 없음")
        score = survival.get("score", 0)

        runway = financial.get("runway_months", "N/A")
        funding_count = len(funding_history)
        team_size = team_info.get("team_size", "N/A")
        risk_count = len(risks)

        return f"""
## 4. 생존성 분석

**Runway**: {runway}개월
**투자 이력**: {funding_count}건
**팀 규모**: {team_size}명
**리스크**: {risk_count}개
**점수**: {score}/100

### 상세 분석
{summary}
"""

    def _section_competition(self, state: Dict[str, Any]) -> str:
        """경쟁사 비교"""
        competitors = state.get("competitors", [])
        comparison = state.get("comparison", {})
        our_strengths = comparison.get("our_strengths", [])
        our_weaknesses = comparison.get("our_weaknesses", [])
        narrative = comparison.get("narrative", "비교 분석 결과 없음")

        comp_names = (
            ", ".join([c.get("name", "N/A") for c in competitors[:3]]) or "없음"
        )
        strength_text = "\n".join([f"- {s}" for s in our_strengths[:3]]) or "- 없음"
        weakness_text = "\n".join([f"- {w}" for w in our_weaknesses[:3]]) or "- 없음"

        return f"""
## 5. 경쟁사 비교

**경쟁사**: {comp_names}

### 우리의 강점
{strength_text}

### 우리의 약점
{weakness_text}

### 상세 분석
{narrative}
"""

    def _section_growth(self, state: Dict[str, Any]) -> str:
        """성장성 분석"""
        growth = state.get("growth", {})
        analysis = growth.get("analysis", {})
        summary = analysis.get("summary", "분석 결과 없음")
        score = growth.get("score", 0)

        revenue_2023 = analysis.get("revenue_2023", "N/A")
        revenue_2024 = analysis.get("revenue_2024", "N/A")
        growth_rate = analysis.get("growth_rate")
        growth_rate_text = f"{growth_rate*100:.1f}%" if growth_rate else "N/A"

        return f"""
## 6. 성장성 분석

**매출 (2023)**: {revenue_2023}억원
**매출 (2024)**: {revenue_2024}억원
**성장률**: {growth_rate_text}
**점수**: {score}/100

### 상세 분석
{summary}
"""

    def _section_score(self, state: Dict[str, Any]) -> str:
        """종합 점수"""
        score_breakdown = state.get("score_breakdown", {})
        berkus = score_breakdown.get("berkus", 0)
        scorecard = score_breakdown.get("scorecard", 0)
        final = score_breakdown.get("final", 0)

        return f"""
## 7. 종합 점수

**Berkus Method**: {berkus}/100
**Scorecard Method**: {scorecard}/100
**최종 점수**: {final}/100

### 평가 방법론
- Berkus Method (40%): 정성적 평가
- Scorecard Method (60%): 가중치 기반 평가
"""

    def _section_decision(self, state: Dict[str, Any]) -> str:
        """투자 판단"""
        decision = state.get("decision", {})
        grade = decision.get("grade", "N/A")
        recommendation = decision.get("decision", "N/A")
        risk_level = decision.get("risk_level", "N/A")
        reasons = decision.get("reasons", [])
        warnings = decision.get("warnings", [])

        reason_text = "\n".join([f"- {r}" for r in reasons[:5]]) or "- 없음"
        warning_text = "\n".join([f"- {w}" for w in warnings[:5]]) or "- 없음"

        return f"""
## 8. 투자 판단

**최종 등급**: {grade}
**투자 결정**: {recommendation}
**위험도**: {risk_level}

### 투자 사유
{reason_text}

### 주의사항
{warning_text}

{'='*80}
보고서 끝
{'='*80}
"""

    def _save_report(self, company: str, report_text: str) -> Path:
        """보고서 파일 저장"""
        reports_dir = project_root / "reports"
        reports_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{company}_{timestamp}_report.txt"
        report_path = reports_dir / filename

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)

        return report_path

    def _save_report_pdf_reportlab(self, company: str, state: Dict[str, Any]) -> Path:
        """PDF 보고서 저장 (ReportLab - 한글 지원 + 검색 결과 포함)"""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab 패키지가 필요합니다: pip install reportlab")

        reports_dir = project_root / "reports"
        reports_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{company}_{timestamp}_report.pdf"
        pdf_path = reports_dir / filename

        # PDF 문서 생성
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # 스타일 정의 (한글 지원 위해 기본 폰트 사용)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )

        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            fontName='Helvetica'
        )

        # PDF 요소들
        story = []

        # 1. 제목 페이지
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(f"Investment Evaluation Report", title_style))
        story.append(Paragraph(f"{company}", heading_style))
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
        story.append(Spacer(1, 1*cm))

        # 2. Executive Summary
        decision = state.get("decision", {})
        story.append(Paragraph("Executive Summary", heading_style))

        summary_data = [
            ['Final Grade', decision.get('grade', 'N/A')],
            ['Investment Decision', decision.get('decision', 'N/A')],
            ['Risk Level', decision.get('risk_level', 'N/A')],
            ['Final Score', f"{decision.get('final_score', 0)}/100"]
        ]

        summary_table = Table(summary_data, colWidths=[8*cm, 8*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.5*cm))

        # 3. Technology & Team Analysis
        tech = state.get("space", {}) or state.get("tech_analysis", {})
        story.append(Paragraph("Technology & Team Analysis", heading_style))

        tech_data = [
            ['TRL Level', str(tech.get('trl_level', 'N/A'))],
            ['Patents', f"{len(tech.get('patents', []))} items"],
            ['Core Technology', ', '.join(tech.get('core_technology', [])[:3]) or 'N/A'],
            ['Tech Score', f"{tech.get('score', 0)}/100"]
        ]

        tech_table = Table(tech_data, colWidths=[8*cm, 8*cm])
        tech_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4f8')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(tech_table)

        # Tech summary 추가 (검색 결과)
        tech_summary = tech.get('summary', '')
        if tech_summary and len(tech_summary) > 50:
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph("<b>Analysis Summary:</b>", body_style))
            # 요약을 짧게 자르기 (PDF에 맞게)
            summary_lines = tech_summary.split('\n')[:15]  # 처음 15줄만
            for line in summary_lines:
                if line.strip():
                    clean_line = line.replace('**', '').replace('#', '').strip()
                    if clean_line:
                        story.append(Paragraph(f"• {clean_line[:100]}", body_style))

        story.append(Spacer(1, 0.5*cm))

        # 4. Market Analysis
        market = state.get("market", {})
        tam_sam_som = market.get("tam_sam_som", {})
        story.append(Paragraph("Market Analysis", heading_style))

        growth_rate = market.get("growth_rate")
        growth_text = f"{growth_rate*100:.1f}%" if growth_rate else "N/A"

        market_data = [
            ['TAM', f"${tam_sam_som.get('TAM', 'N/A')}B"],
            ['SAM', f"${tam_sam_som.get('SAM', 'N/A')}B"],
            ['SOM', f"${tam_sam_som.get('SOM', 'N/A')}B"],
            ['Growth Rate', growth_text],
            ['PMF Signals', f"{len(market.get('pmf_signals', []))} signals"],
            ['Market Score', f"{market.get('score', 0)}/100"]
        ]

        market_table = Table(market_data, colWidths=[8*cm, 8*cm])
        market_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fef5e7')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(market_table)

        # Market summary 추가 (검색 결과)
        market_summary = market.get('summary', '')
        if market_summary and len(market_summary) > 50:
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph("<b>Market Insights:</b>", body_style))
            summary_lines = market_summary.split('\n')[:10]
            for line in summary_lines:
                if line.strip():
                    clean_line = line.replace('**', '').replace('#', '').strip()
                    if clean_line:
                        story.append(Paragraph(f"• {clean_line[:100]}", body_style))

        story.append(Spacer(1, 0.5*cm))

        # 5. Investment Reasons & Warnings
        story.append(Paragraph("Investment Analysis", heading_style))

        reasons = decision.get('reasons', [])
        warnings = decision.get('warnings', [])

        if reasons:
            story.append(Paragraph("<b>Investment Strengths:</b>", body_style))
            for reason in reasons[:5]:
                story.append(Paragraph(f"✓ {reason}", body_style))
            story.append(Spacer(1, 0.3*cm))

        if warnings:
            story.append(Paragraph("<b>Risk Factors:</b>", body_style))
            for warning in warnings[:5]:
                story.append(Paragraph(f"⚠ {warning}", body_style))

        # PDF 생성
        doc.build(story)

        return pdf_path


def _demo():
    """데모 실행"""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from graph.state import create_initial_state

    state = create_initial_state()
    state["profile"] = {
        "name": "나라스페이스",
        "founded_year": 2016,
        "business_description": "큐브위성 개발",
    }
    state["space"] = {"main_technology": ["AI", "큐브위성"]}
    state["funding"] = {"stage": "Series A", "total_funding_krw": 50}
    state["tech_analysis"] = {
        "trl_level": 9,
        "patents": [],
        "core_technology": ["AI"],
        "summary": "기술 성숙도 높음",
        "score": 70,
    }
    state["market_analysis"] = {
        "tam_sam_som": {"TAM": 100},
        "growth_rate": 0.15,
        "pmf_signals": ["신호1"],
        "summary": "시장 전망 양호",
        "score": 65,
    }
    state["survival_analysis"] = {
        "financial": {"runway_months": 18},
        "funding_history": [{}],
        "team_info": {"team_size": 25},
        "risks": [],
        "summary": "생존성 양호",
        "score": 60,
    }
    state["competitors"] = [{"name": "경쟁사A"}]
    state["comparison"] = {
        "our_strengths": ["강점1"],
        "our_weaknesses": ["약점1"],
        "narrative": "경쟁 우위",
    }
    state["growth"] = {"analysis": {"summary": "성장성 양호"}, "score": 65}
    state["score"] = 78.5
    state["score_breakdown"] = {"berkus": 75, "scorecard": 80, "final": 78.5}
    state["decision"] = {
        "grade": "A",
        "decision": "적극 투자 추천",
        "risk_level": "낮음",
        "final_score": 78.5,
        "reasons": ["이유1", "이유2"],
        "warnings": ["주의1"],
    }

    generator = ReportGenerator()
    result = generator.run(state)

    print("\n" + "=" * 80)
    print("📊 최종 결과")
    print("=" * 80)
    print(f"보고서 저장: {result['report']['path']}")


if __name__ == "__main__":
    _demo()
