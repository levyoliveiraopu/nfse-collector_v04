"use client";

import { ROLES, type Role } from "@/lib/users/types";
import { rolesAssignableBy } from "@/lib/users/schemas";
import { cn } from "@/lib/utils";

const LABELS: Record<Role, string> = {
  owner: "Owner (acesso total)",
  admin: "Admin",
  operator: "Operador",
  viewer: "Leitor",
};

type RoleSelectProps = {
  id?: string;
  value: Role;
  onChange: (role: Role) => void;
  /** Papel do ator — limita as opcoes oferecidas. Default: aceita todas. */
  actor?: Role;
  /** Desabilita o controle (ex.: target=owner sem ator owner). */
  disabled?: boolean;
  "aria-describedby"?: string;
  "aria-label"?: string;
  className?: string;
};

/**
 * Select de papel respeitando o RBAC: um `admin` nao ve `owner`/`admin`
 * nas opcoes (o backend tambem bloqueia, mas o UI dimensiona as
 * possibilidades).
 */
export function RoleSelect({
  id,
  value,
  onChange,
  actor,
  disabled,
  className,
  ...rest
}: RoleSelectProps) {
  const options: Role[] = actor ? rolesAssignableBy(actor) : [...ROLES];
  // Garante que o valor atual aparece mesmo se estiver fora do assignable
  // set (ex.: admin visualizando um owner): mantemos o value para UI nao
  // ficar quebrada, mas o select permanece `disabled`.
  const expanded = options.includes(value) ? options : [value, ...options];

  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value as Role)}
      disabled={disabled}
      className={cn(
        "h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...rest}
    >
      {expanded.map((role) => (
        <option key={role} value={role}>
          {LABELS[role]}
        </option>
      ))}
    </select>
  );
}
