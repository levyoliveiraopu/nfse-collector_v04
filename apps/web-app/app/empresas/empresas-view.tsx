"use client";

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";

import { EmpresasTable, EMPRESAS_QUERY_KEY } from "./empresas-table";
import { NovaEmpresaDialog } from "./nova-empresa-dialog";

const WRITE_ROLES = new Set(["owner", "admin", "operator"]);

/**
 * View client da listagem `/empresas`. Encapsula:
 * - botao "Nova empresa" (visivel para owner/admin/operator),
 * - dialog de criacao,
 * - DataTable que invalida o cache react-query apos criar.
 */
export function EmpresasView() {
  const { user } = useAuth();
  const canWrite = user ? WRITE_ROLES.has(user.role) : false;

  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const handleCreated = useCallback(() => {
    setDialogOpen(false);
    void queryClient.invalidateQueries({ queryKey: [EMPRESAS_QUERY_KEY] });
  }, [queryClient]);

  return (
    <div className="flex flex-col gap-4" data-help-id="companies-primary">
      <div className="flex justify-end">
        {canWrite ? (
          <button
            type="button"
            onClick={() => setDialogOpen(true)}
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Nova empresa
          </button>
        ) : null}
      </div>

      <EmpresasTable />

      {canWrite ? (
        <NovaEmpresaDialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          onCreated={handleCreated}
        />
      ) : null}
    </div>
  );
}
