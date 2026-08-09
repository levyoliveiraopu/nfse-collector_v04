"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { HelpEntry } from "@/lib/help/catalog";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; markdown: string }
  | { status: "error" };

export function HelpArticle({ entry }: { entry: HelpEntry }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fetch(`/help/${entry.slug}.md`)
      .then(async (response) => {
        if (!response.ok) throw new Error("help_not_found");
        return response.text();
      })
      .then((markdown) => {
        if (!cancelled) setState({ status: "ready", markdown });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [entry.slug]);

  if (state.status === "loading") {
    return (
      <div role="status" className="space-y-3 py-3" aria-label="Carregando ajuda">
        <div className="h-4 w-36 animate-pulse rounded bg-muted" />
        <div className="h-3 w-full animate-pulse rounded bg-muted" />
        <div className="h-3 w-5/6 animate-pulse rounded bg-muted" />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
        Não foi possível carregar este artigo. Tente novamente ou abra a
        Central de Ajuda.
      </div>
    );
  }

  return (
    <article className="help-markdown text-sm leading-6 text-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target={href?.startsWith("http") ? "_blank" : undefined}
              rel={href?.startsWith("http") ? "noreferrer noopener" : undefined}
              className="font-medium text-primary underline underline-offset-4"
            >
              {children}
            </a>
          ),
        }}
      >
        {state.markdown}
      </ReactMarkdown>
    </article>
  );
}
