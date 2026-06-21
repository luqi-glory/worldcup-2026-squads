# worldcup-2026-squads

Static 2026 World Cup squad browser generated from the local RAG project.

Open `index.html` after publishing with GitHub Pages.

## Video chat page

`video-chat.html` adds the match video, synced subtitles, and a right-side chat panel.

The page no longer shows a local API address field or defaults to `127.0.0.1`. It can use a hidden remote chat endpoint when `window.VIDEO_CHAT_API_URL` is set, including an OpenAI-compatible `/chat/completions` endpoint when `window.VIDEO_CHAT_API_KEY` is provided by a private runtime wrapper. If no remote endpoint is configured, the page answers from the loaded subtitles and squad data instead of failing with `Failed to fetch`.

For local development, you can still run the DeepSeek bridge and set `window.VIDEO_CHAT_API_URL` to that local endpoint in a private wrapper:

```powershell
python tools\video_chat_server.py --host 127.0.0.1 --port 8765
```

The bridge reads `assets/video/worldcup-commentary.srt`, `worldcup_site.json`, and the local `F:\RAG\dpsk.py` module. If `dpsk.py` is not available, set `DEEPSEEK_API_KEY` and the server will use the same DeepSeek-compatible OpenAI client directly.
