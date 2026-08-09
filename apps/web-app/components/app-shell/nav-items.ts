import {
  AlertCircle,
  LayoutDashboard,
  FolderArchive,
  Building2,
  CalendarClock,
  CreditCard,
  PlayCircle,
  Users,
  CircleHelp,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

// Exiba somente rotas funcionais. Enderecos legados podem redirecionar para
// uma area equivalente, mas nao devem aparecer como uma pagina independente.
// Tickets implementados:
// - APP-03: `/empresas`
// - APP-05: `/execucoes`
// - APP-06: `/ocorrencias`
// - APP-07: `/agendamentos`
// - APP-08: `/arquivos`
// - APP-09: `/usuarios`
// - APP-10: `/dashboard/assinatura`
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Empresas", href: "/empresas", icon: Building2 },
  { label: "Execucoes", href: "/execucoes", icon: PlayCircle },
  { label: "Agendamentos", href: "/agendamentos", icon: CalendarClock },
  { label: "Ocorrencias", href: "/ocorrencias", icon: AlertCircle },
  { label: "Arquivos", href: "/arquivos", icon: FolderArchive },
  { label: "Ajuda", href: "/ajuda", icon: CircleHelp },
  { label: "Assinatura", href: "/dashboard/assinatura", icon: CreditCard },
  { label: "Usuarios", href: "/usuarios", icon: Users },
];
