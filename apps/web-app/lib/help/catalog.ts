export type HelpRole = "owner" | "admin" | "operator" | "viewer";

export type HelpRouteKey =
  | "dashboard"
  | "companies"
  | "company_detail"
  | "credential"
  | "executions"
  | "execution_new"
  | "execution_detail"
  | "schedules"
  | "occurrences"
  | "occurrence_detail"
  | "files"
  | "users"
  | "subscription"
  | "help"
  | "access";

export type HelpCategory =
  | "Primeiros passos"
  | "Operação"
  | "Administração"
  | "Conta e acesso";

export type HelpTourStep = {
  id: string;
  target: string;
  title: string;
  content: string;
  placement?: "top" | "right" | "bottom" | "left" | "center" | "auto";
};

export type HelpEntry = {
  slug: string;
  title: string;
  summary: string;
  category: HelpCategory;
  keywords: string[];
  roles: HelpRole[];
  routeKey: HelpRouteKey;
  matches: (pathname: string) => boolean;
  related: string[];
  version: string;
  lastReviewed: string;
  tourId?: string;
  tourSteps?: HelpTourStep[];
  capabilitiesByRole: Record<HelpRole, string[]>;
};

export const HELP_VERSION = "1";
export const ALL_HELP_ROLES: HelpRole[] = [
  "owner",
  "admin",
  "operator",
  "viewer",
];

function exact(path: string) {
  return (pathname: string) => pathname === path;
}
function pattern(regex: RegExp) {
  return (pathname: string) => regex.test(pathname);
}

function standardTour(
  routeKey: Exclude<HelpRouteKey, "access">,
  pageTitle: string,
  taskDescription: string,
  primaryTarget?: string,
): Pick<HelpEntry, "tourId" | "tourSteps"> {
  return {
    tourId: `${routeKey}-tour`,
    tourSteps: [
      {
        id: "page",
        target: '[data-help-id="page-content"]',
        title: pageTitle,
        content: taskDescription,
        placement: "center",
      },
      {
        id: "primary",
        target: primaryTarget ?? '[data-help-id="page-content"]',
        title: "Ações da tela",
        content:
          "Use os filtros e ações disponíveis para seu perfil. O guia não clica nem salva nada por você.",
        placement: "bottom",
      },
      {
        id: "navigation",
        target: '[data-help-id="sidebar-navigation"]',
        title: "Continue navegando",
        content:
          "O menu leva às demais etapas da operação. A Ajuda se atualiza automaticamente quando você muda de seção.",
        placement: "right",
      },
      {
        id: "help",
        target: '[data-help-id="help-button"]',
        title: "Ajuda sempre disponível",
        content:
          "Abra este painel quando precisar rever regras, passos ou soluções para erros comuns.",
        placement: "bottom",
      },
    ],
  };
}

const readOnly = ["Consultar informações, filtros e status desta tela."];
const operate = [
  "Consultar informações, filtros e status desta tela.",
  "Executar as ações operacionais descritas no artigo.",
];

