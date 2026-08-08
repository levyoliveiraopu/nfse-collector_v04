import {
  AlertCircle,
  LayoutDashboard,
  FileText,
  FolderArchive,
  ShieldCheck,
  Building2,
  CalendarClock,
  CreditCard,
  PlayCircle,
  Users,
  Settings,
  CircleHelp,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

// Rotas existentes vao sendo ligadas a medida que os tickets APP-*
// destravam:
// - APP-03: `/empresas`
// - APP-05: `/execucoes`
// - APP-06: `/ocorrencias`
// - APP-07: `/agendamentos`
// - APP-08: `/arquivos`
// - APP-09: `/usuarios`
// - APP-10: `/dashboard/assinatura`
// As demais permanecem como placeholders ate o ticket correspondente.
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Empresas", href: "/empresas", icon: Building2 },
  { label: "Execucoes", href: "/execucoes", icon: PlayCircle },
  { label: "Agendamentos", href: "/agendamentos", icon: CalendarClock },
  { label: "Ocorrencias", href: "/ocorrencias", icon: AlertCircle },
  { label: "Arquivos", href: "/arquivos", icon: FolderArchive },
  { label: "Ajuda", href: "/ajuda", icon: CircleHelp },
  { label: "Notas", href: "/dashboard/notas", icon: FileText },
  { label: "Certificados", href: "/dashboard/certificados", icon: ShieldCheck },
  { label: "Tenants", href: "/dashboard/tenants", icon: Building2 },
  { label: "Assinatura", href: "/dashboard/assinatura", icon: CreditCard },
  { label: "Usuarios", href: "/usuarios", icon: Users },
  { label: "Configuracoes", href: "/dashboard/configuracoes", icon: Settings },
];
