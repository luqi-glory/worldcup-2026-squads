# worldcup-2026-squads

Static 2026 World Cup squad browser generated from the local RAG project.

Open `index.html` after publishing with GitHub Pages.

## Video chat page

`video-chat.html` adds the match video, synced subtitles, and a right-side chat panel with a bounded, scrollable chat history.

The page uses a real chat API whenever an endpoint is configured through `chat-config.js` or `window.VIDEO_CHAT_API_URL`. It supports the local `/chat` bridge and OpenAI-compatible `/chat/completions` endpoints. If no endpoint is configured on GitHub Pages, the UI clearly switches to local-context mode and answers from the loaded subtitles and squad data instead of pretending the API is online.

For local development, run the DeepSeek bridge and open the page from that server. The page will automatically use the same-origin `/chat` endpoint:

```powershell
python tools\video_chat_server.py --host 127.0.0.1 --port 8765
```

The bridge reads `assets/video/worldcup-commentary.srt`, `worldcup_site.json`, and the local `F:\RAG\dpsk.py` module. If `dpsk.py` is not available, set `DEEPSEEK_API_KEY` and the server will use the same DeepSeek-compatible OpenAI client directly. Do not put private API keys in `chat-config.js` before publishing to GitHub Pages.
