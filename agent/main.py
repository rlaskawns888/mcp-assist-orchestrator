import asyncio
import os

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

SYSTEM_PROMPT = (
    "너는 사용자의 할일 관리를 도와주는 비서다. "
    "사용자가 할일 관련 요청을 하면 반드시 제공된 도구를 호출해서 처리해라. "
    "도구를 부르지 않고 자연어로만 답하지 마라."
)

async def main():
    client = MultiServerMCPClient({
        "task-server": {
            "command": "python3",
            "args": ["mcp_servers/task_server.py"],
            "transport":"stdio",
        }
    })
    tools = await client.get_tools()
    print(f"연결된 도구 개수: {len(tools)}")
    for t in tools:
        print(f"  - {t.name}")

    model = ChatOpenAI(model="gpt-4o-mini")
    agent = create_react_agent(model, tools, prompt=SYSTEM_PROMPT)

    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": "보고서 작성하기 할일 추가해줘"}]
    })

    # 전체 메시지 흐름 출력
    print("\n=== 대화 흐름 ===")
    for msg in result["messages"]:
        print(f"\n[{type(msg).__name__}]")
        content = msg.content if msg.content else "(비어있음)"
        print(content)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"→ 도구 호출: {msg.tool_calls}")

asyncio.run(main())