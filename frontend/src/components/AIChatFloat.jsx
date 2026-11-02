import { useState, useRef, useEffect } from "react";
import { Sparkles, X, Send, Loader2 } from "lucide-react";
import { api, errorText } from "@/lib/api";
import { useConfig } from "@/lib/config";

export default function AIChatFloat() {
  const cfg = useConfig();
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([
    { role: "ai", text: "Hi! I'm LoNo AI. Ask me about content, tokens, staking, or the platform." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const send = async (e) => {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setMsgs((m) => [...m, { role: "user", text }]);
    setInput(""); setLoading(true);
    try {
      const { data } = await api.post("/ai/chat", { message: text, session_id: sessionId });
      setSessionId(data.session_id);
      setMsgs((m) => [...m, { role: "ai", text: data.reply }]);
    } catch (err) {
      setMsgs((m) => [...m, { role: "ai", text: errorText(err, "I couldn't answer that just now. Try again in a moment.") }]);
    } finally { setLoading(false); }
  };

  if (!cfg.ai) return null;

  return (
    <>
      {!open && (
        <button
          data-testid="ai-chat-fab"
          onClick={() => setOpen(true)}
          className="fixed bottom-24 lg:bottom-8 right-4 md:right-6 z-[10000] w-14 h-14 rounded-full bg-[#FF3B30] hover:bg-[#FF5C53] grid place-items-center shadow-2xl shadow-[#FF3B30]/40 transition"
          aria-label="Open AI Assistant"
        >
          <Sparkles className="w-6 h-6" />
        </button>
      )}

      {open && (
        <div data-testid="ai-chat-panel" className="fixed bottom-24 lg:bottom-8 right-4 md:right-6 z-[10000] w-[92vw] max-w-md h-[560px] rounded-2xl glass shadow-2xl flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[#FF3B30] grid place-items-center">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <div className="font-display text-sm font-medium">LoNo AI</div>
                <div className="text-[10px] text-gray-400">Powered by Claude</div>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="p-1.5 rounded hover:bg-white/10" aria-label="Close">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === "user" ? "bg-[#FF3B30] text-white" : "bg-white/10 text-gray-100"
                }`}>
                  {m.text}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start"><div className="bg-white/10 px-3.5 py-2.5 rounded-2xl"><Loader2 className="w-4 h-4 animate-spin" /></div></div>
            )}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={send} className="p-3 border-t border-white/5 flex items-center gap-2">
            <input
              data-testid="ai-chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask LoNo AI…"
              className="flex-1 bg-white/5 border border-white/10 rounded-full px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FF3B30]/40"
            />
            <button data-testid="ai-chat-send" disabled={loading} className="w-10 h-10 rounded-full bg-[#FF3B30] grid place-items-center disabled:opacity-50">
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
