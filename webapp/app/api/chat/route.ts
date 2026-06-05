import Anthropic from "@anthropic-ai/sdk";

export const runtime = "nodejs";

const client = new Anthropic();

// CareAI persona. Static context lives here so the prefix caches; volatile
// per-request data would go in the messages, not the system prompt.
const SYSTEM = `You are Elda, an AI care assistant for an elderly person living at home and their family.

You help with: medication schedule and reminders, the SO-101 care robot arm, the home camera, general questions, and what to do in an emergency.

Be warm, calm, and concise — short, clear sentences for an older user. Don't over-explain. If something is a medical or safety emergency, tell them to contact emergency services or a relative immediately and offer to trigger the emergency flow.

Current care context you can use:
- Medications: Aspirin 100mg (1 pill, daily 14:00), Metformin 500mg (daily 08:00), Vitamin D 1000 IU, Ibuprofen 200mg (low stock — 4 left), Amoxicillin 250mg (expiring this month).
- Next dose: Aspirin 100mg at 14:00.
- Robot: SO-101 arm, online, used for pick & place of medication.
- Location: Munich. Nearest hospital routing is available in the Emergency tab.`;

type ChatMessage = { role: "user" | "assistant"; content: string };

export async function POST(req: Request) {
  if (!process.env.ANTHROPIC_API_KEY) {
    return Response.json(
      { error: "ANTHROPIC_API_KEY is not set on the server." },
      { status: 500 },
    );
  }

  let messages: ChatMessage[];
  try {
    const body = await req.json();
    messages = Array.isArray(body?.messages) ? body.messages : [];
  } catch {
    return Response.json({ error: "Invalid request body." }, { status: 400 });
  }
  if (messages.length === 0) {
    return Response.json({ error: "No messages provided." }, { status: 400 });
  }

  try {
    const response = await client.messages.create({
      model: "claude-opus-4-8",
      max_tokens: 1024,
      thinking: { type: "adaptive" },
      output_config: { effort: "low" },
      system: [
        { type: "text", text: SYSTEM, cache_control: { type: "ephemeral" } },
      ],
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
    });

    const text = response.content
      .filter((b): b is Anthropic.TextBlock => b.type === "text")
      .map((b) => b.text)
      .join("");

    return Response.json({ text });
  } catch (err) {
    if (err instanceof Anthropic.APIError) {
      return Response.json(
        { error: `Claude API error (${err.status}): ${err.message}` },
        { status: 502 },
      );
    }
    return Response.json({ error: "Unexpected server error." }, { status: 500 });
  }
}
