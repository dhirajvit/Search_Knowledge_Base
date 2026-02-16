"use client";

import { useState, useEffect, useRef, FormEvent } from "react";
import ReactMarkdown from "react-markdown";

interface Source {
  filename: string;
  similarity: number;
  excerpt: string;
}

interface SearchResponse {
  answer: string;
  filenames: string[];
  sources: Source[];
}

interface ConversationTurn {
  question: string;
  answer: string;
  sources: Source[];
}

export default function HomePage() {
  const [question, setQuestion] = useState("");
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef<string>("");

  useEffect(() => {
    // Generate or retrieve session ID
    let id = sessionStorage.getItem("session_id");
    if (!id) {
      id = crypto.randomUUID();
      sessionStorage.setItem("session_id", id);
    }
    sessionIdRef.current = id;

    // Restore conversation from Redis on page refresh
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const headers: Record<string, string> = {};
    if (process.env.NEXT_PUBLIC_API_KEY) {
      headers["x-api-key"] = process.env.NEXT_PUBLIC_API_KEY;
    }
    fetch(`${apiUrl}/session/${id}`, { headers })
      .then((res) => res.json())
      .then((data) => {
        if (data.turns?.length) setConversation(data.turns);
      })
      .catch(() => {});

    // Flush session to PostgreSQL on tab/browser close
    const handleUnload = () => {
      const apiKey = process.env.NEXT_PUBLIC_API_KEY;
      const endUrl = `${apiUrl}/session/end`;
      const body = JSON.stringify({
        session_id: sessionIdRef.current,
        user_id: apiKey || "anonymous",
      });
      navigator.sendBeacon(
        endUrl,
        new Blob([body], { type: "application/json" })
      );
    };

    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (process.env.NEXT_PUBLIC_API_KEY) {
        headers["x-api-key"] = process.env.NEXT_PUBLIC_API_KEY;
      }

      const res = await fetch(`${apiUrl}/search`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          question,
          session_id: sessionIdRef.current,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Request failed (${res.status})`);
      }

      const data: SearchResponse = await res.json();
      setConversation((prev) => [
        ...prev,
        { question, answer: data.answer, sources: data.sources },
      ]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-16 font-sans">
      <h1 className="mb-8 text-3xl font-bold tracking-tight">
        Search Knowledge Base
      </h1>

      {/* Conversation thread */}
      {conversation.length > 0 && (
        <div className="mb-10 space-y-6">
          {conversation.map((turn, i) => (
            <div key={i} className="space-y-3">
              {/* Question */}
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-lg bg-zinc-900 px-4 py-3 text-white dark:bg-zinc-100 dark:text-zinc-900">
                  {turn.question}
                </div>
              </div>

              {/* Answer */}
              <div className="prose prose-zinc dark:prose-invert max-w-none rounded-lg border border-zinc-200 p-5 dark:border-zinc-800">
                <ReactMarkdown>{turn.answer}</ReactMarkdown>
              </div>

              {/* Sources */}
              {turn.sources.length > 0 && (
                <ul className="space-y-1">
                  {turn.sources.map((src, j) => (
                    <li
                      key={j}
                      className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800"
                    >
                      <span className="truncate font-mono">{src.filename}</span>
                      <span className="ml-4 shrink-0 text-zinc-500">
                        {(src.similarity * 100).toFixed(1)}% match
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-3">
        <div className="relative flex-1">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value.slice(0, 1000))}
            maxLength={1000}
            placeholder="Ask a question..."
            className="w-full rounded-lg border border-zinc-300 px-4 py-3 text-base outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:focus:border-zinc-400"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-zinc-400">
            {question.length}/1000
          </span>
        </div>
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="rounded-lg bg-zinc-900 px-6 py-3 text-base font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>
    </div>
  );
}
