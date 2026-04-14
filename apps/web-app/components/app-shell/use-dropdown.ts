"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Hook minimo para popovers/dropdowns sem depender de Radix.
 * Fecha em clique fora e em Escape. Mantem foco trap simples via tabindex
 * nativo dos elementos do painel.
 */
export function useDropdown() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;

    function handlePointer(event: MouseEvent) {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  return { open, setOpen, containerRef };
}
