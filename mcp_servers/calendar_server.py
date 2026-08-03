import json
import os
from datetime import datetime

from mcp.server.fastmcp import FastMCP

# task_server랑 파일만 다르게, 같은 폴더에 events.json 저장
DATA_FILE = os.path.join(os.path.dirname(__file__), "events.json")

mcp = FastMCP('calendar-server')

def _load_events() -> list[dict]:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_events(events: list[dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


def _next_id(events: list[dict]) -> int:
    return max([e["id"] for e in events], default=0) + 1


@mcp.tool()
def create_event(title: str, date: str, time: str) -> str:
    events = _load_events()
    event = {
        "id": _next_id(events),
        "title": title,
        "date": date,
        "time": time,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    events.append(event)
    _save_events(events)
    return f"일정 추가됨 (id={event['id']}): {date} {time} - {title}"


@mcp.tool()
def list_events(date: str) -> str:
    events = _load_events()
    filtered = [e for e in events if e["date"] == date]

    if not filtered:
        return f"{date}에 등록된 일정이 없습니다."

    # 시간순 정렬
    filtered.sort(key=lambda e: e["time"])
    lines = [f"[{e['id']}] {e['time']} - {e['title']}" for e in filtered]
    return f"{date} 일정:\n" + "\n".join(lines)


@mcp.tool()
def delete_event(event_id: int) -> str:
    events = _load_events()
    target = next((e for e in events if e["id"] == event_id), None)
    if target is None:
        return f"id={event_id}인 일정을 찾을 수 없습니다."
    events = [e for e in events if e["id"] != event_id]
    _save_events(events)
    return f"삭제됨: [{target['id']}] {target['date']} {target['time']} - {target['title']}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
