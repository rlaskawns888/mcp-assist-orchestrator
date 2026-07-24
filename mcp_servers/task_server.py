import json
import os
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# 이 파일이 있는 폴더에 tasks.json 저장
DATA_FILE = os.path.join(os.path.dirname(__file__), "tasks.json")

mcp = FastMCP("task-server")


def _load_tasks() -> list[dict]:
    """저장된 할일 목록을 파일에서 불러온다. 파일이 없으면 빈 리스트."""
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_tasks(tasks: list[dict]) -> None:
    """할일 목록을 파일에 저장한다."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def _next_id(tasks: list[dict]) -> int:
    """새 할일에 부여할 다음 id를 계산."""
    return max([t["id"] for t in tasks], default=0) + 1


@mcp.tool()
def add_task(title: str) -> str:
    """새로운 할일을 추가한다.

    Args:
        title: 할일 내용 (예: "보고서 작성하기")
    """
    tasks = _load_tasks()
    task = {
        "id": _next_id(tasks),
        "title": title,
        "done": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    tasks.append(task)
    _save_tasks(tasks)
    return f"할일 추가됨 (id={task['id']}): {title}"


if __name__ == "__main__":
    mcp.run(transport="stdio")