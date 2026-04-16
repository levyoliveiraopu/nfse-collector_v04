"use client";

import { CalendarClock } from "lucide-react";

import type { Company } from "@/lib/api/companies";

/**
 * Stub da aba "Agendamentos". Schema da tabela ja existe (DATA-05);
 * endpoints REST e UI de criacao/edicao chegam em APP-08 / API-09.
 */
export function SchedulesTab({ company }: { company: Company }) {
  return (
    <div
      className="flex items-start gap-3 rounded-lg border border-border bg-card p-6 text-sm shadow-sm"
      data-tab-content="schedules"
      data-company-id={company.id}
    >
      <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div>
        <p className="font-medium">Agendamentos chegam em APP-08</p>
        <p className="mt-1 text-muted-foreground">
          A tabela <code className="font-mono">schedules</code> ja existe no
          banco (DATA-05). O CRUD REST e a UI de criar/editar agendamentos
          serao entregues em API-09 e APP-08.
        </p>
      </div>
    </div>
  );
}
