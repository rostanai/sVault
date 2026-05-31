"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { askSvault, type AskResponse, type AskSource } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sparkles, Send, Loader2, FileText } from "lucide-react";
import { toast } from "sonner";

interface Props {
  token: string;
}

type MessageRole = "user" | "assistant";

interface Message {
  id: string;
  role: MessageRole;
  content: string;
  sources?: AskSource[];
  isError?: boolean;
}

const EXAMPLE_QUESTIONS = [
  "Which policies expire in the next 30 days?",
  "What is the sum insured on my fleet vehicles?",
  "Do any policies cover flood damage?",
  "List all active employee group health policies.",
];

let msgCounter = 0;
function nextId(): string {
  return `msg-${++msgCounter}`;
}

export default function AskClient({ token }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom whenever messages change or loading state toggles
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || loading) return;

      const userMsg: Message = {
        id: nextId(),
        role: "user",
        content: trimmed,
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);

      // Auto-resize the textarea back to single line
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }

      try {
        const res: AskResponse = await askSvault(token, trimmed);
        const assistantMsg: Message = {
          id: nextId(),
          role: "assistant",
          content: res.answer,
          sources: res.sources,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch {
        // apiFetch already showed a toast (including 402 entitlement_required)
        const errorMsg: Message = {
          id: nextId(),
          role: "assistant",
          content: "Sorry, I couldn't answer that right now. Please try again.",
          isError: true,
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setLoading(false);
        // Re-focus the input after response
        setTimeout(() => textareaRef.current?.focus(), 50);
      }
    },
    [loading, token]
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  function handleTextareaChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    // Auto-grow
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-h-[900px]">
      {/* Header */}
      <div className="shrink-0 pb-4 border-b border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold tracking-tight">Ask sVault</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              AI-powered answers grounded in your policy documents
            </p>
          </div>
        </div>
      </div>

      {/* Conversation area */}
      <div className="flex-1 overflow-y-auto py-6 space-y-6">
        {isEmpty ? (
          <EmptyState onSelectQuestion={sendMessage} />
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {loading && <TypingIndicator />}
          </>
        )}
        <div ref={bottomRef} aria-hidden="true" />
      </div>

      {/* Input area — pinned at bottom */}
      <div className="shrink-0 pt-4 border-t border-zinc-200 dark:border-zinc-800">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(input);
          }}
          className="flex items-end gap-2"
        >
          <label htmlFor="ask-input" className="sr-only">
            Ask a question about your insurance policies
          </label>
          <textarea
            id="ask-input"
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your insurance policies…"
            disabled={loading}
            aria-label="Ask a question"
            className={cn(
              "flex-1 resize-none rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm",
              "placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-600/40 focus:border-brand-600/60",
              "dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "transition-[height] min-h-[48px] max-h-[160px] overflow-y-auto"
            )}
          />
          <Button
            type="submit"
            size="icon"
            disabled={loading || !input.trim()}
            aria-label="Send message"
            className="h-12 w-12 shrink-0 rounded-xl bg-brand-600 hover:bg-brand-700 text-white disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </Button>
        </form>
        <p className="mt-2 text-center text-[11px] text-zinc-400 dark:text-zinc-600">
          Shift + Enter for a new line &middot; Enter to send
        </p>
      </div>
    </div>
  );
}

// ── Empty / hero state ────────────────────────────────────────────────────────

function EmptyState({
  onSelectQuestion,
}: {
  onSelectQuestion: (q: string) => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4 py-12">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-600/10 dark:bg-brand-600/20 mb-5">
        <Sparkles className="h-8 w-8 text-brand-600" />
      </div>
      <h3 className="text-2xl font-bold tracking-tight mb-2">Ask sVault</h3>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm mb-8">
        Ask anything about your insurance policies — coverage, expiry, premiums,
        exclusions.
      </p>
      <div className="flex flex-wrap justify-center gap-2 max-w-lg">
        {EXAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onSelectQuestion(q)}
            className={cn(
              "rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-700",
              "hover:border-brand-600/50 hover:bg-brand-600/5 hover:text-brand-700",
              "dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300",
              "dark:hover:border-brand-600/40 dark:hover:bg-brand-600/10 dark:hover:text-brand-400",
              "transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
            )}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 mt-0.5"
          aria-hidden="true"
        >
          <Sparkles className="h-4 w-4 text-white" />
        </div>
      )}

      <div className={cn("flex flex-col gap-2 max-w-[80%]", isUser && "items-end")}>
        {/* Role label */}
        <span className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500 px-1">
          {isUser ? "You" : "sVault AI"}
        </span>

        {/* Bubble */}
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "bg-brand-600 text-white rounded-tr-sm"
              : cn(
                  "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 rounded-tl-sm",
                  message.isError && "border border-red-200 dark:border-red-900/50"
                )
          )}
        >
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Sources */}
        {!isUser &&
          message.sources &&
          message.sources.length > 0 && (
            <SourcesList sources={message.sources} />
          )}
      </div>
    </div>
  );
}

// ── Sources section ───────────────────────────────────────────────────────────

function SourcesList({ sources }: { sources: AskSource[] }) {
  return (
    <div className="mt-1 px-1">
      <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-400 dark:text-zinc-500 mb-1.5">
        Sources
      </p>
      <div className="flex flex-col gap-1.5">
        {sources.map((src, idx) => {
          const snippet =
            src.snippet.length > 120
              ? `${src.snippet.slice(0, 120)}…`
              : src.snippet;
          return (
            <Link
              key={`${src.policy_id}-${idx}`}
              href={`/app/policies/${src.policy_id}`}
              className="group block"
              aria-label={`View policy source: ${snippet}`}
            >
              <div
                className={cn(
                  "flex items-start gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2",
                  "dark:border-zinc-700 dark:bg-zinc-900",
                  "group-hover:border-brand-600/40 group-hover:bg-brand-600/5 dark:group-hover:bg-brand-600/10",
                  "transition-colors"
                )}
              >
                <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-zinc-400 group-hover:text-brand-600" />
                <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
                  {snippet}
                </p>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

// ── Typing indicator ──────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex gap-3 justify-start" aria-live="polite" aria-label="sVault AI is thinking">
      <div
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 mt-0.5"
        aria-hidden="true"
      >
        <Sparkles className="h-4 w-4 text-white" />
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500 px-1">
          sVault AI
        </span>
        <div className="rounded-2xl rounded-tl-sm bg-zinc-100 dark:bg-zinc-800 px-4 py-3">
          <div className="flex items-center gap-1.5" aria-hidden="true">
            <span className="h-2 w-2 rounded-full bg-zinc-400 animate-bounce [animation-delay:0ms]" />
            <span className="h-2 w-2 rounded-full bg-zinc-400 animate-bounce [animation-delay:150ms]" />
            <span className="h-2 w-2 rounded-full bg-zinc-400 animate-bounce [animation-delay:300ms]" />
          </div>
        </div>
      </div>
    </div>
  );
}
