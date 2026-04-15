"use client";

import { useState } from "react";

import { FileDropzone } from "@/components/ui/file-dropzone";

export function FileDropzoneDemo() {
  const [uploaded, setUploaded] = useState<string | null>(null);

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="space-y-2">
        <FileDropzone
          accept=".pfx,.p12"
          maxSize={5 * 1024 * 1024}
          label="Arraste o PFX A1 aqui ou clique para selecionar"
          hint="Formatos .pfx ou .p12 ate 5 MB"
          onUpload={async (file) => {
            // Simula upload para a API (APP-04).
            await new Promise((r) => setTimeout(r, 800));
            setUploaded(file.name);
          }}
        />
        <p className="text-xs text-muted-foreground">
          Ultimo upload simulado: <code>{uploaded ?? "—"}</code>
        </p>
      </div>

      <div>
        <FileDropzone
          accept=".csv"
          maxSize={1024 * 1024}
          label="Importar lista de empresas (.csv)"
          hint="Ate 1 MB"
          onUpload={async () => {
            await new Promise((r) => setTimeout(r, 400));
          }}
        />
      </div>
    </div>
  );
}