export const HELP_CATALOG: HelpEntry[] = [
  {
    slug: "dashboard",
    title: "Dashboard",
    summary: "Entenda os indicadores e identifique o que precisa de atenção.",
    category: "Primeiros passos",
    keywords: ["início", "indicadores", "resumo", "kpi", "alertas"],
    roles: ALL_HELP_ROLES,
    routeKey: "dashboard",
    matches: exact("/dashboard"),
    related: ["companies", "executions", "occurrences"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: operate,
      admin: operate,
      operator: operate,
      viewer: readOnly,
    },
    ...standardTour(
      "dashboard",
      "Visão geral da operação",
      "Os indicadores resumem empresas, coletas, ocorrências e arquivos recentes.",
      '[data-help-id="dashboard-primary"]',
    ),
  },
  {
    slug: "companies",
    title: "Empresas",
    summary: "Cadastre e acompanhe os CNPJs que serão consultados.",
    category: "Operação",
    keywords: ["empresa", "cnpj", "cadastro", "município", "ibge"],
    roles: ALL_HELP_ROLES,
    routeKey: "companies",
    matches: exact("/empresas"),
    related: ["company-detail", "credential", "execution-new"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: [...operate, "Cadastrar, editar e excluir empresas."],
      admin: [...operate, "Cadastrar, editar e excluir empresas."],
      operator: [...operate, "Cadastrar e editar empresas."],
      viewer: readOnly,
    },
    ...standardTour(
      "companies",
      "Empresas consultadas",
      "Localize um CNPJ, confira seu status ou abra o cadastro para ver credencial, coletas e arquivos.",
      '[data-help-id="companies-primary"]',
    ),
  },
  {
    slug: "company-detail",
    title: "Detalhe da empresa",
    summary: "Consulte cadastro, credencial e histórico operacional de um CNPJ.",
    category: "Operação",
    keywords: ["empresa", "abas", "histórico", "credencial", "arquivos"],
    roles: ALL_HELP_ROLES,
    routeKey: "company_detail",
    matches: pattern(/^\/empresas\/[^/]+$/),
    related: ["companies", "credential", "executions"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: operate,
      admin: operate,
      operator: operate,
      viewer: readOnly,
    },
    ...standardTour(
      "company_detail",
      "Histórico por empresa",
      "As abas reúnem os dados e resultados pertencentes apenas ao CNPJ aberto.",
      '[data-help-id="company-detail-primary"]',
    ),
  },
  {
    slug: "credential",
    title: "Credencial A1",
    summary: "Entenda validade, envio e substituição segura do certificado.",
    category: "Administração",
    keywords: ["certificado", "pfx", "p12", "senha", "validade", "a1"],
    roles: ALL_HELP_ROLES,
    routeKey: "credential",
    matches: pattern(/^(\/dashboard)?\/empresas\/[^/]+\/credencial$/),
    related: ["companies", "execution-new", "occurrences"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: [...readOnly, "Enviar, substituir e remover a credencial."],
      admin: [...readOnly, "Enviar, substituir e remover a credencial."],
      operator: readOnly,
      viewer: readOnly,
    },
    ...standardTour(
      "credential",
      "Certificado da empresa",
      "Confira a validade antes de coletar. O arquivo e a senha são enviados somente à API protegida.",
      '[data-help-id="credential-primary"]',
    ),
  },
  {
    slug: "executions",
    title: "Execuções",
    summary: "Acompanhe coletas manuais, automáticas e reprocessamentos.",
    category: "Operação",
    keywords: ["execução", "coleta", "fila", "parcial", "falha", "status"],
    roles: ALL_HELP_ROLES,
    routeKey: "executions",
    matches: exact("/execucoes"),
    related: ["execution-new", "execution-detail", "occurrences"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: operate,
      admin: operate,
      operator: operate,
      viewer: readOnly,
    },
    ...standardTour(
      "executions",
      "Histórico de coletas",
      "Filtre por status e abra uma execução para conferir itens, erros e totais.",
      '[data-help-id="executions-primary"]',
    ),
  },
  {
    slug: "execution-new",
    title: "Nova execução",
    summary: "Selecione empresas e período para iniciar uma coleta manual.",
    category: "Operação",
    keywords: ["nova coleta", "período", "incremental", "simulação", "dry run"],
    roles: ALL_HELP_ROLES,
    routeKey: "execution_new",
    matches: exact("/execucoes/nova"),
    related: ["credential", "executions", "schedules"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: [...operate, "Iniciar coletas manuais."],
      admin: [...operate, "Iniciar coletas manuais."],
      operator: [...operate, "Iniciar coletas manuais."],
      viewer: ["Consultar a orientação; o perfil viewer não inicia coletas."],
    },
    ...standardTour(
      "execution_new",
      "Preparar uma coleta",
      "Escolha apenas empresas com credencial válida, confirme o período e revise as opções antes de iniciar.",
      '[data-help-id="execution-new-primary"]',
    ),
  },
  {
    slug: "execution-detail",
    title: "Detalhe da execução",
    summary: "Interprete o resultado de uma coleta e seus itens processados.",
    category: "Operação",
    keywords: ["itens", "nsu", "resultado", "cancelar", "reprocessar"],
    roles: ALL_HELP_ROLES,
    routeKey: "execution_detail",
    matches: pattern(/^\/execucoes\/[^/]+$/),
    related: ["executions", "occurrences", "files"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: operate,
      admin: operate,
      operator: operate,
      viewer: readOnly,
    },
    ...standardTour(
      "execution_detail",
      "Resultado da coleta",
      "Confira o status geral, a quantidade processada e cada item antes de tratar falhas.",
      '[data-help-id="execution-detail-primary"]',
    ),
  },
  {
    slug: "schedules",
    title: "Agendamentos",
    summary: "Crie e controle coletas automáticas recorrentes.",
    category: "Operação",
    keywords: ["agendamento", "recorrência", "cron", "fuso", "pausar", "ativar"],
    roles: ALL_HELP_ROLES,
    routeKey: "schedules",
    matches: exact("/agendamentos"),
    related: ["execution-new", "executions", "credential"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: [...operate, "Criar, editar, ativar, pausar e excluir agendamentos."],
      admin: [...operate, "Criar, editar, ativar, pausar e excluir agendamentos."],
      operator: [...operate, "Criar, editar, ativar e pausar agendamentos."],
      viewer: readOnly,
    },
    ...standardTour(
      "schedules",
      "Coletas automáticas",
      "Cada agendamento combina empresa, frequência, fuso horário e próxima execução.",
      '[data-help-id="schedules-primary"]',
    ),
  },
  {
    slug: "occurrences",
    title: "Ocorrências",
    summary: "Priorize e acompanhe situações que exigem ação humana.",
    category: "Operação",
    keywords: ["ocorrência", "alerta", "erro", "severidade", "resolver", "atribuir"],
    roles: ALL_HELP_ROLES,
    routeKey: "occurrences",
    matches: exact("/ocorrencias"),
    related: ["occurrence-detail", "executions", "credential"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: operate,
      admin: operate,
      operator: operate,
      viewer: readOnly,
    },
    ...standardTour(
      "occurrences",
      "Caixa de entrada operacional",
      "Use status e severidade para priorizar o que precisa ser reconhecido, atribuído ou resolvido.",
      '[data-help-id="occurrences-primary"]',
    ),
  },
  {
    slug: "occurrence-detail",
    title: "Detalhe da ocorrência",
    summary: "Investigue, atribua e registre a solução de uma ocorrência.",
    category: "Operação",
    keywords: ["runbook", "reconhecer", "atribuir", "resolver", "nota"],
    roles: ALL_HELP_ROLES,
    routeKey: "occurrence_detail",
    matches: pattern(/^\/ocorrencias\/[^/]+$/),
    related: ["occurrences", "execution-detail", "credential"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: [...operate, "Reconhecer, atribuir, resolver e reprocessar."],
      admin: [...operate, "Reconhecer, atribuir, resolver e reprocessar."],
      operator: [...operate, "Reconhecer, atribuir, resolver e reprocessar."],
      viewer: readOnly,
    },
    ...standardTour(
      "occurrence_detail",
      "Tratamento auditável",
      "Leia o contexto e o runbook antes de reconhecer, atribuir ou registrar uma resolução.",
      '[data-help-id="occurrence-detail-primary"]',
    ),
  },
  {
    slug: "files",
    title: "Arquivos",
    summary: "Localize documentos e gere Excel ou ZIP de XML.",
    category: "Operação",
    keywords: ["arquivo", "xml", "zip", "excel", "download", "exportação"],
    roles: ALL_HELP_ROLES,
    routeKey: "files",
    matches: exact("/arquivos"),
    related: ["companies", "executions", "occurrences"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: [...operate, "Solicitar novos arquivos fiscais."],
      admin: [...operate, "Solicitar novos arquivos fiscais."],
      operator: [...operate, "Solicitar novos arquivos fiscais."],
      viewer: ["Consultar e baixar arquivos existentes; não solicitar novos exports."],
    },
    ...standardTour(
      "files",
      "Documentos e exports",
      "Filtre por empresa e período. Escolha Excel para análise ou ZIP para obter os XMLs.",
      '[data-help-id="files-primary"]',
    ),
  },
  {
    slug: "users",
    title: "Usuários e permissões",
    summary: "Consulte membros, convites e responsabilidades de cada perfil.",
    category: "Administração",
    keywords: ["usuário", "convite", "owner", "admin", "operator", "viewer"],
    roles: ALL_HELP_ROLES,
    routeKey: "users",
    matches: exact("/usuarios"),
    related: ["access-login", "subscription", "help-overview"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: [...readOnly, "Convidar e gerenciar todos os perfis, respeitando o último owner."],
      admin: [...readOnly, "Convidar e gerenciar operator/viewer; não alterar owners."],
      operator: readOnly,
      viewer: readOnly,
    },
    ...standardTour(
      "users",
      "Equipe e papéis",
      "Consulte quem tem acesso. Somente owner e admin veem ações de gestão permitidas pelo próprio papel.",
      '[data-help-id="users-primary"]',
    ),
  },
  {
    slug: "subscription",
    title: "Assinatura",
    summary: "Entenda o plano atual, limites e canais de atendimento.",
    category: "Administração",
    keywords: ["assinatura", "plano", "limite", "uso", "fatura"],
    roles: ALL_HELP_ROLES,
    routeKey: "subscription",
    matches: exact("/dashboard/assinatura"),
    related: ["companies", "users", "help-overview"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: [...readOnly, "Solicitar alteração de plano ao suporte."],
      admin: readOnly,
      operator: readOnly,
      viewer: readOnly,
    },
    ...standardTour(
      "subscription",
      "Plano e consumo",
      "Compare o uso atual com os limites antes de cadastrar empresas ou usuários.",
      '[data-help-id="subscription-primary"]',
    ),
  },
  {
    slug: "help-overview",
    title: "Central de Ajuda",
    summary: "Pesquise procedimentos, regras e solução de problemas.",
    category: "Primeiros passos",
    keywords: ["ajuda", "pesquisa", "guia", "tour", "suporte"],
    roles: ALL_HELP_ROLES,
    routeKey: "help",
    matches: exact("/ajuda"),
    related: ["dashboard", "executions", "occurrences"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: {
      owner: ["Pesquisar toda a ajuda e consultar indicadores de uso."],
      admin: ["Pesquisar toda a ajuda e consultar indicadores de uso."],
      operator: ["Pesquisar procedimentos operacionais permitidos ao perfil."],
      viewer: ["Pesquisar procedimentos de consulta permitidos ao perfil."],
    },
    ...standardTour(
      "help",
      "Encontre respostas",
      "Pesquise por tarefa, erro ou regra. A consulta acontece somente no navegador.",
      '[data-help-id="help-search"]',
    ),
  },
  {
    slug: "access-login",
    title: "Entrar no sistema",
    summary: "Acesse com o endereço e as credenciais fornecidas pelo administrador.",
    category: "Conta e acesso",
    keywords: ["login", "entrar", "senha", "tenant"],
    roles: ALL_HELP_ROLES,
    routeKey: "access",
    matches: exact("/login"),
    related: ["access-recovery", "access-signup"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: { owner: [], admin: [], operator: [], viewer: [] },
  },
  {
    slug: "access-signup",
    title: "Criar uma conta",
    summary: "Crie um tenant e o primeiro usuário owner.",
    category: "Conta e acesso",
    keywords: ["cadastro", "conta", "tenant", "owner"],
    roles: ALL_HELP_ROLES,
    routeKey: "access",
    matches: exact("/signup"),
    related: ["access-login"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: { owner: [], admin: [], operator: [], viewer: [] },
  },
  {
    slug: "access-recovery",
    title: "Recuperar acesso",
    summary: "Saiba o que fazer quando não consegue entrar.",
    category: "Conta e acesso",
    keywords: ["recuperar", "senha", "acesso", "email"],
    roles: ALL_HELP_ROLES,
    routeKey: "access",
    matches: exact("/recuperar-senha"),
    related: ["access-login", "access-reset"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: { owner: [], admin: [], operator: [], viewer: [] },
  },
  {
    slug: "access-reset",
    title: "Definir nova senha",
    summary: "Use um link válido de recuperação para trocar a senha.",
    category: "Conta e acesso",
    keywords: ["redefinir", "senha", "token", "expirado"],
    roles: ALL_HELP_ROLES,
    routeKey: "access",
    matches: pattern(/^\/redefinir-senha\/[^/]+$/),
    related: ["access-login", "access-recovery"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: { owner: [], admin: [], operator: [], viewer: [] },
  },
  {
    slug: "access-invitation",
    title: "Aceitar convite",
    summary: "Conclua o ingresso no tenant usando o convite recebido.",
    category: "Conta e acesso",
    keywords: ["convite", "aceitar", "tenant", "expirado"],
    roles: ALL_HELP_ROLES,
    routeKey: "access",
    matches: pattern(/^\/aceitar-convite\/[^/]+$/),
    related: ["access-login", "users"],
    version: HELP_VERSION,
    lastReviewed: "2026-08-08",
    capabilitiesByRole: { owner: [], admin: [], operator: [], viewer: [] },
  },
];

export const HELP_FALLBACK = HELP_CATALOG.find(
  (entry) => entry.slug === "help-overview",
)!;

export function normalizeHelpRole(role: string | null | undefined): HelpRole {
  return ALL_HELP_ROLES.includes(role as HelpRole)
    ? (role as HelpRole)
    : "viewer";
}

export function resolveHelpEntry(
  pathname: string,
  role: string | null | undefined,
): HelpEntry {
  const normalizedRole = normalizeHelpRole(role);
  return (
    HELP_CATALOG.find(
      (entry) =>
        entry.matches(pathname) && entry.roles.includes(normalizedRole),
    ) ?? HELP_FALLBACK
  );
}

export function getRelatedEntries(
  entry: HelpEntry,
  role: string | null | undefined,
): HelpEntry[] {
  const normalizedRole = normalizeHelpRole(role);
  return entry.related
    .map((slug) => HELP_CATALOG.find((candidate) => candidate.slug === slug))
    .filter(
      (candidate): candidate is HelpEntry =>
        Boolean(candidate?.roles.includes(normalizedRole)),
    );
}

export function normalizeSearchText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR")
    .trim();
}
