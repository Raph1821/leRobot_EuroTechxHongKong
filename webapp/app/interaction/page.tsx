"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Mic, MicOff, Bot, User } from "lucide-react";

type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
};

/**
 * Interaction page — text/voice interface to the robot's LLM agent.
 *
 * In production this connects to the FastAPI backend at /query/stream
 * and /command/stream (interaction module), which routes to the LLM
 * provider (Bedrock / OpenAI / Ollama) with MCP tool access.
 *
 * Modes:
 *  - Ask: read-only queries (what do you see? where is the medicine?)
 *  - Agent: full tool access (go pick up Aspirin, start patrol)
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function InteractionPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Hello! I'm your SO-101 care robot assistant. You can ask me questions about what I see in the workspace, or give me commands like \"pick up the Aspirin and sort it\", \"what medicines have you scanned?\", or \"start patrol mode\". Use the microphone for voice input.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<"ask" | "agent">("agent");
  const [isListening, setIsListening] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage() {
    if (!input.trim() || isStreaming) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      text: input.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", text: "", timestamp: new Date() },
    ]);

    try {
      const endpoint =
        mode === "agent" ? "/command/stream" : "/query/stream";
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: userMsg.text }),
      });

      if (!response.ok) throw new Error("API unavailable");

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") break;
              try {
                const token = JSON.parse(data);
                accumulated += token;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, text: accumulated } : m
                  )
                );
              } catch {
                // non-JSON line, skip
              }
            }
          }
        }
      }
    } catch {
      // Fallback when backend is not running
      const fallback =
        mode === "agent"
          ? `[Agent mode] I received your command: "${userMsg.text}". The backend API is not connected yet. Once the interaction server is running (python -m uvicorn interaction.web.endpoints:app), I'll be able to execute robot commands via MCP tools.`
          : `[Ask mode] I received your question: "${userMsg.text}". The backend API is not connected. Start the interaction server to enable live responses.`;

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, text: fallback } : m
        )
      );
    } finally {
      setIsStreaming(false);
    }
  }

  function toggleMic() {
    if (isListening) {
      setIsListening(false);
      // In production, stop recording and send to /transcribe endpoint
    } else {
      setIsListening(true);
      // In production, start recording audio via MediaRecorder API
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Mode selector */}
      <div className="flex items-center gap-3 border-b border-hairline px-6 py-3">
        <span className="text-xs text-ink-soft">Mode:</span>
        <button
          onClick={() => setMode("ask")}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            mode === "ask"
              ? "bg-ink text-paper"
              : "bg-paper-2 text-ink-soft hover:text-ink"
          }`}
        >
          Ask (read-only)
        </button>
        <button
          onClick={() => setMode("agent")}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            mode === "agent"
              ? "bg-ink text-paper"
              : "bg-paper-2 text-ink-soft hover:text-ink"
          }`}
        >
          Agent (full control)
        </button>
        <span className="ml-auto text-[11px] text-ink-soft">
          {mode === "agent"
            ? "Can move arm, pick & place, sort medicines"
            : "Observe only — no arm movement commands"}
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="mx-auto max-w-2xl space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${
                msg.role === "user" ? "justify-end" : ""
              }`}
            >
              {msg.role === "assistant" && (
                <span className="mt-1 grid h-7 w-7 flex-none place-items-center rounded-full bg-ink text-paper">
                  <Bot size={14} />
                </span>
              )}
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-ink text-paper"
                    : "bg-paper-2 text-ink"
                }`}
              >
                {msg.text || (
                  <span className="inline-block animate-pulse text-ink-soft">
                    Thinking…
                  </span>
                )}
              </div>
              {msg.role === "user" && (
                <span className="mt-1 grid h-7 w-7 flex-none place-items-center rounded-full bg-paper-2 text-ink-soft">
                  <User size={14} />
                </span>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-hairline px-6 py-4">
        <div className="mx-auto flex max-w-2xl items-center gap-2">
          <button
            onClick={toggleMic}
            className={`grid h-10 w-10 flex-none place-items-center rounded-full transition-colors ${
              isListening
                ? "bg-coral text-paper animate-pulse"
                : "bg-paper-2 text-ink-soft hover:text-ink"
            }`}
          >
            {isListening ? <MicOff size={16} /> : <Mic size={16} />}
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder={
              mode === "agent"
                ? "Give a command: sort Aspirin to morning slot, start patrol…"
                : "Ask: what medicines have you scanned? is anything expired?"
            }
            className="flex-1 rounded-full border border-hairline bg-paper-2/50 px-4 py-2.5 text-sm outline-none placeholder:text-ink-soft/60 focus:border-ink"
            disabled={isStreaming}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming}
            className="grid h-10 w-10 flex-none place-items-center rounded-full bg-ink text-paper transition-opacity disabled:opacity-30"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
