import {
  AlertCircle,
  LayoutDashboard,
  FileText,
  ShieldCheck,
  Building2,
  CreditCard,
  Users,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

// Rotas existentes vao sendo ligadas a medida que os tickets APP-*
// destravam: APP-03 entrega `/empresas`, APP-06 entrega `/ocorrencias`.
// As demais permanecem como placeholders ate o ticket correspondente.
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Empresas", href: "/empresas", icon: Building2 },
  { label: "Ocorrencias", href: "/ocorrencias", icon: AlertCircle },
  { label: "Notas", href: "/dashboard/notas", icon: FileText },
  { label: "Certificados", href: "/dashboard/certificados", icon: ShieldCheck },
  { label: "Tenants", href: "/dashboard/tenants", icon: Building2 },
  { label: "Assinatura", href: "/dashboard/assinatura", icon: CreditCard },
  { label: "Usuarios", href: "/usuarios", icon: Users },
  { label: "Configuracoes", href: "/dashboard/configuracoes", icon: Settings },
];
