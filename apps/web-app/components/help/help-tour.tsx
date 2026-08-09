"use client";

import { useMemo, useRef } from "react";
import {
  EVENTS,
  Joyride,
  STATUS,
  type EventData,
  type Step,
} from "react-joyride";

import { useHelp } from "./help-provider";

export function HelpTour() {
  const { activeTour, finishTour, track } = useHelp();
  const failedRef = useRef(false);

  const steps = useMemo<Step[]>(() => {
    if (!activeTour?.tourSteps) return [];
    return activeTour.tourSteps.map((step) => ({
      target: step.target,
      title: step.title,
      content: step.content,
      placement: step.placement,
      data: { id: step.id },
    }));
  }, [activeTour]);

  if (!activeTour?.tourId || steps.length === 0) return null;

  const handleEvent = (event: EventData) => {
    if (event.type === EVENTS.TARGET_NOT_FOUND && !failedRef.current) {
      failedRef.current = true;
      track({
        event_type: "tour_failed",
        article_slug: activeTour.slug,
        route_key: activeTour.routeKey,
        tour_id: activeTour.tourId,
      });
    }
    if (event.type !== EVENTS.TOUR_END) return;
    track({
      event_type:
        event.status === STATUS.SKIPPED ? "tour_skipped" : "tour_completed",
      article_slug: activeTour.slug,
      route_key: activeTour.routeKey,
      tour_id: activeTour.tourId,
    });
    failedRef.current = false;
    finishTour();
  };

  return (
    <Joyride
      run
      continuous
      scrollToFirstStep
      steps={steps}
      onEvent={handleEvent}
      locale={{
        back: "Voltar",
        close: "Fechar",
        last: "Concluir",
        next: "Próximo",
        nextWithProgress: "Próximo ({current} de {total})",
        skip: "Sair do guia",
      }}
      options={{
        blockTargetInteraction: true,
        buttons: ["back", "skip", "primary"],
        closeButtonAction: "skip",
        dismissKeyAction: "close",
        overlayClickAction: false,
        showProgress: true,
        skipBeacon: true,
        targetWaitTimeout: 1200,
        primaryColor: "hsl(142 71% 35%)",
        zIndex: 100,
      }}
    />
  );
}
