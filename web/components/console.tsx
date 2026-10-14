"use client";

import { FormEvent, useEffect, useState } from "react";

type Hit = { id: string; text: string; score: number };
type Answer = string | number | Hit[];

type Turn = {
  question: string;
  answer: Answer;
  mode?: string;
  tool?: string;
  cached?: boolean;
};

type Health = {
  ok: boolean;
  store: string;
  queue: string;
  cache: string;
};

const SUGGESTIONS = ["What is the refund policy?", "2*(3+4)"];

export function Console() {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [docId, setDocId] = useState("");
  const [docText, setDocText] = useState("");
  const [docNote, setDocNote] = useState("");
  const [asking, setAsking] = useState(false);
  const [storing, setStoring] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const healthResponse = await fetch("/api/health");
        if (!healthResponse.ok) throw new Error("health");
        const healthBody = (await healthResponse.json()) as Health;
        if (!cancelled) setHealth(healthBody);
      } catch {
        if (!cancelled) setOffline(true);
      }
      try {
        const chatResponse = await fetch("/api/chats");
        if (!chatResponse.ok) return;
        const body = (await chatResponse.json()) as { chats?: Turn[] };
        if (!cancelled) setTurns([...(body.chats ?? [])].reverse());
      } catch {
        /* history is optional; the ask box still works */
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || asking) return;
    setAsking(true);
    setError("");
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });
      if (!response.ok) throw new Error("ask failed");
      const turn = (await response.json()) as Omit<Turn, "question">;
      setTurns((current) => [...current, { question: trimmed, ...turn }]);
      setQuestion("");
    } catch {
      setError("The agent could not answer. Check that the API is running.");
    } finally {
      setAsking(false);
    }
  }

  async function onAsk(event: FormEvent) {
    event.preventDefault();
    await ask(question);
  }

  async function onStore(event: FormEvent) {
    event.preventDefault();
    const id = docId.trim();
    const text = docText.trim();
    if (!id || !text || storing) return;
    setStoring(true);
    setDocNote("");
    setError("");
    try {
      const response = await fetch("/api/docs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ id, text }),
      });
      if (!response.ok) throw new Error("store failed");
      const body = (await response.json()) as { status?: string };
      setDocNote(body.status === "queued" ? "Queued for the worker." : "Stored.");
      setDocText("");
    } catch {
      setError("The document was not stored. Check that the API is running.");
    } finally {
      setStoring(false);
    }
  }

  return (
    <main className="shell">
      <header className="top">
        <div>
          <p className="eyebrow">AgentOps</p>
          <h1>Ask the documents.</h1>
        </div>
        <div className="pills" aria-live="polite">
          {offline && <span className="pill bad">API unreachable</span>}
          {health && (
            <>
              <span className="pill">store {health.store}</span>
              <span className="pill">queue {health.queue}</span>
              <span className="pill">cache {health.cache}</span>
            </>
          )}
        </div>
      </header>

      <div className="layout">
        <section className="panel">
          <h2>Add a document</h2>
          <p className="lede">
            Stored text is what <code>search_docs</code> can retrieve. Arithmetic skips the index and uses the calculator.
          </p>
          <form onSubmit={onStore} className="stack">
            <label>
              Document id
              <input
                value={docId}
                onChange={(event) => setDocId(event.target.value)}
                placeholder="d1"
                name="doc-id"
                autoComplete="off"
              />
            </label>
            <label>
              Text
              <textarea
                value={docText}
                onChange={(event) => setDocText(event.target.value)}
                placeholder="refund policy is 30 days"
                name="doc-text"
                rows={6}
              />
            </label>
            <button type="submit" disabled={storing || !docId.trim() || !docText.trim()}>
              {storing ? "Saving…" : "Save document"}
            </button>
            {docNote && <p className="note">{docNote}</p>}
          </form>
        </section>

        <section className="chat">
          <div className="transcript" aria-live="polite">
            {turns.length === 0 && (
              <div className="empty">
                <p>No questions yet.</p>
                <p>Save a document, then ask about it, or send an expression such as 2*(3+4).</p>
              </div>
            )}
            {turns.map((turn, index) => (
              <article key={`${turn.question}-${index}`} className="exchange">
                <p className="who">You</p>
                <p className="question">{turn.question}</p>
                <div className="answer">
                  <div className="meta">
                    {turn.tool && <span className="chip">{turn.tool}</span>}
                    {turn.mode && <span className="chip quiet">{turn.mode}</span>}
                    {turn.cached && <span className="chip quiet">cached</span>}
                  </div>
                  <AnswerView answer={turn.answer} />
                </div>
              </article>
            ))}
          </div>

          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          <div className="suggestions">
            {SUGGESTIONS.map((suggestion) => (
              <button key={suggestion} type="button" className="ghost" onClick={() => void ask(suggestion)} disabled={asking}>
                {suggestion}
              </button>
            ))}
          </div>

          <form onSubmit={onAsk} className="composer">
            <label className="sr" htmlFor="question">
              Question
            </label>
            <input
              id="question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question"
              autoComplete="off"
            />
            <button type="submit" disabled={asking || !question.trim()}>
              {asking ? "Asking…" : "Ask"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}

function AnswerView({ answer }: { answer: Answer }) {
  if (typeof answer === "string" || typeof answer === "number") {
    return <p className="plain">{String(answer)}</p>;
  }
  if (!Array.isArray(answer) || answer.length === 0) {
    return <p className="plain muted">No matching documents.</p>;
  }
  return (
    <ul className="hits">
      {answer.map((hit) => (
        <li key={hit.id}>
          <div className="hit-head">
            <span className="doc">{hit.id}</span>
            <span className="score">{hit.score}</span>
          </div>
          <p>{hit.text}</p>
        </li>
      ))}
    </ul>
  );
}
