from config import MAX_HISTORY

_sessions: dict[int, list[dict]] = {}

def get_session(user_id: int) -> list[dict]:
    if user_id not in _sessions:
        _sessions[user_id] = []
    return _sessions[user_id]

def add_message(user_id: int, role: str, content: str) -> None:
    session = get_session(user_id)
    session.append({"role": role, "content": content})
    if len(session) > MAX_HISTORY:
        session[:] = session[-MAX_HISTORY:]

def clear_session(user_id: int) -> None:
    _sessions.pop(user_id, None)

def cleanup() -> None:
    _sessions.clear()
