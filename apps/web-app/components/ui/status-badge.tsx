import * as React from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock,
  KeyRound,
  Loader2,
  RefreshCw,
  ShieldAlert,
  WifiOff,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

export type StatusBadgeVariant =
  | "success"
  | "processing"
  | "pending"
  | "failed"
  | "warning"
  | "blocked"
  | "cert_expiring"
  | "cred_invalid"
  | "portal_unstable"
  | "reprocess_needed";

export type StatusBadgeSize = "sm" | "md";

type VariantSpec = {
  label: string;
  Icon: LucideIcon;
  /** Classes de cor aplicadas ao container. Usam tokens do DS-02. */
  classes: string;
  /** Descricao curta para tooltip (atributo `title`). */
  tooltip: string;
  /** Se o icone deve girar (ex.: processing). */
  spin?: boolean;
};

const VARIANTS: Record<StatusBadgeVariant, VariantSpec> = {
  success: {
    label: "Sucesso",
    Icon: CheckCircle2,
    classes:
      "bg-success/10 text-success border-success/30 dark:bg-success/15",
    tooltip: "Execucao concluida com sucesso.",
  },
  processing: {
    label: "Processando",
    Icon: Loader2,
    classes:
      "bg-primary/10 text-primary border-primary/30 dark:bg-primary/15",
    tooltip: "Execucao em andamento.",
    spin: true,
  },
  pending: {
    label: "Pendente",
    Icon: Clock,
    classes:
      "bg-muted text-muted-foreground border-border",
    tooltip: "Aguardando inicio ou recursos.",
  },
  failed: {
    label: "Falhou",
    Icon: XCircle,
    classes:
      "bg-destructive/10 text-destructive border-destructive/30 dark:bg-destructive/15",
    tooltip: "Execucao falhou. Verifique os detalhes.",
  },
  warning: {
    label: "Atencao",
    Icon: AlertTriangle,
    classes:
      "bg-warning/15 text-warning-foreground border-warning/40 dark:text-warning",
    tooltip: "Execucao concluida com avisos.",
  },
  blocked: {
    label: "Bloqueado",
    Icon: Ban,
    classes:
      "bg-muted text-muted-foreground border-border",
    tooltip: "Execucao bloqueada por dependencia ou politica.",
  },
  cert_expiring: {
    label: "Cert. expirando",
    Icon: ShieldAlert,
    classes:
      "bg-warning/15 text-warning-foreground border-warning/40 dark:text-warning",
    tooltip: "Certificado A1 proximo do vencimento.",
  },
  cred_invalid: {
    label: "Credencial invalida",
    Icon: KeyRound,
    classes:
      "bg-destructive/10 text-destructive border-destructive/30 dark:bg-destructive/15",
    tooltip: "Credencial recusada pelo portal. Ver runbook.",
  },
  portal_unstable: {
    label: "Portal instavel",
    Icon: WifiOff,
    classes:
      "bg-warning/15 text-warning-foreground border-warning/40 dark:text-warning",
    tooltip: "Portal da prefeitura indisponivel ou com rate-limit.",
  },
  reprocess_needed: {
    label: "Reprocessar",
    Icon: RefreshCw,
    classes:
      "bg-primary/10 text-primary border-primary/30 dark:bg-primary/15",
    tooltip: "Ocorrencia requer reprocessamento manual.",
  },
};

const SIZE_CLASSES: Record<StatusBadgeSize, string> = {
  sm: "h-5 gap-1 px-1.5 text-[11px]",
  md: "h-6 gap-1.5 px-2 text-xs",
};

const ICON_SIZE: Record<StatusBadgeSize, string> = {
  sm: "h-3 w-3",
  md: "h-3.5 w-3.5",
};

export interface StatusBadgeProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> {
  variant: StatusBadgeVariant;
  size?: StatusBadgeSize;
  /** Sobrescreve o rotulo padrao da variante. */
  label?: string;
  /** Sobrescreve o tooltip padrao (atributo `title`). */
  tooltip?: string;
  /** Oculta o icone. */
  hideIcon?: boolean;
}

/**
 * StatusBadge (DS-04) — badge compacto para status de execucoes,
 * credenciais e ocorrencias. Tooltip via atributo `title` nativo.
 */
export const StatusBadge = React.forwardRef<HTMLSpanElement, StatusBadgeProps>(
  function StatusBadge(
    {
      variant,
      size = "md",
      label,
      tooltip,
      hideIcon = false,
      className,
      ...rest
    },
    ref,
  ) {
    const spec = VARIANTS[variant];
    const { Icon, spin } = spec;
    const text = label ?? spec.label;
    const title = tooltip ?? spec.tooltip;

    return (
      <span
        ref={ref}
        role="status"
        aria-label={text}
        title={title}
        data-variant={variant}
        data-size={size}
        className={cn(
          "inline-flex items-center whitespace-nowrap rounded-full border font-medium leading-none",
          SIZE_CLASSES[size],
          spec.classes,
          className,
        )}
        {...rest}
      >
        {hideIcon ? null : (
          <Icon
            aria-hidden="true"
            className={cn(ICON_SIZE[size], spin && "animate-spin")}
          />
        )}
        <span>{text}</span>
      </span>
    );
  },
);

export const STATUS_BADGE_VARIANTS = Object.keys(
  VARIANTS,
) as StatusBadgeVariant[];
