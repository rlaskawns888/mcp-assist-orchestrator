import asyncio
from datetime import date
from typing import Optional, Annotated

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler  


#State에 approved 필드 추가
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    approved: Optional[bool] # None=판단 전, True=승인, False=거부


# 위험한 도구 목록 (실행 전 확인)
DANGEROUS_TOOLS = {"delete_task", "delete_event"}


SYSTEM_PROMPT = (
    "너는 사용자의 할일과 일정을 관리해주는 개인 비서다. "
    "사용자가 요청하면 반드시 제공된 도구를 호출해서 처리해라. "
    "할일 관련 요청은 task 관련 도구를, 캘린더 일정 관련 요청은 event 관련 도구를 사용해라. "
    "도구 실행 중 오류가 발생하면 사용자에게 친절하게 안내하고 다시 시도를 권유해라. "
    f"오늘 날짜는 {date.today().isoformat()}이다."
)


THREAD_ID = "default-session"


def make_agent_node(model, tools):
    """ agent노드 - LLM이 메세지를 보고 뭘 할지 판단 """
    model_with_tools = model.bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        last_error = None

        for attempt in range(3): #최대 3번 시도
            try:
                resp = model_with_tools.invoke(
                    [{"role":"system", "content":SYSTEM_PROMPT}] + state["messages"]
                )

                return {"messages":[resp], "approved": None}

            except Exception as e:
                last_error = e
                if attempt < 2:
                    import time
                    time.sleep(2 ** attempt)  # 1초, 2초 대기 후 재시도 (exponential backoff)
                    continue
        #3번 실패 
        raise last_error

    return agent_node


def should_continue(state: AgentState) -> str:
    """ 도구 호출(o): is_dangerouse, (x) -> END """
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "is_dangerous"
    return "end"


def is_dangerous(state: AgentState) -> str:
    """엣지 함수 — 위험한 도구면 human_review로, 안전하면 tools로"""
    last = state["messages"][-1]
    for tool_call in last.tool_calls:
        if tool_call["name"] in DANGEROUS_TOOLS:
            return "human_review"
    return "tools"


def human_review_node(state: AgentState) -> dict:
    #interrupt 발생 시, 사람 확인 대기
    from langgraph.types import interrupt  

    last = state["messages"][-1]
    tool_calls_info = [f"{tc['name']}({tc['args']})" for tc in last.tool_calls]
    decision = interrupt({
        "message": f"위험한 작업 요청됨: {', '.join(tool_calls_info)}\n승인하시겠습니까? (yes/no)"
    })

    if decision.lower() == "yes":
        return Command(goto="tools", update={"approved": True})
    else:
        last = state["messages"][-1]
        # ToolMessage로 각 tool_call에 응답 + AIMessage로 취소 안내
        cancel_messages = [
            ToolMessage(
                content="사용자가 작업을 취소했습니다.",
                tool_call_id=tc["id"]
            )
            for tc in last.tool_calls
        ] + [AIMessage(content="작업이 취소되었습니다.")]

        return Command(
            goto=END,
            update={
                "messages": cancel_messages,
                "approved": False
            }
        )            

# def after_human_review(state: AgentState) -> str:
#     print(f"[DEBUG] approved: {state.get('approved')}")
#     if state.get("approved") is False:
#         return "agent"
#     return "tools"


def build_graph(model, tools):
    """ 노드들을 엣지로 연결해서 그래프 완성 """
    tool_node = ToolNode(tools)
    agent_node = make_agent_node(model, tools)

    graph = StateGraph(AgentState)

    #노드 등록
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("is_dangerous_check", lambda state: {})
    graph.add_node("human_review", human_review_node)

    #엣지 연결
    graph.add_edge(START, "agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"is_dangerous": "is_dangerous_check", "end":END}
    )
    graph.add_conditional_edges(
        "is_dangerous_check",
        is_dangerous,
        {"human_review": "human_review", "tools": "tools"}
    )
    # graph.add_conditional_edges(
    #     "human_review",
    #     after_human_review,
    #     {"agent": "agent", "tools": "tools"}
    # )
    #tools -> agent(루프)
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=MemorySaver())


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
    graph = build_graph(model, tools)

    #Langfuse 콜백 핸들러 생성
    langfuse_handler = CallbackHandler()
    config={
        "configurable": {"thread_id": THREAD_ID},
        "callbacks": [langfuse_handler],
        "recursion_limit": 10, #최대 10번 노드 실행(무한 루프 방지)

    }

    print(f"도구 {len(tools)}개 로드됨: {[t.name for t in tools]}")
    print("개인 비서 시작 — 종료하려면 'exit' 입력\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("종료합니다.")
            break
        if not user_input:
            continue

        try:
            #Langfuse
            with propagate_attributes(session_id=THREAD_ID, user_id="local-user"):
                result = await graph.ainvoke(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config=config
                )
    
            # interrupt가 발생했는지 확인
            state = await graph.aget_state(config)
            interrupted = any(
                task.interrupts
                for task in state.tasks
                if hasattr(task, "interrupts")
            )
    
            # print(f"[DEBUG] state.next: {state.next}")
            # print(f"[DEBUG] state.tasks: {state.tasks}")
    
            if interrupted:
                for task in state.tasks:
                    if hasattr(task, "interrupts") and task.interrupts:
                        print(f"\nAgent: {task.interrupts[0].value['message']}")
                        break
    
                approval = input("You: ").strip().lower()
    
                with propagate_attributes(session_id=THREAD_ID, user_id="local-user"):
                    result = await graph.ainvoke(
                        Command(resume=approval),
                        config=config
                    )
                
            print(f"Agent: {result['messages'][-1].content}\n")

        except KeyboardInterrupt:
            print("\n종료합니다.")
            break
        except Exception as e:
            if "GraphRecursionError" in type(e).__name__ or "recursion" in str(e).lower():
                print("Agent: 요청을 처리하는 데 너무 많은 단계가 필요합니다. 더 구체적으로 말씀해주세요.\n")
            else:
                print(f"Agent: 오류가 발생했습니다. 다시 시도해주세요. ({type(e).__name__})\n")
        continue

asyncio.run(main())
