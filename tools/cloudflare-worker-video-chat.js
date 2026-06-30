const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization"
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json; charset=utf-8"
    }
  });
}

function formatTime(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const minute = Math.floor(safe / 60);
  const second = Math.floor(safe % 60);
  return `${String(minute).padStart(2, "0")}:${String(second).padStart(2, "0")}`;
}

function cueLine(cue) {
  if (!cue) return "";
  return `[${formatTime(cue.start)}-${formatTime(cue.end)}] ${cue.text || ""}`;
}

function buildMessages(payload) {
  const question = String(payload.question || "").trim();
  const nearby = Array.isArray(payload.nearbySubtitles) ? payload.nearbySubtitles : [];
  const commentary = Array.isArray(payload.commentaryCues) ? payload.commentaryCues : [];
  const history = Array.isArray(payload.history) ? payload.history : [];
  return [
    {
      role: "system",
      content: "你是一个中文足球视频解说问答助手。请结合交互视频 commentary.json 时间轴、当前播放时间和字幕上下文简洁回答；证据不足时明确说不确定，不要编造。问足球规则时可以直接给出简洁规则解释。"
    },
    ...history
      .filter(item => item && ["user", "assistant"].includes(item.role))
      .slice(-6)
      .map(item => ({ role: item.role, content: String(item.content || "").slice(0, 1200) })),
    {
      role: "user",
      content: [
        `当前播放时间：${formatTime(payload.currentTime)}`,
        `当前字幕：${cueLine(payload.activeSubtitle) || "无"}`,
        `附近字幕：\n${nearby.map(cueLine).filter(Boolean).join("\n") || "无"}`,
        `交互视频 commentary.json 全量时间轴：\n${commentary.map(cueLine).filter(Boolean).join("\n") || "无"}`,
        `用户问题：${question}`
      ].join("\n\n")
    }
  ];
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }
    if (request.method !== "POST") {
      return json({ error: "Use POST /chat" }, 405);
    }
    if (!env.DEEPSEEK_API_KEY) {
      return json({ error: "Missing DEEPSEEK_API_KEY worker secret" }, 500);
    }

    const payload = await request.json().catch(() => null);
    if (!payload || !String(payload.question || "").trim()) {
      return json({ error: "Missing question" }, 400);
    }

    const upstream = await fetch(env.DEEPSEEK_BASE_URL || "https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.DEEPSEEK_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: env.DEEPSEEK_MODEL || "deepseek-v4-pro",
        messages: buildMessages(payload),
        temperature: 0.25,
        max_tokens: 900
      })
    });

    const data = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      return json({ error: data.error?.message || `Upstream HTTP ${upstream.status}` }, upstream.status);
    }

    return json({
      answer: data.choices?.[0]?.message?.content || "",
      model: data.model || env.DEEPSEEK_MODEL || "deepseek-v4-pro"
    });
  }
};
