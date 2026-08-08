"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, BookOpen, Search } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { HelpArticle } from "@/components/help/help-article";
import { useHelp } from "@/components/help/help-provider";
import {
  HELP_CATALOG,
  normalizeHelpRole,
  normalizeSearchText,
  type HelpEntry,
} from "@/lib/help/catalog";
import { HelpInsightsPanel } from "./help-insights-panel";

type SearchDocument = { entry: HelpEntry; markdown: string; haystack: string };

export function AjudaView() {
  const { user } = useAuth();
  const { track } = useHelp();
  const role = normalizeHelpRole(user?.role);
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedSlug = searchParams.get("artigo");
  const [query, setQuery] = useState("");
  const [documents, setDocuments] = useState<SearchDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const lastTrackedQuery = useRef<string | null>(null);

  const allowedEntries = useMemo(
    () => HELP_CATALOG.filter((entry) => entry.roles.includes(role)),
    [role],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void Promise.all(
      allowedEntries.map(async (entry) => {
        let markdown = "";
        try {
          const response = await fetch(`/help/${entry.slug}.md`);
          if (response.ok) markdown = await response.text();
        } catch {
          // Titulo, resumo e palavras-chave continuam pesquisaveis.
        }
        const haystack = normalizeSearchText(
          [
            entry.title,
            entry.summary,
            entry.category,
            ...entry.keywords,
            markdown,
          ].join(" "),
        );
        return { entry, markdown, haystack };
      }),
    ).then((loaded) => {
      if (!cancelled) {
        setDocuments(loaded);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [allowedEntries]);

  const normalizedQuery = normalizeSearchText(query);
  const results = useMemo(() => {
    if (normalizedQuery.length < 2) return documents;
    const terms = normalizedQuery.split(/\s+/).filter(Boolean);
    return documents.filter((doc) =>
      terms.every((term) => doc.haystack.includes(term)),
    );
  }, [documents, normalizedQuery]);

  useEffect(() => {
    if (normalizedQuery.length < 2 || loading) return;
    const timeout = window.setTimeout(() => {
      if (lastTrackedQuery.current === normalizedQuery) return;
      lastTrackedQuery.current = normalizedQuery;
      track({ event_type: "search_performed", route_key: "help" });
      if (results.length === 0) {
        track({ event_type: "search_no_results", route_key: "help" });
      }
    }, 500);
    return () => window.clearTimeout(timeout);
  }, [loading, normalizedQuery, results.length, track]);

  const selected = requestedSlug
    ? allowedEntries.find((entry) => entry.slug === requestedSlug)
    : null;

  if (selected) {
    return (
      <div className="mx-auto max-w-4xl" data-help-id="help-search">
        <button
          type="button"
          onClick={() => router.push("/ajuda")}
          className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Voltar à pesquisa
        </button>
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm md:p-8">
          <p className="text-xs font-medium uppercase tracking-wide text-primary">
            {selected.category}
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">{selected.title}</h1>
          <p className="mt-2 text-muted-foreground">{selected.summary}</p>

          {selected.capabilitiesByRole[role].length ? (
            <div className="my-6 rounded-lg border border-primary/25 bg-primary/5 p-4">
              <h2 className="text-sm font-semibold">Para seu perfil: {role}</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {selected.capabilitiesByRole[role].map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <HelpArticle entry={selected} />
        </div>
      </div>
    );
  }

  const categories = Array.from(
    new Set(results.map((document) => document.entry.category)),
  );

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8" data-help-id="help-search">
      <header>
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <BookOpen className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Central de Ajuda</h1>
            <p className="text-sm text-muted-foreground">
              Pesquise uma tarefa, regra, status ou mensagem de erro.
            </p>
          </div>
        </div>

        <label className="relative mt-6 block" data-help-id="help-search-input">
          <span className="sr-only">Pesquisar na ajuda</span>
          <Search
            className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ex.: criar agendamento, certificado vencido, gerar Excel"
            className="h-12 w-full rounded-lg border border-input bg-background pl-12 pr-4 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>
        <p className="mt-2 text-xs text-muted-foreground">
          O texto pesquisado fica somente neste navegador.
        </p>
      </header>

      {loading ? (
        <p role="status" className="text-sm text-muted-foreground">
          Preparando artigos…
        </p>
      ) : results.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-8 text-center">
          <h2 className="font-semibold">Nenhum artigo encontrado</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Tente menos palavras ou pesquise pelo nome da seção.
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {categories.map((category) => (
            <section key={category} aria-labelledby={`category-${category}`}>
              <h2 id={`category-${category}`} className="mb-3 text-lg font-semibold">
                {category}
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {results
                  .filter((document) => document.entry.category === category)
                  .map(({ entry }) => (
                    <button
                      key={entry.slug}
                      type="button"
                      onClick={() => router.push(`/ajuda?artigo=${entry.slug}`)}
                      className="rounded-lg border border-border bg-card p-4 text-left shadow-sm transition hover:border-primary/40 hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <span className="font-semibold">{entry.title}</span>
                      <span className="mt-1 block text-sm text-muted-foreground">
                        {entry.summary}
                      </span>
                    </button>
                  ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {role === "owner" || role === "admin" ? <HelpInsightsPanel /> : null}
    </div>
  );
}
