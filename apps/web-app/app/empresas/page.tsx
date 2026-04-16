import { EmpresasView } from "./empresas-view";

export const metadata = {
  title: "Empresas — NFS-e SaaS",
};

export default function EmpresasPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Empresas</h1>
          <p className="text-sm text-muted-foreground">
            CNPJs cadastrados no tenant para coleta automatica de NFS-e.
          </p>
        </div>
      </header>

      <EmpresasView />
    </div>
  );
}
