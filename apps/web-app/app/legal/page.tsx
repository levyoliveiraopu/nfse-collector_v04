import Link from "next/link";

const updatedAt = "12 de junho de 2026";

export const metadata = {
  title: "Termos e Privacidade — NFS-e SaaS",
  description: "Termos de Uso e Politica de Privacidade da plataforma NFS-e SaaS.",
};

export default function LegalPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-10 text-foreground">
      <header className="space-y-3">
        <Link href="/signup" className="text-sm font-medium text-primary hover:underline">
          Voltar para criar conta
        </Link>
        <p className="text-sm text-muted-foreground">Atualizado em {updatedAt}</p>
        <h1 className="text-3xl font-semibold tracking-tight">Termos de Uso e Politica de Privacidade</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Esta pagina consolida o contrato operacional minimo para uso da plataforma. A versao juridica final deve ser
          revisada pelo responsavel legal antes do go-live, mas os pontos abaixo ja documentam escopo, dados tratados,
          responsabilidades e retencao.
        </p>
      </header>

      <nav aria-label="Indice" className="rounded-lg border border-border bg-card p-4 text-sm">
        <ul className="grid gap-2 sm:grid-cols-2">
          <li><a className="text-primary hover:underline" href="#terms">Termos de Uso</a></li>
          <li><a className="text-primary hover:underline" href="#privacy">Politica de Privacidade</a></li>
          <li><a className="text-primary hover:underline" href="#retention">Retencao de dados</a></li>
          <li><a className="text-primary hover:underline" href="#security">Seguranca e suporte</a></li>
        </ul>
      </nav>

      <section id="terms" className="space-y-4 scroll-mt-6">
        <h2 className="text-2xl font-semibold">Termos de Uso</h2>
        <div className="space-y-3 text-sm leading-6 text-muted-foreground">
          <p>
            A plataforma automatiza coleta, organizacao e exportacao de documentos fiscais NFS-e para empresas
            autorizadas pelo usuario. O usuario declara possuir poderes para cadastrar empresas, usuarios e certificados
            digitais vinculados ao tenant.
          </p>
          <p>
            E responsabilidade do usuario manter CNPJ, certificado A1, senha do PFX, membros e permissoes atualizados.
            O uso indevido de certificado de terceiro, acesso nao autorizado a dados fiscais ou compartilhamento de
            credenciais fora do fluxo seguro pode levar a suspensao do tenant.
          </p>
          <p>
            O servico pode aplicar limites de plano para quantidade de empresas, usuarios, execucoes, armazenamento e
            exportacoes. Os limites vigentes devem aparecer na tela de assinatura antes da cobranca em producao.
          </p>
        </div>
      </section>

      <section id="privacy" className="space-y-4 scroll-mt-6">
        <h2 className="text-2xl font-semibold">Politica de Privacidade</h2>
        <div className="space-y-3 text-sm leading-6 text-muted-foreground">
          <p>
            Tratamos dados de cadastro, identificadores de tenant, usuarios, papeis, empresas, CNPJ, metadados de
            documentos fiscais, XMLs de NFS-e, logs operacionais e credenciais criptografadas necessarias para executar o
            servico contratado.
          </p>
          <p>
            Certificados A1 e senhas sao tratados como segredos operacionais: o PFX e armazenado cifrado no storage, a
            senha e protegida por envelope encryption e nenhum deles deve aparecer em logs, tickets ou canais de suporte.
          </p>
          <p>
            A base legal principal e execucao de contrato/prestacao de servico. Quando aplicavel, dados fiscais podem
            estar sujeitos a obrigacoes legais e regulatórias do cliente/controlador.
          </p>
        </div>
      </section>

      <section id="retention" className="space-y-4 scroll-mt-6">
        <h2 className="text-2xl font-semibold">Retencao de dados</h2>
        <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
          <li>XMLs de execucoes seguem a regra de lifecycle do bucket configurada para o prefixo operacional.</li>
          <li>Exports ZIP sao temporarios e possuem expiracao operacional de 30 dias.</li>
          <li>Logs tecnicos devem ser retidos pelo menor periodo util para suporte e seguranca, sem segredos.</li>
          <li>Backups do Postgres seguem a politica operacional documentada em `infra/backup.md`.</li>
        </ul>
      </section>

      <section id="security" className="space-y-4 scroll-mt-6">
        <h2 className="text-2xl font-semibold">Seguranca e suporte</h2>
        <p className="text-sm leading-6 text-muted-foreground">
          Incidentes, solicitacoes de revogacao de sessao, suspeita de acesso indevido, credencial invalida ou exclusao
          de dados devem ser tratados pelos runbooks operacionais versionados em `docs/runbooks/`. Nunca envie PFX,
          senha, refresh token ou presigned URL por email, chat ou ticket.
        </p>
      </section>
    </main>
  );
}
