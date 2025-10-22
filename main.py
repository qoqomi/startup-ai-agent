# main.py
from graph.workflow import create_workflow
from graph.state import create_initial_state


def main():
    print("=" * 60)
    print("스타트업 투자 분석 시스템")
    print("=" * 60)

    # 워크플로우 생성
    workflow = create_workflow()

    # 실행
    query = "AI 핀테크 스타트업"
    initial_state = create_initial_state(query)

    result = workflow.invoke(initial_state)

    # 결과 출력
    print("\n" + "=" * 60)
    print(result["report"])
    print("=" * 60)


if __name__ == "__main__":
    main()
