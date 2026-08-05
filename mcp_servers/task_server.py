import json
import os
from datetime import datetime

from mcp.server.fastmcp import FastMCP

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
def add_task(title: str, priority: str = "medium") -> str:
    """새로운 할일을 추가한다.

    Args:
        title: 할일 내용 (예: "보고서 작성하기")
        priority: 우선순위. "high", "medium", "low" 중 하나. 기본값 medium.
    """
    tasks = _load_tasks()
    task = {
        "id": _next_id(tasks),
        "title": title,
        "priority": priority,
        "done": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    tasks.append(task)
    _save_tasks(tasks)
    return f"할일 추가됨 (id={task['id']}): {title} [{priority}]"


@mcp.tool()
def list_task(include_done: bool = False) -> str:
    """할일 목록을 조회한다.

    Args:
        include_done: True면 완료된 항목도 포함. 기본값 False (미완료만).
    """
    tasks = _load_tasks()
    if not include_done:
        tasks = [t for t in tasks if not t["done"]]

    if not tasks:
        return "할일이 없습니다."

    lines = []
    for t in tasks:
        status = "완료" if t["done"] else "진행중"
        lines.append(f"[{t['id']}] {t['title']} (우선순위: {t['priority']}, 상태: {status})")
    return "\n".join(lines)


@mcp.tool()
def complete_task(task_id: int) -> str:
    """지정한 id의 할일을 완료 처리한다.

    Args:
        task_id: list_tasks로 조회한 할일의 id 번호
    """
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["done"] = True
            _save_tasks(tasks)
            return f"완료 처리됨: [{t['id']}] {t['title']}"
    return f"id={task_id}인 할일을 찾을 수 없습니다."


@mcp.tool()
def delete_task(task_id: int) -> str:
    """지정한 id의 할일을 영구 삭제한다. 되돌릴 수 없으니 신중히 사용한다.

    Args:
        task_id: list_tasks로 조회한 할일의 id 번호
    """
    tasks = _load_tasks()
    target = next((t for t in tasks if t["id"] == task_id), None)
    if target is None:
        return f"id={task_id}인 할일을 찾을 수 없습니다."
    tasks = [t for t in tasks if t["id"] != task_id]
    _save_tasks(tasks)
    return f"삭제됨: [{target['id']}] {target['title']}"


@mcp.tool()
def search_task(keyword: str) -> str:
    """제목에 특정 키워드가 포함된 할일을 검색한다.

    Args:
        keyword: 검색할 키워드
    """
    tasks = _load_tasks()
    matched = [t for t in tasks if keyword.lower() in t["title"].lower()]
    if not matched:
        return f"'{keyword}'가 포함된 할일이 없습니다."
    lines = [f"[{t['id']}] {t['title']} (완료: {t['done']})" for t in matched]
    return "\n".join(lines)




if __name__ == "__main__":    
    mcp.run(transport="stdio")