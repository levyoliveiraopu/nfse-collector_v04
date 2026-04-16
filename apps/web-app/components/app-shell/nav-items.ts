import {
  LayoutDashboard,
  FileText,
  ShieldCheck,
  Building2,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

// Rotas existentes vao sendo ligadas a medida que os tickets APP-*
// destravam: APP-03 entrega `/empresas`. As demais permanecem como
// placeholders ate o ticket correspondente.
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Empresas", href: "/empresas", icon: Building2 },
  { label: "Notas", href: "/dashboard/notas", icon: FileText },
  { label: "Certificados", href: "/dashboard/certificados", icon: ShieldCheck },
  { label: "Configuracoes", href: "/dashboard/configuracoes", icon: Settings },
];
