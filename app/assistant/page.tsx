"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, Send, Sparkles } from "lucide-react";

type Msg = { role: "user" | "assistant"; content: string };

const SUGGESTIONS = [
  "When is my next dose?",
  "Is the robot online?",
  "What should I do in an emergency?",
];

export default function AssistantPage() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content:
        "Hi, I'm Elda. I can help with your medication schedule, the robot, or anything you need. How can I help?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    const next = [...messages, { role: "user" as const, content: trimmed }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next }),
      });
      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.text ?? data.error ?? "Sorry, something went wrong.",
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "I couldn't reach the server. Try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function toggleMic() {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      alert("Voice input isn't supported in this browser.");
      return;
    }
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.onresult = (e: { results: { 0: { 0: { transcript: string } } } }) => {
      setInput(e.results[0][0].transcript);
    };
    rec.onend = () => setListening(false);
    rec.start();
    recognitionRef.current = rec;
    setListening(true);
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col p-6">
      {/* messages */}
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto pb-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-ink text-paper"
                  : "border border-hairline bg-paper text-ink"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1.5 rounded-2xl border border-hairline bg-paper px-4 py-3">
              {[0, 1, 2].map((d) => (
                <span
                  key={d}
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-soft"
                  style={{ animationDelay: `${d * 0.15}s` }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* suggestions */}
      {messages.length <= 1 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-paper px-3 py-1.5 text-xs text-ink-soft transition-colors hover:border-ink hover:text-ink"
            >
              <Sparkles size={12} /> {s}
            </button>
          ))}
        </div>
      )}

      {/* input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-center gap-2 rounded-2xl border border-hairline bg-paper p-2"
      >
        <button
          type="button"
          onClick={toggleMic}
          aria-label="Voice input"
          className={`grid h-10 w-10 flex-none place-items-center rounded-xl transition-colors ${
            listening ? "bg-coral text-paper" : "text-ink-soft hover:bg-paper-2"
          }`}
        >
          <Mic size={18} />
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={listening ? "Listening…" : "Ask Elda anything…"}
          className="min-w-0 flex-1 bg-transparent p-2 text-sm outline-none placeholder:text-ink-soft/60"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          aria-label="Send"
          className="grid h-10 w-10 flex-none place-items-center rounded-xl bg-ink text-paper transition-opacity disabled:opacity-30"
        >
          <Send size={17} />
        </button>
      </form>
    </div>
  );
}
