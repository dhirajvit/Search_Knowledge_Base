"use client";

import { useState, FormEvent } from "react";
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

export default function HomePage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("http://localhost:8000/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Request failed (${res.status})`);
      }

      const data: SearchResponse = await res.json();
      setResult(data);
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

      <form onSubmit={handleSubmit} className="mb-10 flex gap-3">
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

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-8">
          {/* Answer */}
          <section>
            <h2 className="mb-3 text-lg font-semibold">Answer</h2>
            <div className="prose prose-zinc dark:prose-invert max-w-none rounded-lg border border-zinc-200 p-5 dark:border-zinc-800">
              <ReactMarkdown>{result.answer}</ReactMarkdown>
            </div>
          </section>

          {/* Sources */}
          <section>
            <h2 className="mb-3 text-lg font-semibold">Sources</h2>
            <ul className="space-y-2">
              {result.sources.map((src, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-800"
                >
                  <span className="truncate font-mono text-sm">
                    {src.filename}
                  </span>
                  <span className="ml-4 shrink-0 text-sm text-zinc-500">
                    {(src.similarity * 100).toFixed(1)}% match
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}
