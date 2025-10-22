"""
에이전트 개별 테스트 스크립트
각 에이전트를 독립적으로 테스트합니다.
"""

import sys
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()


def test_candidate_agent():
    """후보 선택 에이전트 테스트"""
    print("\n" + "=" * 60)
    print("🧪 후보 선택 에이전트 테스트")
    print("=" * 60)

    try:
        from agents.candidate_selector import run

        test_state = {"query": "AI 핀테크 스타트업"}
        result = run(test_state)

        print("\n✅ 테스트 성공")
        print(f"후보 수: {len(result.get('candidates', []))}")
        print(f"검색 결과: {len(result.get('search_results', []))}개")

        if result.get("candidates"):
            print("\n선택된 후보:")
            for i, c in enumerate(result["candidates"][:3], 1):
                print(f"  {i}. {c['name']}")
                print(f"     카테고리: {c.get('category', 'N/A')}")
                print(f"     관련성: {c.get('relevance_score', 0):.2f}")

        return True

    except ImportError as e:
        print(f"❌ 모듈 임포트 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_research_agent():
    """조사 에이전트 테스트"""
    print("\n" + "=" * 60)
    print("🧪 조사 에이전트 테스트")
    print("=" * 60)

    try:
        from agents.researcher import run

        test_state = {
            "query": "AI 핀테크 스타트업",
            "candidates": [
                {
                    "name": "테스트 스타트업",
                    "description": "AI 기반 금융 서비스",
                    "website": "https://example.com",
                    "category": "FinTech",
                }
            ],
        }
        result = run(test_state)

        print("\n✅ 테스트 성공")
        print(f"조사된 기업 수: {len(result.get('research_data', []))}")

        if result.get("research_data"):
            print("\n조사 결과 샘플:")
            data = result["research_data"][0]
            print(f"  기업: {data.get('company_name', 'N/A')}")
            print(f"  데이터 포인트: {len(data.get('data_points', []))}개")

        return True

    except ImportError as e:
        print(f"❌ 모듈 임포트 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_analyzer_agent():
    """분석 에이전트 테스트"""
    print("\n" + "=" * 60)
    print("🧪 분석 에이전트 테스트")
    print("=" * 60)

    try:
        from agents.analyzer import run

        test_state = {
            "query": "AI 핀테크 스타트업",
            "research_data": [
                {
                    "company_name": "테스트 스타트업",
                    "data_points": [
                        {
                            "category": "funding",
                            "content": "Series A $10M 투자 유치",
                            "source": "test",
                        },
                        {
                            "category": "team",
                            "content": "CEO: 전 Google 엔지니어",
                            "source": "test",
                        },
                    ],
                }
            ],
        }
        result = run(test_state)

        print("\n✅ 테스트 성공")
        print(f"분석 결과: {len(result.get('analysis', []))}개")

        if result.get("analysis"):
            analysis = result["analysis"][0]
            print(f"\n기업: {analysis.get('company_name', 'N/A')}")
            print(f"투자 점수: {analysis.get('investment_score', 0):.1f}/10")
            print(f"추천: {analysis.get('recommendation', 'N/A')}")

        return True

    except ImportError as e:
        print(f"❌ 모듈 임포트 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_report_agent():
    """보고서 생성 에이전트 테스트"""
    print("\n" + "=" * 60)
    print("🧪 보고서 생성 에이전트 테스트")
    print("=" * 60)

    try:
        from agents.report_generator import run

        test_state = {
            "query": "AI 핀테크 스타트업",
            "analysis": [
                {
                    "company_name": "테스트 스타트업",
                    "investment_score": 8.5,
                    "recommendation": "투자 권장",
                    "strengths": ["강력한 팀", "혁신적 기술"],
                    "weaknesses": ["제한적 시장"],
                    "risks": ["경쟁 심화"],
                }
            ],
        }
        result = run(test_state)

        print("\n✅ 테스트 성공")
        report = result.get("final_report", "")
        print(f"보고서 길이: {len(report)}자")
        if report:
            print(f"\n보고서 미리보기:\n{report[:200]}...")

        return True

    except ImportError as e:
        print(f"❌ 모듈 임포트 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_environment():
    """환경 설정 확인"""
    print("\n" + "=" * 60)
    print("🔧 환경 설정 확인")
    print("=" * 60)

    required_keys = ["OPENAI_API_KEY", "TAVILY_API_KEY"]
    missing_keys = []

    for key in required_keys:
        if os.getenv(key):
            print(f"✅ {key}: 설정됨")
        else:
            print(f"❌ {key}: 없음")
            missing_keys.append(key)

    if missing_keys:
        print(f"\n⚠️  누락된 환경변수: {', '.join(missing_keys)}")
        print("일부 테스트가 제한될 수 있습니다.")
        return False

    return True


def main():
    """메인 테스트 실행"""
    print("\n🚀 에이전트 테스트 시작")

    # 환경 확인
    env_ok = check_environment()

    # 각 에이전트 테스트
    tests = [
        ("candidate_selector", test_candidate_agent),
        ("researcher", test_research_agent),
        ("analyzer", test_analyzer_agent),
        ("report_generator", test_report_agent),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except KeyboardInterrupt:
            print("\n\n⚠️  사용자에 의해 중단됨")
            sys.exit(1)

    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)

    for name, passed in results.items():
        status = "✅ 통과" if passed else "❌ 실패"
        print(f"{status} - {name}")

    total = len(results)
    passed = sum(results.values())
    print(f"\n총 {total}개 중 {passed}개 통과 ({passed/total*100:.0f}%)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="에이전트 개별 테스트")
    parser.add_argument(
        "--agent",
        choices=["candidate", "research", "analyzer", "report", "all"],
        default="all",
        help="테스트할 에이전트 선택",
    )

    args = parser.parse_args()

    if args.agent == "all":
        main()
    elif args.agent == "candidate":
        check_environment()
        test_candidate_agent()
    elif args.agent == "research":
        check_environment()
        test_research_agent()
    elif args.agent == "analyzer":
        check_environment()
        test_analyzer_agent()
    elif args.agent == "report":
        check_environment()
        test_report_agent()
