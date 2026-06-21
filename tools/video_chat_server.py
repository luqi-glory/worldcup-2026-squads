from __future__ import annotations

import argparse
import importlib.util
import json
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "assets" / "video"
SUBTITLE_PATH = VIDEO_DIR / "worldcup-commentary.srt"
SITE_DATA_PATH = ROOT / "worldcup_site.json"
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start: float
    end: float
    text: str


def parse_timestamp(value: str) -> float:
    hour, minute, rest = value.strip().replace(",", ".").split(":")
    second = float(rest)
    return int(hour) * 3600 + int(minute) * 60 + second


def format_timestamp(seconds: float | None) -> str:
    if seconds is None:
        return "未知"
    seconds = max(0, float(seconds))
    minute = int(seconds // 60)
    second = int(seconds % 60)
    return f"{minute:02d}:{second:02d}"


def parse_srt(path: Path) -> list[SubtitleCue]:
    raw = path.read_text(encoding="utf-8-sig")
    cues: list[SubtitleCue] = []
    blocks = re.split(r"\n\s*\n", raw.strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        try:
            index = int(lines[0])
            start_raw, end_raw = [part.strip() for part in lines[1].split("-->", 1)]
            text = " ".join(lines[2:])
            cues.append(SubtitleCue(index=index, start=parse_timestamp(start_raw), end=parse_timestamp(end_raw), text=text))
        except ValueError:
            continue
    return cues


def load_site_data() -> dict:
    return json.loads(SITE_DATA_PATH.read_text(encoding="utf-8"))


SUBTITLES = parse_srt(SUBTITLE_PATH)
SITE_DATA = load_site_data()


def cue_lines(cues: list[SubtitleCue], limit: int | None = None) -> str:
    selected = cues if limit is None else cues[:limit]
    return "\n".join(
        f"[{format_timestamp(cue.start)}-{format_timestamp(cue.end)}] {cue.text}"
        for cue in selected
    )


def subtitle_window(current_time: float | None, before: float = 100, after: float = 20) -> list[SubtitleCue]:
    if current_time is None:
        return SUBTITLES
    start = max(0, current_time - before)
    end = current_time + after
    return [cue for cue in SUBTITLES if cue.end >= start and cue.start <= end]


def clean_text(value: object) -> str:
    return str(value or "").strip()


def question_numbers(question: str) -> set[str]:
    return set(re.findall(r"(\d{1,2})\s*号", question))


def field_hits(question: str, fields: list[str]) -> int:
    question_lower = question.lower()
    score = 0
    for field in fields:
        value = clean_text(field)
        if len(value) < 2:
            continue
        if value.lower() in question_lower or value in question:
            score += 3 if len(value) >= 4 else 2
    return score


def is_player_profile_question(question: str) -> bool:
    player_intent = re.search(r"(介绍|身世|经历|背景|履历|俱乐部|国家队|球员|队员|几号|\d{1,2}\s*号|是谁)", question)
    video_intent = re.search(r"(刚才|刚刚|当前|现在|这一段|这段|进球|战术|发生|打门|射门|字幕|视频|比赛)", question)
    return bool(player_intent and not video_intent)


def build_background(question: str, team_id: str | None = None) -> str:
    teams = SITE_DATA.get("teams", [])
    number_hints = question_numbers(question)
    team_notes: list[tuple[int, str]] = []
    player_notes: list[tuple[int, str]] = []

    for team in teams:
        team_fields = [
            team.get("id"),
            team.get("country"),
            team.get("nameZh"),
            team.get("nicknameEn"),
            team.get("nicknameZh"),
            team.get("coach"),
        ]
        selected = bool(team_id and team.get("id") == team_id)
        team_score = (8 if selected else 0) + field_hits(question, team_fields)
        if team_score:
            team_notes.append((
                team_score,
                f"- {team.get('country')} / {team.get('nameZh', '')}: group {team.get('group')}, coach {team.get('coach')}. "
                f"{team.get('storyZh') or team.get('storyEn') or ''} {team.get('currentZh') or team.get('currentEn') or ''}",
            ))

        for player in team.get("players", []):
            player_fields = [
                player.get("name"),
                player.get("nameZh"),
                player.get("club"),
                player.get("roleEn"),
                player.get("roleZh"),
                player.get("storyEn"),
                player.get("storyZh"),
            ]
            score = team_score
            if number_hints and clean_text(player.get("number")) in number_hints:
                score += 10
            score += field_hits(question, player_fields)
            if selected and not number_hints and score == team_score:
                score += 1
            if score <= 0:
                continue
            player_notes.append((
                score,
                "- "
                f"{player.get('name')} / {player.get('nameZh', '')}, "
                f"{team.get('country')} #{player.get('number') or '-'} {player.get('position')}, "
                f"club {player.get('club') or '-'}, age {player.get('age') or '-'}, "
                f"caps {player.get('caps') if player.get('caps') is not None else '-'}, "
                f"goals {player.get('goals') if player.get('goals') is not None else '-'}. "
                f"{player.get('storyZh') or player.get('storyEn') or ''} "
                f"{player.get('currentZh') or player.get('currentEn') or ''}",
            ))

    if not team_notes and not player_notes:
        top_players: list[tuple[int, str]] = []
        for team in teams:
            for player in team.get("players", []):
                caps = int(player.get("caps") or 0)
                top_players.append((
                    caps,
                    f"- {player.get('name')} / {player.get('nameZh', '')}, {team.get('country')} #{player.get('number') or '-'}, "
                    f"{player.get('position')}, club {player.get('club') or '-'}, caps {caps}, goals {player.get('goals') or 0}.",
                ))
        player_notes = sorted(top_players, reverse=True)[:24]

    team_notes = sorted(team_notes, reverse=True)[:10]
    player_notes = sorted(player_notes, reverse=True)[:70]
    priority_notes = [note for score, note in player_notes if score >= 18][:8]
    return "\n".join(
        ["最相关球员（回答球员/号码问题时优先使用）:"]
        + priority_notes
        + ["", "球队背景:"]
        + [note for _, note in team_notes]
        + ["", "球员背景:"]
        + [note for _, note in player_notes]
    ).strip()


def load_dpsk_module():
    explicit = os.environ.get("DPSK_MODULE_PATH")
    candidates = [Path(explicit)] if explicit else [ROOT.parent / "dpsk.py", Path("F:/RAG/dpsk.py")]
    for path in candidates:
        if not path or not path.exists():
            continue
        spec = importlib.util.spec_from_file_location("local_dpsk", path)
        if not spec or not spec.loader:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules["local_dpsk"] = module
        spec.loader.exec_module(module)
        return module
    return None


def call_model(messages: list[dict[str, str]]) -> str:
    module = load_dpsk_module()
    if module and hasattr(module, "chat_completion"):
        return str(module.chat_completion(messages, model=DEFAULT_MODEL, temperature=0.25, max_tokens=900))
    if module and hasattr(module, "client"):
        response = module.client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=0.25,
            max_tokens=900,
        )
        return response.choices[0].message.content

    from openai import OpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 dpsk.py，也没有设置 DEEPSEEK_API_KEY。")
    client = OpenAI(api_key=api_key, base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        temperature=0.25,
        max_tokens=900,
    )
    return response.choices[0].message.content


def build_messages(payload: dict) -> list[dict[str, str]]:
    question = clean_text(payload.get("question"))
    current_time = payload.get("currentTime")
    try:
        current_time = float(current_time) if current_time is not None else None
    except (TypeError, ValueError):
        current_time = None

    team_id = clean_text(payload.get("teamId")) or None
    recent = subtitle_window(current_time)
    profile_question = is_player_profile_question(question)
    full_transcript = (
        "本问题是球员/号码资料问题，已省略全量字幕以避免干扰；请优先使用相关背景信息。"
        if profile_question
        else cue_lines(SUBTITLES)
    )
    recent_transcript = (
        "本问题是球员/号码资料问题，当前字幕仅作背景，不可用来否定已命中的球员资料。"
        if profile_question
        else cue_lines(recent)
    )
    background = build_background(question, team_id=team_id)
    history = payload.get("history") or []
    clipped_history = [
        {"role": item.get("role"), "content": clean_text(item.get("content"))[:1200]}
        for item in history[-6:]
        if item.get("role") in {"user", "assistant"} and clean_text(item.get("content"))
    ]

    system = (
        "你是世界杯视频解说互动助手。请用中文回答，结合给定字幕、当前播放时间和球员/球队背景信息。"
        "用户问“球员、队员、几号、号码、身世、经历、俱乐部、国家队履历”时，优先使用球员/球队背景；"
        "如果用户选择了球队并询问某个号码，优先回答该球队对应号码的球员，不要因为当前字幕没提到他就否定背景。"
        "如果这是纯球员资料问题，不要转去介绍当前视频字幕里的其他人物。"
        "用户问“刚才”“刚刚”“我离开时”“这一段”这类视频进程问题时，重点参考当前时间附近字幕。"
        "如果字幕或背景没有足够证据，请明确说不确定，不要编造。回答要简洁、有判断，可以使用简洁 Markdown。"
    )
    user = f"""当前视频播放时间: {format_timestamp(current_time)}

相关背景信息（已按问题相关性排序；如果“最相关球员”有内容，回答球员/号码问题时必须优先使用）:
{background}

当前时间附近字幕:
{recent_transcript}

全量字幕:
{full_transcript}

用户问题:
{question}
"""
    return [{"role": "system", "content": system}, *clipped_history, {"role": "user", "content": user}]


class Handler(BaseHTTPRequestHandler):
    server_version = "WorldCupVideoChat/1.0"

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        raw_path = unquote(parsed.path.lstrip("/")) or "video-chat.html"
        target = (ROOT / raw_path).resolve()
        if not str(target).startswith(str(ROOT.resolve())) or not target.is_file():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/chat":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            messages = build_messages(payload)
            answer = call_model(messages)
            body = json.dumps({"answer": answer, "model": DEFAULT_MODEL}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
        except Exception as exc:
            body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
            self.send_response(500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[video-chat] {self.address_string()} {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the World Cup video chat page and DeepSeek chat endpoint.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving video chat at http://{args.host}:{args.port}/video-chat.html")
    print("Chat endpoint:", f"http://{args.host}:{args.port}/chat")
    server.serve_forever()


if __name__ == "__main__":
    main()
