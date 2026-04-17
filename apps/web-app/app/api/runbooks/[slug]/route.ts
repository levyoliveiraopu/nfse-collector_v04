import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { isRunbookSlug } from "@/lib/occurrences/codes";

// Runtime Node: precisamos de `fs` para ler o arquivo markdown do repo.
export const runtime = "nodejs";
// Runbooks sao estaticos (arquivos versionados em `docs/runbooks/`).
// Cache agressivo em producao; revalida em dev.
export const revalidate = 3600;

const REPO_ROOT = path.resolve(process.cwd(), "..", "..");
const RUNBOOKS_DIR = path.join(REPO_ROOT, "docs", "runbooks");

export async function GET(
  _req: Request,
  { params }: { params: { slug: string } },
): Promise<NextResponse> {
  // Allowlist: o slug precisa ser um dos catalogados em
  // `lib/occurrences/codes.ts`. Evita path traversal e vazamento de
  // arquivos fora de `docs/runbooks/`.
  if (!isRunbookSlug(params.slug)) {
    return NextResponse.json(
      { detail: "runbook nao encontrado" },
      { status: 404 },
    );
  }

  const filePath = path.join(RUNBOOKS_DIR, `${params.slug}.md`);
  try {
    const content = await readFile(filePath, "utf-8");
    return new NextResponse(content, {
      status: 200,
      headers: {
        "Content-Type": "text/markdown; charset=utf-8",
        "Cache-Control": "public, max-age=300, stale-while-revalidate=3600",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "runbook indisponivel" },
      { status: 404 },
    );
  }
}
