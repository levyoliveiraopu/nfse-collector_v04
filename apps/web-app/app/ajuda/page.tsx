import { Suspense } from "react";

import { AjudaView } from "./ajuda-view";

export default function AjudaPage() {
  return (
    <Suspense
      fallback={<p className="text-sm text-muted-foreground">Carregando ajuda…</p>}
    >
      <AjudaView />
    </Suspense>
  );
}
