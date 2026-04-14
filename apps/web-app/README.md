# web-app

Painel logado NFS-e SaaS — Next.js 14 (App Router) + TypeScript strict,
Tailwind CSS, shadcn/ui, Lucide e Sonner.

## Requisitos

- Node >= 20.11
- pnpm >= 9.12

## Scripts

Executar a partir da raiz do monorepo:

```bash
pnpm install
pnpm --filter web-app dev        # http://localhost:3000
pnpm --filter web-app build
pnpm --filter web-app start
pnpm --filter web-app lint
pnpm --filter web-app typecheck
```

## Adicionar componentes shadcn/ui

```bash
pnpm --filter web-app dlx shadcn@latest add button
```

O manifesto fica em `components.json` (aliases `@/components`, `@/lib/utils`).
