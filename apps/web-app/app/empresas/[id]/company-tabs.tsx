"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { cn } from "@/lib/utils";
import type { Company } from "@/lib/api/companies";

// Lazy-load (DoD APP-03): cada painel so e baixado/montado quando a aba
// e selecionada pela primeira vez. React.lazy garante que o bundle do
// painel nao entre na rota inicial.
const OverviewTab = React.lazy(() =>
  import("./tabs/overview-tab").then((m) => ({ default: m.OverviewTab })),
);
const ExecutionsTab = React.lazy(() =>
  import("./tabs/executions-tab").then((m) => ({ default: m.ExecutionsTab })),
);
const CredentialTab = React.lazy(() =>
  import("./tabs/credential-tab").then((m) => ({ default: m.CredentialTab })),
);
const SchedulesTab = React.lazy(() =>
  import("./tabs/schedules-tab").then((m) => ({ default: m.SchedulesTab })),
);
const FilesTab = React.lazy(() =>
  import("./tabs/files-tab").then((m) => ({ default: m.FilesTab })),
);
const OccurrencesTab = React.lazy(() =>
  import("./tabs/occurrences-tab").then((m) => ({ default: m.OccurrencesTab })),
);

type TabId =
  | "overview"
  | "executions"
  | "credential"
  | "schedules"
  | "files"
  | "occurrences";

interface TabDef {
  id: TabId;
  label: string;
}

const TABS: readonly TabDef[] = [
  { id: "overview", label: "Visao geral" },
  { id: "executions", label: "Execucoes" },
  { id: "credential", label: "Credencial" },
  { id: "schedules", label: "Agendamentos" },
  { id: "files", label: "Arquivos" },
  { id: "occurrences", label: "Ocorrencias" },
];

const VALID_TAB_IDS = new Set<TabId>(TABS.map((t) => t.id));

function parseTabId(raw: string | null): TabId {
  if (raw && (VALID_TAB_IDS as Set<string>).has(raw)) return raw as TabId;
  return "overview";
}

export interface CompanyTabsProps {
  company: Company;
}

export function CompanyTabs({ company }: CompanyTabsProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchString = searchParams?.toString() ?? "";

  const active: TabId = parseTabId(searchParams?.get("tab") ?? null);

  // Mantem o conjunto de abas ja visitadas para preservar o estado dos
  // paineis montados (cache local ao usuario na sessao). Garante que
  // remontar uma aba nao perde state interno (ex: filtros de DataTable
  // futuros). O painel inativo continua oculto via CSS.
  const [mounted, setMounted] = React.useState<Set<TabId>>(
    () => new Set([active]),
  );

  React.useEffect(() => {
    setMounted((prev) => {
      if (prev.has(active)) return prev;
      const next = new Set(prev);
      next.add(active);
      return next;
    });
  }, [active]);

  const setTab = React.useCallback(
    (id: TabId) => {
      if (id === active) return;
      const sp = new URLSearchParams(searchString);
      if (id === "overview") sp.delete("tab");
      else sp.set("tab", id);
      const qs = sp.toString();
      router.replace(qs ? `${pathname}?${qs}` : (pathname ?? ""), {
        scroll: false,
      });
    },
    [active, searchString, pathname, router],
  );

  // Setas teclado para acessibilidade.
  const tablistRef = React.useRef<HTMLDivElement | null>(null);
  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const idx = TABS.findIndex((t) => t.id === active);
    if (idx < 0) return;
    let nextIdx = idx;
    if (event.key === "ArrowRight") nextIdx = (idx + 1) % TABS.length;
    else if (event.key === "ArrowLeft")
      nextIdx = (idx - 1 + TABS.length) % TABS.length;
    else if (event.key === "Home") nextIdx = 0;
    else if (event.key === "End") nextIdx = TABS.length - 1;
    else return;
    event.preventDefault();
    setTab(TABS[nextIdx].id);
    // Foca o tab recem-selecionado.
    requestAnimationFrame(() => {
      const node = tablistRef.current?.querySelector<HTMLButtonElement>(
        `[data-tab-id="${TABS[nextIdx].id}"]`,
      );
      node?.focus();
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <div
        ref={tablistRef}
        role="tablist"
        aria-label="Detalhes da empresa"
        onKeyDown={onKeyDown}
        className="flex flex-wrap gap-1 border-b border-border"
      >
        {TABS.map((tab) => {
          const isActive = tab.id === active;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              data-tab-id={tab.id}
              id={`tab-${tab.id}`}
              aria-selected={isActive}
              aria-controls={`panel-${tab.id}`}
              tabIndex={isActive ? 0 : -1}
              onClick={() => setTab(tab.id)}
              className={cn(
                "-mb-px inline-flex h-9 items-center rounded-t-md border-b-2 px-3 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {TABS.map((tab) => {
        const isActive = tab.id === active;
        const wasMounted = mounted.has(tab.id);
        return (
          <div
            key={tab.id}
            role="tabpanel"
            id={`panel-${tab.id}`}
            aria-labelledby={`tab-${tab.id}`}
            hidden={!isActive}
            data-state={isActive ? "active" : "inactive"}
            data-tab-panel={tab.id}
          >
            {wasMounted ? (
              <React.Suspense
                fallback={
                  <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
                    Carregando...
                  </div>
                }
              >
                <TabContent tabId={tab.id} company={company} />
              </React.Suspense>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function TabContent({
  tabId,
  company,
}: {
  tabId: TabId;
  company: Company;
}) {
  switch (tabId) {
    case "overview":
      return <OverviewTab company={company} />;
    case "executions":
      return <ExecutionsTab company={company} />;
    case "credential":
      return <CredentialTab company={company} />;
    case "schedules":
      return <SchedulesTab company={company} />;
    case "files":
      return <FilesTab company={company} />;
    case "occurrences":
      return <OccurrencesTab company={company} />;
  }
}
