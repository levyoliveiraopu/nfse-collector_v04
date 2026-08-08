# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS base
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /repo
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web-app/package.json apps/web-app/package.json
RUN pnpm install --frozen-lockfile --filter web-app...

FROM base AS builder
ARG NEXT_PUBLIC_API_BASE_URL=/api
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/apps/web-app/node_modules ./apps/web-app/node_modules
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web-app ./apps/web-app
RUN mkdir -p apps/web-app/public && pnpm --filter web-app build

FROM node:20-alpine AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
RUN addgroup --system --gid 1003 nextjs && \
    adduser --system --uid 1003 --ingroup nextjs nextjs

COPY --from=builder /repo/apps/web-app/public ./apps/web-app/public
COPY --from=builder --chown=nextjs:nextjs /repo/apps/web-app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /repo/apps/web-app/.next/static ./apps/web-app/.next/static

USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "apps/web-app/server.js"]
