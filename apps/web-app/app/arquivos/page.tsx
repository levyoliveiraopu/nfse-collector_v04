import { ArquivosView } from "./arquivos-view";

export const metadata = {
  title: "Arquivos — NFS-e SaaS",
};

export default function ArquivosPage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Arquivos</h1>
        <p className="text-sm text-muted-foreground">
          XMLs coletados, exports ZIP e relatorios gerados pelo tenant.
        </p>
      </header>

      <ArquivosView />
    </div>
  );
}
