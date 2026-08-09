"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, Check, ChevronLeft, Compass, ThumbsDown, ThumbsUp, X } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { Dialog } from "@/components/ui/dialog";
import {
  getRelatedEntries,
  normalizeHelpRole,
  type HelpEntry,
} from "@/lib/help/catalog";
import { cn } from "@/lib/utils";
import { HelpArticle } from "./help-article";
import { useHelp } from "./help-provider";

function useDesktopPanel(): boolean {
  const [desktop, setDesktop] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1280px)");
    const update = () => setDesktop(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return desktop;
}

export function HelpPanel() {
  const { open, closeHelp } = useHelp();
  const desktop = useDesktopPanel();

  useEffect(() => {
    if (!open || !desktop) return;
    const trigger = document.querySelector<HTMLElement>(
      '[data-help-id="help-button"]',
    );
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      closeHelp();
    };
    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
      window.requestAnimationFrame(() => trigger?.focus());
    };
  }, [closeHelp, desktop, open]);

  if (!open) return null;
  if (desktop) {
    return (
      <aside
        aria-label="Ajuda contextual"
        className="fixed bottom-0 right-0 top-14 z-30 w-[440px] border-l border-border bg-background shadow-xl"
      >
        <HelpPanelContent onClose={closeHelp} />
      </aside>
    );
  }

  return (
    <Dialog
      open={open}
      onClose={closeHelp}
      labelledBy="context-help-title"
      showCloseButton={false}
      className="h-[calc(100dvh-1rem)] max-w-none gap-0 overflow-hidden p-0 sm:max-w-xl"
    >
      <HelpPanelContent onClose={closeHelp} />
    </Dialog>
  );
}

function HelpPanelContent({ onClose }: { onClose: () => void }) {
  const { user } = useAuth();
  const {
    entry,
    routeEntry,
    showRouteArticle,
    startTour,
    viewArticle,
    track,
  } = useHelp();
  const role = normalizeHelpRole(user?.role);
  const related = getRelatedEntries(entry, role);
  const [feedback, setFeedback] = useState<"yes" | "no" | null>(null);

  useEffect(() => setFeedback(null), [entry.slug]);

  const sendFeedback = (value: "yes" | "no") => {
    if (feedback) return;
    setFeedback(value);
    track({
      event_type: value === "yes" ? "feedback_yes" : "feedback_no",
      article_slug: entry.slug,
      route_key: entry.routeKey,
    });
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="shrink-0 border-b border-border px-5 py-4">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            {entry.slug !== routeEntry.slug ? (
              <button
                type="button"
                onClick={showRouteArticle}
                className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <ChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />
                Voltar à ajuda desta página
              </button>
            ) : null}
            <p className="text-xs font-medium uppercase tracking-wide text-primary">
              {entry.category}
            </p>
            <h2 id="context-help-title" className="mt-1 text-xl font-semibold tracking-tight">
              {entry.title}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">{entry.summary}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar ajuda"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {entry.tourSteps?.length ? (
          <button
            type="button"
            onClick={startTour}
            className="mt-4 inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Compass className="h-4 w-4" aria-hidden="true" />
            Guie-me nesta tela
          </button>
        ) : null}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {entry.capabilitiesByRole[role].length ? (
          <section
            aria-labelledby="role-capabilities-title"
            className="mb-5 rounded-lg border border-primary/25 bg-primary/5 p-3"
          >
            <h3 id="role-capabilities-title" className="text-sm font-semibold">
              Para seu perfil: {role}
            </h3>
            <ul className="mt-2 space-y-1.5 text-sm text-muted-foreground">
              {entry.capabilitiesByRole[role].map((capability) => (
                <li key={capability} className="flex gap-2">
                  <Check className="mt-1 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
                  <span>{capability}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <HelpArticle entry={entry} />

        {related.length ? (
          <section className="mt-6 border-t border-border pt-4" aria-labelledby="related-help-title">
            <h3 id="related-help-title" className="text-sm font-semibold">
              Assuntos relacionados
            </h3>
            <div className="mt-2 flex flex-col gap-2">
              {related.map((item) => (
                <button
                  key={item.slug}
                  type="button"
                  onClick={() => viewArticle(item.slug)}
                  className="rounded-md border border-border px-3 py-2 text-left text-sm transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="font-medium">{item.title}</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {item.summary}
                  </span>
                </button>
              ))}
            </div>
          </section>
        ) : null}

        <section className="mt-6 rounded-lg bg-muted/50 p-4 text-center">
          {feedback ? (
            <p className="inline-flex items-center gap-2 text-sm font-medium" role="status">
              <Check className="h-4 w-4 text-primary" aria-hidden="true" />
              Obrigado pela resposta.
            </p>
          ) : (
            <>
              <p className="text-sm font-medium">Isso ajudou?</p>
              <div className="mt-2 flex justify-center gap-2">
                <FeedbackButton label="Sim" onClick={() => sendFeedback("yes")} icon={ThumbsUp} />
                <FeedbackButton label="Não" onClick={() => sendFeedback("no")} icon={ThumbsDown} />
              </div>
            </>
          )}
        </section>
      </div>

      <footer className="shrink-0 border-t border-border p-3">
        <Link
          href="/ajuda"
          onClick={onClose}
          className={cn(
            "flex h-9 items-center justify-center gap-2 rounded-md border border-border text-sm font-medium transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
        >
          <BookOpen className="h-4 w-4" aria-hidden="true" />
          Abrir Central de Ajuda
        </Link>
      </footer>
    </div>
  );
}

function FeedbackButton({
  label,
  onClick,
  icon: Icon,
}: {
  label: string;
  onClick: () => void;
  icon: typeof ThumbsUp;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-xs font-medium transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </button>
  );
}
