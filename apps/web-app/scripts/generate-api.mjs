#!/usr/bin/env node
/**
 * DS-09 — gerador do client TS tipado a partir do OpenAPI da API.
 *
 * Uso:
 *   pnpm --filter web-app generate-api            # default: http://localhost:8000/openapi.json
 *   pnpm --filter web-app generate-api --url X    # override da URL
 *   API_OPENAPI_URL=... pnpm --filter web-app generate-api
 *   pnpm --filter web-app generate-api --file /tmp/openapi.json  # lê do disco
 *
 * Escreve `lib/api/generated/schema.d.ts`. Idempotente:
 * reexecutar sem mudancas na API nao altera o arquivo (byte a byte).
 */
import { readFile, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_PATH = resolve(__dirname, "..", "lib", "api", "generated", "schema.d.ts");

function parseArgs(argv) {
  const args = { url: null, file: null };
  for (let i = 2; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") args.url = argv[++i];
    else if (a.startsWith("--url=")) args.url = a.slice("--url=".length);
    else if (a === "--file") args.file = argv[++i];
    else if (a.startsWith("--file=")) args.file = a.slice("--file=".length);
  }
  return args;
}

async function resolveInput() {
  const args = parseArgs(process.argv);
  if (args.file) {
    const abs = resolve(process.cwd(), args.file);
    if (!existsSync(abs)) {
      throw new Error(`arquivo OpenAPI nao encontrado: ${abs}`);
    }
    const raw = readFileSync(abs, "utf8");
    return { source: abs, doc: JSON.parse(raw) };
  }
  const url =
    args.url ?? process.env.API_OPENAPI_URL ?? "http://localhost:8000/openapi.json";
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`falha ao baixar OpenAPI de ${url}: HTTP ${res.status}`);
  }
  return { source: url, doc: await res.json() };
}

const HEADER = `/**
 * AUTO-GERADO por scripts/generate-api.mjs (DS-09).
 * NAO EDITAR MANUALMENTE — reexecute \`pnpm --filter web-app generate-api\`.
 */
/* eslint-disable */
`;

async function main() {
  const { source, doc } = await resolveInput();
  const ast = await openapiTS(doc);
  const body = astToString(ast);
  const next = `${HEADER}\n${body}`;

  let prev = null;
  if (existsSync(OUT_PATH)) {
    prev = await readFile(OUT_PATH, "utf8");
  }

  if (prev === next) {
    console.log(`[generate-api] sem mudancas (fonte: ${source})`);
    return;
  }

  await writeFile(OUT_PATH, next, "utf8");
  console.log(`[generate-api] escrito ${OUT_PATH} (fonte: ${source})`);
}

main().catch((err) => {
  console.error("[generate-api] erro:", err.message ?? err);
  process.exit(1);
});
