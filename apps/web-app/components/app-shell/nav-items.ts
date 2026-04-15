import {
  LayoutDashboard,
  FileText,
  ShieldCheck,
  Building2,
  CreditCard,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

// Placeholders — rotas reais sao definidas em tickets posteriores (APP-*).
// Mantemos aqui apenas para estruturar o shell (DS-03).
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Notas", href: "/dashboard/notas", icon: FileText },
  { label: "Certificados", href: "/dashboard/certificados", icon: ShieldCheck },
  { label: "Tenants", href: "/dashboard/tenants", icon: Building2 },
  { label: "Assinatura", href: "/dashboard/assinatura", icon: CreditCard },
  { label: "Configuracoes", href: "/dashboard/configuracoes", icon: Settings },
];
