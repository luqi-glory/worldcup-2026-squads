# worldcup-2026-squads

Static 2026 World Cup squad browser generated from the local RAG project.

Open `index.html` after publishing with GitHub Pages.

## Video chat page

`video-chat.html` adds the match video, synced subtitles, and a right-side chat panel.

Run the local DeepSeek bridge before using chat:

```powershell
python tools\video_chat_server.py --host 127.0.0.1 --port 8765
```

The bridge reads `assets/video/worldcup-commentary.srt`, `worldcup_site.json`, and the local `F:\RAG\dpsk.py` module. If `dpsk.py` is not available, set `DEEPSEEK_API_KEY` and the server will use the same DeepSeek-compatible OpenAI client directly.
