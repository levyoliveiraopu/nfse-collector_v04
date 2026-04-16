import { cn } from "@/lib/utils";
import type { Role } from "@/lib/users/types";

const ROLE_LABELS: Record<Role, string> = {
  owner: "Owner",
  admin: "Admin",
  operator: "Operador",
  viewer: "Leitor",
};

const ROLE_CLASSES: Record<Role, string> = {
  owner:
    "bg-primary/15 text-primary border-primary/30",
  admin: "bg-accent text-accent-foreground border-border",
  operator:
    "bg-success/10 text-success border-success/30",
  viewer: "bg-muted text-muted-foreground border-border",
};

export function roleLabel(role: Role): string {
  return ROLE_LABELS[role];
}

export function RoleBadge({
  role,
  className,
}: {
  role: Role;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        ROLE_CLASSES[role],
        className,
      )}
    >
      {ROLE_LABELS[role]}
    </span>
  );
}
