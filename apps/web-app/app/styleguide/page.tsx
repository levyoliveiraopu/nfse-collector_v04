import { ThemeToggle } from "@/components/theme-toggle";

const colorTokens: Array<{ name: string; varName: string }> = [
  { name: "background", varName: "--background" },
  { name: "foreground", varName: "--foreground" },
  { name: "card", varName: "--card" },
  { name: "popover", varName: "--popover" },
  { name: "primary", varName: "--primary" },
  { name: "secondary", varName: "--secondary" },
  { name: "muted", varName: "--muted" },
  { name: "accent", varName: "--accent" },
  { name: "destructive", varName: "--destructive" },
  { name: "success", varName: "--success" },
  { name: "warning", varName: "--warning" },
  { name: "border", varName: "--border" },
  { name: "input", varName: "--input" },
  { name: "ring", varName: "--ring" },
];

const typeScale = [
  { token: "text-xs", sample: "The quick brown fox — 12px" },
  { token: "text-sm", sample: "The quick brown fox — 14px" },
  { token: "text-base", sample: "The quick brown fox — 16px" },
  { token: "text-lg", sample: "The quick brown fox — 18px" },
  { token: "text-xl", sample: "The quick brown fox — 20px" },
  { token: "text-2xl", sample: "The quick brown fox — 24px" },
  { token: "text-3xl", sample: "The quick brown fox — 30px" },
  { token: "text-4xl", sample: "The quick brown fox — 36px" },
];

const radii = [
  { token: "rounded-sm", varName: "--radius-sm" },
  { token: "rounded-md", varName: "--radius-md" },
  { token: "rounded-lg", varName: "--radius-lg" },
  { token: "rounded-xl", varName: "--radius-xl" },
  { token: "rounded-2xl", varName: "--radius-2xl" },
  { token: "rounded-full", varName: "--radius-full" },
];

const shadows = [
  { token: "shadow-sm", varName: "--shadow-sm" },
  { token: "shadow-md", varName: "--shadow-md" },
  { token: "shadow-lg", varName: "--shadow-lg" },
  { token: "shadow-xl", varName: "--shadow-xl" },
];

const spacings = [
  { token: "p-1 (4px)", classes: "p-1" },
  { token: "p-2 (8px)", classes: "p-2" },
  { token: "p-3 (12px)", classes: "p-3" },
  { token: "p-4 (16px)", classes: "p-4" },
  { token: "p-6 (24px)", classes: "p-6" },
  { token: "p-8 (32px)", classes: "p-8" },
];

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function ColorSwatch({ name, varName }: { name: string; varName: string }) {
  return (
    <div className="flex flex-col gap-2">
      <div
        className="h-16 w-full rounded-md border border-border"
        style={{ backgroundColor: `hsl(var(${varName}))` }}
        aria-hidden="true"
      />
      <div className="flex flex-col">
        <span className="text-sm font-medium">{name}</span>
        <code className="text-xs text-muted-foreground">{varName}</code>
      </div>
    </div>
  );
}

export default function StyleguidePage() {
  return (
    <main className="mx-auto max-w-5xl space-y-12 p-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            Styleguide — Design Tokens
          </h1>
          <p className="text-sm text-muted-foreground">
            Amostras dos tokens do DS-02. Alterne light/dark no botao a
            direita.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <Section
        title="Cores"
        description="Cores em HSL (componentes). Consuma via `hsl(var(--x))` ou classes Tailwind."
      >
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
          {colorTokens.map((c) => (
            <ColorSwatch key={c.name} name={c.name} varName={c.varName} />
          ))}
        </div>
      </Section>

      <Section
        title="Tipografia"
        description="Inter (sans) + JetBrains Mono (mono) via next/font."
      >
        <div className="space-y-2 rounded-lg border border-border bg-card p-6 text-card-foreground">
          {typeScale.map((t) => (
            <p key={t.token} className={t.token}>
              <span className="text-muted-foreground">{t.token}</span>{" "}
              <span>— {t.sample}</span>
            </p>
          ))}
          <pre className="mt-4 rounded-md bg-muted p-3 font-mono text-sm text-muted-foreground">
            {`// JetBrains Mono
const tenant = "acme";
console.log(\`hello \${tenant}\`);`}
          </pre>
        </div>
      </Section>

      <Section title="Espacamento" description="Escala de 4px.">
        <div className="flex flex-wrap gap-4">
          {spacings.map((s) => (
            <div key={s.token} className="flex flex-col items-center gap-2">
              <div className={`rounded-md bg-primary/20 ${s.classes}`}>
                <div className="h-6 w-6 rounded-sm bg-primary" aria-hidden="true" />
              </div>
              <code className="text-xs text-muted-foreground">{s.token}</code>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Radius">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-6">
          {radii.map((r) => (
            <div key={r.token} className="flex flex-col items-center gap-2">
              <div
                className={`h-16 w-16 border border-border bg-secondary ${r.token}`}
                aria-hidden="true"
              />
              <code className="text-xs text-muted-foreground">{r.varName}</code>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Sombras">
        <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
          {shadows.map((s) => (
            <div key={s.token} className="flex flex-col items-center gap-3">
              <div
                className={`h-20 w-full rounded-md bg-card ${s.token}`}
                aria-hidden="true"
              />
              <code className="text-xs text-muted-foreground">{s.varName}</code>
            </div>
          ))}
        </div>
      </Section>

      <Section
        title="Componentes de exemplo"
        description="Combinacoes tipicas usando os tokens."
      >
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90"
          >
            Primario
          </button>
          <button
            type="button"
            className="inline-flex h-9 items-center rounded-md bg-secondary px-4 text-sm font-medium text-secondary-foreground shadow-sm transition hover:opacity-90"
          >
            Secundario
          </button>
          <button
            type="button"
            className="inline-flex h-9 items-center rounded-md bg-destructive px-4 text-sm font-medium text-destructive-foreground shadow-sm transition hover:opacity-90"
          >
            Destrutivo
          </button>
          <button
            type="button"
            className="inline-flex h-9 items-center rounded-md bg-success px-4 text-sm font-medium text-success-foreground shadow-sm transition hover:opacity-90"
          >
            Sucesso
          </button>
          <button
            type="button"
            className="inline-flex h-9 items-center rounded-md bg-warning px-4 text-sm font-medium text-warning-foreground shadow-sm transition hover:opacity-90"
          >
            Aviso
          </button>
          <button
            type="button"
            className="inline-flex h-9 items-center rounded-md border border-border bg-background px-4 text-sm font-medium text-foreground shadow-sm transition hover:bg-accent hover:text-accent-foreground"
          >
            Outline
          </button>
        </div>
      </Section>
    </main>
  );
}
