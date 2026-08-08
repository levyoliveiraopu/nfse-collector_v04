"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth/auth-provider";
import { recordHelpEvent, type HelpEvent } from "@/lib/api/help";
import {
  HELP_CATALOG,
  HELP_VERSION,
  resolveHelpEntry,
  type HelpEntry,
} from "@/lib/help/catalog";

type HelpContextValue = {
  entry: HelpEntry;
  routeEntry: HelpEntry;
  open: boolean;
  isNew: boolean;
  activeTour: HelpEntry | null;
  openHelp: () => void;
  closeHelp: () => void;
  viewArticle: (slug: string) => void;
  showRouteArticle: () => void;
  startTour: () => void;
  finishTour: () => void;
  track: (event: HelpEvent) => void;
};

const HelpContext = createContext<HelpContextValue | null>(null);

export function HelpProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, accessToken, refresh } = useAuth();
  const routeEntry = useMemo(
    () => resolveHelpEntry(pathname, user?.role),
    [pathname, user?.role],
  );
  const [open, setOpen] = useState(false);
  const [isNew, setIsNew] = useState(true);
  const [articleOverride, setArticleOverride] = useState<string | null>(null);
  const [activeTour, setActiveTour] = useState<HelpEntry | null>(null);
  const trackedOpenRef = useRef<string | null>(null);

  const storageKey = user
    ? `nfse:help:opened:${user.tenantId}:${user.userId}:v${HELP_VERSION}`
    : null;

  useEffect(() => {
    if (!storageKey) {
      setIsNew(false);
      return;
    }
    try {
      setIsNew(window.localStorage.getItem(storageKey) !== "1");
    } catch {
      setIsNew(true);
    }
  }, [storageKey]);

  useEffect(() => {
    setArticleOverride(null);
    setActiveTour(null);
    trackedOpenRef.current = null;
  }, [pathname]);

  const entry = useMemo(
    () =>
      (articleOverride
        ? HELP_CATALOG.find((candidate) => candidate.slug === articleOverride)
        : null) ?? routeEntry,
    [articleOverride, routeEntry],
  );

  const track = useCallback(
    (event: HelpEvent) => {
      if (
        !accessToken ||
        routeEntry.routeKey === "access" ||
        event.route_key === "access"
      ) return;
      void recordHelpEvent(
        {
          accessToken,
          onTokenRefreshed: () => {
            void refresh();
          },
        },
        event,
      ).catch(() => {
        // Telemetria nunca bloqueia a ajuda nem gera ruido visual.
      });
    },
    [accessToken, refresh, routeEntry.routeKey],
  );

  useEffect(() => {
    if (!open || entry.routeKey === "access") return;
    const marker = `${pathname}:${entry.slug}`;
    if (trackedOpenRef.current === marker) return;
    trackedOpenRef.current = marker;
    track({
      event_type: "article_opened",
      article_slug: entry.slug,
      route_key: entry.routeKey,
    });
  }, [entry, open, pathname, track]);

  const markOpened = useCallback(() => {
    if (!storageKey) return;
    try {
      window.localStorage.setItem(storageKey, "1");
    } catch {
      // O selo some nesta sessao mesmo se storage estiver bloqueado.
    }
    setIsNew(false);
  }, [storageKey]);

  const openHelp = useCallback(() => {
    markOpened();
    setOpen(true);
  }, [markOpened]);

  const closeHelp = useCallback(() => {
    setOpen(false);
    trackedOpenRef.current = null;
  }, []);

  const viewArticle = useCallback((slug: string) => {
    if (!HELP_CATALOG.some((candidate) => candidate.slug === slug)) return;
    trackedOpenRef.current = null;
    setArticleOverride(slug);
    setOpen(true);
  }, []);

  const showRouteArticle = useCallback(() => {
    trackedOpenRef.current = null;
    setArticleOverride(null);
    setOpen(true);
  }, []);

  const startTour = useCallback(() => {
    if (!entry.tourId || !entry.tourSteps?.length) return;
    setOpen(false);
    setActiveTour(entry);
    track({
      event_type: "tour_started",
      article_slug: entry.slug,
      route_key: entry.routeKey,
      tour_id: entry.tourId,
    });
  }, [entry, track]);

  const finishTour = useCallback(() => setActiveTour(null), []);

  const value = useMemo<HelpContextValue>(
    () => ({
      entry,
      routeEntry,
      open,
      isNew,
      activeTour,
      openHelp,
      closeHelp,
      viewArticle,
      showRouteArticle,
      startTour,
      finishTour,
      track,
    }),
    [
      entry,
      routeEntry,
      open,
      isNew,
      activeTour,
      openHelp,
      closeHelp,
      viewArticle,
      showRouteArticle,
      startTour,
      finishTour,
      track,
    ],
  );

  return <HelpContext.Provider value={value}>{children}</HelpContext.Provider>;
}

export function useHelp(): HelpContextValue {
  const value = useContext(HelpContext);
  if (!value) {
    throw new Error("useHelp deve ser usado dentro de <HelpProvider>.");
  }
  return value;
}
