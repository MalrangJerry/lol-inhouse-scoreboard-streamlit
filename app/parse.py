from __future__ import annotations

def parse_line(line: str) -> dict:
    """
    "본명,게임닉#태그" -> {real_name, game_name, tag_line}
    """
    t = line.strip()
    if not t:
        raise ValueError("빈 줄은 허용되지 않습니다.")
    parts = t.split(",")
    if len(parts) != 2:
        raise ValueError(f"형식 오류: {line} (예: 홍길동,Hide on bush#KR1)")
    real_name = parts[0].strip()
    riot_id = parts[1].strip()

    idx = riot_id.rfind("#")
    if idx <= 0 or idx == len(riot_id) - 1:
        raise ValueError(f"형식 오류: {line} (게임닉#태그 필요)")
    game_name = riot_id[:idx].strip()
    tag_line = riot_id[idx + 1 :].strip()

    if not real_name or not game_name or not tag_line:
        raise ValueError(f"형식 오류: {line}")
    return {"real_name": real_name, "game_name": game_name, "tag_line": tag_line}
