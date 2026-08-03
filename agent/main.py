import asyncio
import os
from datetime import date

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent


SYSTEM_PROMPT = (
    "너는 사용자의 할일과 일정을 관리해주는 개인 비서다. "
    "사용자가 요청하면 반드시 제공된 도구를 호출해서 처리해라. "
    "할일 관련 요청은 task 관련 도구를, 캘린더 일정 관련 요청은 event 관련 도구를 사용해라. "
    f"오늘 날짜는 {date.today().isoformat()}이다."
)


async def main():
    client = MultiServerMCPClient({
        "task-server": {
            "command": "python3",
            "args": ["mcp_servers/task_server.py"],
            "transport": "stdio",
        },
        "calendar-server": {
            "command": "python3",
            "args": ["mcp_servers/calendar_server.py"],
            "transport": "stdio",
        },
    })
    tools = await client.get_tools()
    model = ChatOpenAI(model="gpt-4o-mini")
    agent = create_react_agent(model, tools, prompt=SYSTEM_PROMPT)
    print(f"도구 {len(tools)}개 로드됨: {[t.name for t in tools]}")
    print("개인 비서 시작 — 종료하려면 'exit' 입력\n")


    #챗 루프 
    while True:
        user_ipt = input("You: ").strip()

        if user_ipt.lower() in ("exit", "quit"):
            print("종료합니다.")
            break

        if not user_ipt:
            continue
 
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": user_ipt}]
        })

        print(f"Agent: {result['messages'][-1].content}\n")

        # 전체 흐름 출력 (디버깅용)
        # for msg in result["messages"]:
        #     print(f"[{type(msg).__name__}] {msg.content if msg.content else '(비어있음)'}")
        #     if hasattr(msg, "tool_calls") and msg.tool_calls:
        #         print(f"→ 도구 호출: {msg.tool_calls}")
        # print()


asyncio.run(main())
