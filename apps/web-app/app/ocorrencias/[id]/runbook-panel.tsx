"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpen } from "lucide-react";

import type { RunbookSlug } from "@/lib/occurrences/codes";

export interface RunbookPanelProps {
  slug: RunbookSlug | null;
  code: string;
}

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; content: string }
  | { kind: "error" };

/**
 * Carrega e renderiza o runbook `docs/runbooks/<slug>.md` para o codigo
 * da ocorrencia. Faz GET em `/api/runbooks/<slug>` (route handler que le
 * o MD do disco — server only, allowlist por slug). Renderiza com
 * `react-markdown` + GFM. Mostra fallback quando o codigo nao e
 * catalogado.
 */
export function RunbookPanel({ slug, code }: RunbookPanelProps) {
  const [state, setState] = React.useState<State>({ kind: "idle" });

  React.useEffect(() => {
    if (!slug) {
      setState({ kind: "idle" });
      return;
    }
    setState({ kind: "loading" });
    const controller = new AbortController();
    fetch(`/api/runbooks/${slug}`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`status ${res.status}`);
        return res.text();
      })
      .then((content) => setState({ kind: "ok", content }))
      .catch((err) => {
        if ((err as { name?: string }).name === "AbortError") return;
        setState({ kind: "error" });
      });
    return () => controller.abort();
  }, [slug]);

  return (
    <section
      aria-label="Runbook"
      data-runbook-slug={slug ?? undefined}
      className="rounded-lg border border-border bg-card p-5 text-sm shadow-sm"
    >
      <header className="mb-3 flex items-center gap-2">
        <BookOpen
          className="h-4 w-4 text-muted-foreground"
          aria-hidden="true"
        />
        <h2 className="text-base font-semibold tracking-tight">
          Como resolver
        </h2>
      </header>

      {slug === null ? (
        <p className="text-muted-foreground">
          Codigo <code className="font-mono">{code}</code> nao tem runbook
          catalogado. Registre o incidente e abra uma issue em
          engenharia para promover este codigo em{" "}
          <code className="font-mono">
            docs/architecture/occurrence-codes.md
          </code>
          .
        </p>
      ) : state.kind === "loading" || state.kind === "idle" ? (
        <p className="text-muted-foreground">Carregando runbook...</p>
      ) : state.kind === "error" ? (
        <p className="text-destructive">
          Nao foi possivel carregar o runbook{" "}
          <code className="font-mono">{slug}</code>.
        </p>
      ) : (
        <div className="runbook-body" data-testid="runbook-content">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: (props) => (
                <h1
                  {...props}
                  className="mb-3 text-xl font-semibold tracking-tight"
                />
              ),
              h2: (props) => (
                <h2
                  {...props}
                  className="mb-2 mt-5 text-base font-semibold tracking-tight"
                />
              ),
              h3: (props) => (
                <h3
                  {...props}
                  className="mb-2 mt-4 text-sm font-semibold tracking-tight"
                />
              ),
              p: (props) => (
                <p {...props} className="mb-3 leading-6 text-foreground" />
              ),
              ul: (props) => (
                <ul
                  {...props}
                  className="mb-3 list-disc space-y-1 pl-5 text-foreground"
                />
              ),
              ol: (props) => (
                <ol
                  {...props}
                  className="mb-3 list-decimal space-y-1 pl-5 text-foreground"
                />
              ),
              li: (props) => <li {...props} className="leading-6" />,
              code: ({ children, ...rest }) => (
                <code
                  {...rest}
                  className="rounded bg-muted px-1 py-0.5 font-mono text-[12px]"
                >
                  {children}
                </code>
              ),
              pre: (props) => (
                <pre
                  {...props}
                  className="mb-3 overflow-x-auto rounded-md border border-border bg-muted/40 p-3 text-xs"
                />
              ),
              a: (props) => (
                <a
                  {...props}
                  className="text-primary hover:underline"
                  target="_blank"
                  rel="noreferrer"
                />
              ),
              blockquote: (props) => (
                <blockquote
                  {...props}
                  className="mb-3 border-l-2 border-border pl-3 italic text-muted-foreground"
                />
              ),
            }}
          >
            {state.content}
          </ReactMarkdown>
        </div>
      )}
    </section>
  );
}
