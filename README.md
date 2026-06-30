# worldcup-2026-squads

Static 2026 World Cup squad browser generated from the local RAG project.

Open `index.html` after publishing with GitHub Pages.

## Video chat page

`video-chat.html` adds the interaction demo video, a live subtitle bar, and a right-side chat panel with a bounded, scrollable chat history. The full transcript list is intentionally not rendered on the page.

The interaction button currently runs a demo flow: typed input is accepted directly; if the input is empty, the same button tries browser speech recognition and falls back to a demo voice input if speech recognition is unavailable. The demo writes `好的我看到了你的问题我等下再回答你` into the live subtitle bar and video subtitle track shortly after the user input.

The speech entry uses the browser Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`). It needs a user click to start, and browser support varies, so the page keeps a text-input fallback.

The page can still use a real chat API whenever an endpoint is configured through `chat-config.js`, `window.VIDEO_CHAT_API_URL`, or the query string:

```text
video-chat.html?api=https://your-proxy.example.com/chat
```

GitHub Pages cannot run the local `/chat` bridge because it only serves static files. For the public page, deploy a small HTTPS proxy on Cloudflare Workers, Vercel, or another server, keep the model API key on that server, then set `apiUrl` to the proxy URL. Do not put private API keys in `chat-config.js`.

`tools/cloudflare-worker-video-chat.js` is a deployable Worker proxy for this. Set `DEEPSEEK_API_KEY` as a Worker secret, deploy the Worker, then open the GitHub Pages page with:

```text
video-chat.html?api=https://your-worker.example.workers.dev
```

For local development, run the DeepSeek bridge and open the page from that server. The page will automatically use the same-origin `/chat` endpoint:

```powershell
python tools\video_chat_server.py --host 127.0.0.1 --port 8765
```

The bridge reads `assets/video/worldcup-commentary.srt`, `worldcup_site.json`, and the local `F:\RAG\dpsk.py` module. If `dpsk.py` is not available, set `DEEPSEEK_API_KEY` and the server will use the same DeepSeek-compatible OpenAI client directly.

The interaction demo video is tracked with Git LFS because it is larger than the normal GitHub single-file limit. The Pages workflow uses `actions/checkout` with `lfs: true` so the deployed artifact contains the real `.mp4` instead of an LFS pointer.
