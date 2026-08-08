/**
 * AUTO-GERADO por scripts/generate-api.mjs (DS-09).
 * NAO EDITAR MANUALMENTE — reexecute `pnpm --filter web-app generate-api`.
 */
/* eslint-disable */

export interface paths {
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ready */
        get: operations["ready_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/version": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Version */
        get: operations["version_version_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/signup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Signup */
        post: operations["signup_auth_signup_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Refresh */
        post: operations["refresh_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Me
         * @description Identidade corrente + prova de vida do middleware de tenant (API-03).
         *
         *     Responde 200 apenas quando:
         *     - o JWT foi validado (`get_current_claims`);
         *     - o tenant existe e nao esta suspenso/cancelado (`assert_tenant_active`);
         *     - a sessao RLS-gated foi aberta (`get_tenant_db`) — a contagem em
         *       `tenant_users` comprova que as politicas RLS enxergam somente o
         *       tenant corrente.
         */
        get: operations["me_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/companies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Companies */
        get: operations["list_companies_companies_get"];
        put?: never;
        /** Create Company */
        post: operations["create_company_companies_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/companies/{company_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Company */
        get: operations["get_company_companies__company_id__get"];
        put?: never;
        post?: never;
        /** Soft Delete Company */
        delete: operations["soft_delete_company_companies__company_id__delete"];
        options?: never;
        head?: never;
        /** Update Company */
        patch: operations["update_company_companies__company_id__patch"];
        trace?: never;
    };
    "/companies/{company_id}/executions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Atalho: lista execucoes da company (API-08) */
        get: operations["list_company_executions_companies__company_id__executions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/companies/{company_id}/credential": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Le a credencial ativa de uma company (metadados publicos)
         * @description Retorna a credencial `active` mais recente da company.
         *
         *     Nunca expoe ciphertext, senha ou bytes do PFX — apenas metadados
         *     publicos do certificado (fingerprint, validade, status, CN match).
         *     404 quando nao ha credencial ativa (company cross-tenant tambem cai
         *     aqui por RLS).
         */
        get: operations["get_credential_companies__company_id__credential_get"];
        put?: never;
        /** Upload de PFX A1 cifrado para uma company */
        post: operations["upload_credential_companies__company_id__credential_post"];
        /** Revoga a credencial ativa de uma company */
        delete: operations["revoke_credential_companies__company_id__credential_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/occurrences": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Occurrences */
        get: operations["list_occurrences_occurrences_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/occurrences/{occurrence_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Occurrence */
        get: operations["get_occurrence_occurrences__occurrence_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/occurrences/{occurrence_id}/acknowledge": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Marca a ocorrencia como reconhecida (open -> ack) */
        post: operations["acknowledge_occurrence_occurrences__occurrence_id__acknowledge_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/occurrences/{occurrence_id}/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Marca a ocorrencia como resolvida (nota obrigatoria) */
        post: operations["resolve_occurrence_occurrences__occurrence_id__resolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/occurrences/{occurrence_id}/assign": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Atribui a ocorrencia a um membro do tenant */
        post: operations["assign_occurrence_occurrences__occurrence_id__assign_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/schedules/presets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Presets */
        get: operations["list_presets_schedules_presets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/schedules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Schedules */
        get: operations["list_schedules_schedules_get"];
        put?: never;
        /** Create Schedule */
        post: operations["create_schedule_schedules_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/schedules/{schedule_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Schedule */
        get: operations["get_schedule_schedules__schedule_id__get"];
        put?: never;
        post?: never;
        /** Delete Schedule */
        delete: operations["delete_schedule_schedules__schedule_id__delete"];
        options?: never;
        head?: never;
        /** Update Schedule */
        patch: operations["update_schedule_schedules__schedule_id__patch"];
        trace?: never;
    };
    "/files": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lista arquivos do tenant (com filtros) */
        get: operations["list_files_files_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/files/{file_id}/url": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Gera URL pre-assinada (1h) para baixar o arquivo */
        get: operations["get_file_download_url_files__file_id__url_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/executions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lista execucoes do tenant (paginado, com filtros) */
        get: operations["list_executions_executions_get"];
        put?: never;
        /** Cria N execucoes (1 por company) e enfileira no Redis */
        post: operations["create_executions_executions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/executions/{execution_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Execution */
        get: operations["get_execution_executions__execution_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/executions/{execution_id}/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lista os items processados de uma execucao (paginado) */
        get: operations["list_execution_items_executions__execution_id__items_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/exports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cria pedido de export e enfileira job assincrono */
        post: operations["create_export_exports_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/exports/{export_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Status do export (inclui URL pre-assinada quando pronto) */
        get: operations["get_export_exports__export_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/onboarding/first-collection-done": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Registra na outbox a conclusao da 1a coleta do onboarding. */
        post: operations["record_first_collection_done_onboarding_first_collection_done_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reprocess": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cria um reprocess_job + executions filhas e enfileira no Redis */
        post: operations["create_reprocess_reprocess_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reprocess/{reprocess_job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Detalha um reprocess_job + progresso agregado das executions */
        get: operations["get_reprocess_reprocess__reprocess_job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/help/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Incrementa uma metrica diaria anonimizada da ajuda */
        post: operations["record_help_event_help_events_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/help/insights": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Indicadores agregados da ajuda para administradores */
        get: operations["get_help_insights_help_insights_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AuthOut
         * @description Par access + refresh devolvido em signup/login/refresh.
         */
        AuthOut: {
            /** Access Token */
            access_token: string;
            /** Refresh Token */
            refresh_token: string;
            /**
             * Token Type
             * @default bearer
             */
            token_type: string;
            /** Expires In */
            expires_in: number;
            /** Tenant Id */
            tenant_id: string;
            /** User Id */
            user_id: string;
            /** Role */
            role: string;
        };
        /** Body_upload_credential_companies__company_id__credential_post */
        Body_upload_credential_companies__company_id__credential_post: {
            /**
             * Pfx
             * @description Arquivo .pfx (PKCS#12) do certificado A1
             */
            pfx: string;
            /**
             * Password
             * @description Senha do PFX
             */
            password: string;
        };
        /**
         * CompanyIn
         * @description Payload de criacao (POST /companies).
         */
        CompanyIn: {
            /**
             * Cnpj
             * @description CNPJ do estabelecimento (com ou sem formatacao).
             */
            cnpj: string;
            /** Razao Social */
            razao_social: string;
            /** Nome Fantasia */
            nome_fantasia?: string | null;
            /**
             * Municipio Ibge
             * @description Codigo IBGE do municipio (string para preservar zeros a esquerda).
             */
            municipio_ibge: string;
            /** Uf */
            uf: string;
            /**
             * Status
             * @default active
             * @enum {string}
             */
            status: "active" | "paused" | "disabled";
            /** Portal Provider */
            portal_provider?: string | null;
            /** Notes */
            notes?: string | null;
        };
        /**
         * CompanyListOut
         * @description Envelope paginado de GET /companies.
         */
        CompanyListOut: {
            /** Items */
            items: components["schemas"]["CompanyOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /**
         * CompanyOut
         * @description Representacao retornada pelo CRUD.
         */
        CompanyOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /** Cnpj */
            cnpj: string;
            /** Razao Social */
            razao_social: string;
            /** Nome Fantasia */
            nome_fantasia?: string | null;
            /** Municipio Ibge */
            municipio_ibge: string;
            /** Uf */
            uf: string;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "paused" | "disabled";
            /** Last Nsu */
            last_nsu?: number | null;
            /** Last Success At */
            last_success_at?: string | null;
            /** Portal Provider */
            portal_provider?: string | null;
            /** Notes */
            notes?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * CompanyUpdate
         * @description Payload de edicao (PATCH /companies/{id}).
         *
         *     CNPJ e imutavel — para mudar, crie outra company. Todos os demais
         *     campos sao opcionais; somente os presentes no payload sao aplicados.
         *     `extra="forbid"` rejeita payloads com `cnpj` (ou qualquer campo
         *     desconhecido) para proteger contra typos silenciosos.
         */
        CompanyUpdate: {
            /** Razao Social */
            razao_social?: string | null;
            /** Nome Fantasia */
            nome_fantasia?: string | null;
            /** Municipio Ibge */
            municipio_ibge?: string | null;
            /** Uf */
            uf?: string | null;
            /** Status */
            status?: ("active" | "paused" | "disabled") | null;
            /** Portal Provider */
            portal_provider?: string | null;
            /** Notes */
            notes?: string | null;
        };
        /**
         * CreateExecutionsIn
         * @description Payload do POST /executions.
         *
         *     - `company_ids`: lista nao vazia, unica, de UUIDs. Cada UUID gera
         *       uma linha em `executions` + um job na fila.
         *     - `period_start` <= `period_end` (CHECK de dominio defende novamente
         *       no banco).
         *     - `dry_run`: nao persiste no schema; vai no `meta` do job RQ e e
         *       consumido pelo worker (API-13).
         *     - `trigger`: default `manual`.
         */
        CreateExecutionsIn: {
            /** Company Ids */
            company_ids: string[];
            /**
             * Period Start
             * Format: date
             */
            period_start: string;
            /**
             * Period End
             * Format: date
             */
            period_end: string;
            /**
             * Dry Run
             * @default false
             */
            dry_run: boolean;
            /**
             * Trigger
             * @default manual
             * @enum {string}
             */
            trigger: "manual" | "schedule" | "api" | "reprocess";
        };
        /**
         * CreateExecutionsOut
         * @description Envelope de POST /executions.
         */
        CreateExecutionsOut: {
            /** Created */
            created: components["schemas"]["CreatedExecution"][];
        };
        /**
         * CreateExportIn
         * @description Payload do POST /exports.
         *
         *     - `company_id`: UUID da company (escopo do export). RLS valida
         *       ownership pelo tenant.
         *     - `period_start` <= `period_end` (validado aqui e via CHECK no DB).
         *     - `kind`: ZIP dos XMLs ou planilha das NFS-e emitidas.
         */
        CreateExportIn: {
            /**
             * Company Id
             * Format: uuid
             */
            company_id: string;
            /**
             * Period Start
             * Format: date
             */
            period_start: string;
            /**
             * Period End
             * Format: date
             */
            period_end: string;
            /**
             * Kind
             * @default zip_xml
             * @enum {string}
             */
            kind: "zip_xml" | "excel_nfse";
        };
        /**
         * CreateExportOut
         * @description Resposta do POST /exports.
         */
        CreateExportOut: {
            /**
             * Export Id
             * Format: uuid
             */
            export_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "ready" | "failed" | "empty";
            /** Job Id */
            job_id?: string | null;
            /** Enqueue Error */
            enqueue_error?: string | null;
        };
        /**
         * CreatedExecution
         * @description Item da resposta de POST /executions — uma linha por company.
         */
        CreatedExecution: {
            /**
             * Execution Id
             * Format: uuid
             */
            execution_id: string;
            /**
             * Company Id
             * Format: uuid
             */
            company_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "succeeded" | "failed" | "cancelled" | "partial";
            /**
             * Job Id
             * @description Id do job no RQ. Null se o enqueue falhou (status=failed).
             */
            job_id?: string | null;
            /**
             * Enqueue Error
             * @description Mensagem curta quando o enqueue falhou apos o INSERT.
             */
            enqueue_error?: string | null;
        };
        /**
         * CredentialOut
         * @description Resposta retornada pelo POST/DELETE de credencial.
         *
         *     Nunca contem ciphertext nem fingerprint da chave privada — apenas
         *     metadados publicos do certificado X.509.
         */
        CredentialOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /**
             * Company Id
             * Format: uuid
             */
            company_id: string;
            /**
             * Type
             * @default pfx_a1
             * @constant
             */
            type: "pfx_a1";
            /** Pfx Object Key */
            pfx_object_key: string;
            /** Cert Fingerprint */
            cert_fingerprint?: string | null;
            /** Cert Not Before */
            cert_not_before?: string | null;
            /** Cert Not After */
            cert_not_after?: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "expired" | "revoked" | "invalid";
            /** Cn Matches Cnpj */
            cn_matches_cnpj?: boolean | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * ExecutionItemListOut
         * @description Envelope paginado do GET /executions/{id}/items.
         */
        ExecutionItemListOut: {
            /** Items */
            items: components["schemas"]["ExecutionItemOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /**
         * ExecutionItemOut
         * @description Linha de `execution_items` devolvida pelo GET /executions/{id}/items.
         */
        ExecutionItemOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /**
             * Execution Id
             * Format: uuid
             */
            execution_id: string;
            /** Nsu */
            nsu?: number | null;
            /** Chave Nfse */
            chave_nfse?: string | null;
            /** Cnpj Emitente */
            cnpj_emitente?: string | null;
            /** Data Emissao */
            data_emissao?: string | null;
            /** Valor */
            valor?: string | null;
            /** Xml Object Key */
            xml_object_key?: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "failed" | "skipped" | "pending";
            /** Error Code */
            error_code?: string | null;
            /** Error Message */
            error_message?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * ExecutionListOut
         * @description Envelope paginado do GET /executions e GET /companies/{id}/executions.
         */
        ExecutionListOut: {
            /** Items */
            items: components["schemas"]["ExecutionOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /**
         * ExecutionOut
         * @description Representacao retornada por GET /executions/{id}.
         */
        ExecutionOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /**
             * Company Id
             * Format: uuid
             */
            company_id: string;
            /**
             * Trigger
             * @enum {string}
             */
            trigger: "manual" | "schedule" | "api" | "reprocess";
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "succeeded" | "failed" | "cancelled" | "partial";
            /**
             * Period Start
             * Format: date
             */
            period_start: string;
            /**
             * Period End
             * Format: date
             */
            period_end: string;
            /** Started At */
            started_at?: string | null;
            /** Finished At */
            finished_at?: string | null;
            /** Nsu From */
            nsu_from?: number | null;
            /** Nsu To */
            nsu_to?: number | null;
            /** Items Total */
            items_total: number;
            /** Items Ok */
            items_ok: number;
            /** Items Fail */
            items_fail: number;
            /** Error Summary */
            error_summary?: string | null;
            /** Triggered By User Id */
            triggered_by_user_id?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * ExportOut
         * @description Representacao de um pedido de export.
         *
         *     `download_url` + `expires_in` vem preenchidos **somente** quando
         *     `status == 'ready'` e `file_id` esta populado. Em qualquer outro
         *     estado ficam como `None`.
         */
        ExportOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /**
             * Company Id
             * Format: uuid
             */
            company_id: string;
            /** Requested By User Id */
            requested_by_user_id?: string | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "zip_xml" | "excel_nfse";
            /**
             * Period Start
             * Format: date
             */
            period_start: string;
            /**
             * Period End
             * Format: date
             */
            period_end: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "ready" | "failed" | "empty";
            /** File Id */
            file_id?: string | null;
            /** Items Count */
            items_count: number;
            /** Total Bytes */
            total_bytes: number;
            /** Error Code */
            error_code?: string | null;
            /** Error Message */
            error_message?: string | null;
            /** Started At */
            started_at?: string | null;
            /** Finished At */
            finished_at?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Download Url */
            download_url?: string | null;
            /** Expires In */
            expires_in?: number | null;
        };
        /**
         * FileListOut
         * @description Envelope paginado.
         */
        FileListOut: {
            /** Items */
            items: components["schemas"]["FileOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /**
         * FileOut
         * @description Linha de `files` devolvida pelo GET /files.
         */
        FileOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "nfse_xml" | "export" | "pfx" | "report" | "other";
            /** Object Key */
            object_key: string;
            /** Bytes */
            bytes: number;
            /** Checksum Sha256 */
            checksum_sha256: string;
            /** Source Execution Id */
            source_execution_id?: string | null;
            /** Expires At */
            expires_at?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * FileUrlOut
         * @description Resposta do GET /files/{id}/url — URL pre-assinada.
         */
        FileUrlOut: {
            /** Url */
            url: string;
            /** Expires In */
            expires_in: number;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
        };
        /**
         * FirstCollectionDoneOut
         * @description Resposta de `POST /onboarding/first-collection-done`.
         *
         *     - `already_recorded=True` quando ja havia `notifications` com o
         *       mesmo (tenant_id, user_id, type) — o endpoint e idempotente.
         *     - `notification_id` e o id da linha recem criada (ou da existente
         *       quando `already_recorded`).
         */
        FirstCollectionDoneOut: {
            /** Already Recorded */
            already_recorded: boolean;
            /** Notification Id */
            notification_id?: string | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * HelpEventIn
         * @description Evento anonimo e normalizado; nunca recebe texto pesquisado ou URL.
         */
        HelpEventIn: {
            /**
             * Event Type
             * @enum {string}
             */
            event_type: "article_opened" | "search_performed" | "search_no_results" | "tour_started" | "tour_completed" | "tour_skipped" | "tour_failed" | "feedback_yes" | "feedback_no";
            /** Article Slug */
            article_slug?: string | null;
            /** Route Key */
            route_key?: ("dashboard" | "companies" | "company_detail" | "credential" | "executions" | "execution_new" | "execution_detail" | "schedules" | "occurrences" | "occurrence_detail" | "files" | "users" | "subscription" | "help") | null;
            /** Tour Id */
            tour_id?: string | null;
        };
        /** HelpInsightRow */
        HelpInsightRow: {
            /** Article Slug */
            article_slug: string;
            /** Route Key */
            route_key: string;
            /**
             * Article Opened
             * @default 0
             */
            article_opened: number;
            /**
             * Search Performed
             * @default 0
             */
            search_performed: number;
            /**
             * Search No Results
             * @default 0
             */
            search_no_results: number;
            /**
             * Tour Started
             * @default 0
             */
            tour_started: number;
            /**
             * Tour Completed
             * @default 0
             */
            tour_completed: number;
            /**
             * Tour Skipped
             * @default 0
             */
            tour_skipped: number;
            /**
             * Tour Failed
             * @default 0
             */
            tour_failed: number;
            /**
             * Feedback Yes
             * @default 0
             */
            feedback_yes: number;
            /**
             * Feedback No
             * @default 0
             */
            feedback_no: number;
        };
        /** HelpInsightsOut */
        HelpInsightsOut: {
            /**
             * Days
             * @enum {integer}
             */
            days: 7 | 30 | 90;
            /**
             * Date From
             * Format: date
             */
            date_from: string;
            /**
             * Date To
             * Format: date
             */
            date_to: string;
            totals: components["schemas"]["HelpInsightsTotals"];
            /** Rows */
            rows: components["schemas"]["HelpInsightRow"][];
        };
        /** HelpInsightsTotals */
        HelpInsightsTotals: {
            /**
             * Article Opened
             * @default 0
             */
            article_opened: number;
            /**
             * Search Performed
             * @default 0
             */
            search_performed: number;
            /**
             * Search No Results
             * @default 0
             */
            search_no_results: number;
            /**
             * Tour Started
             * @default 0
             */
            tour_started: number;
            /**
             * Tour Completed
             * @default 0
             */
            tour_completed: number;
            /**
             * Tour Skipped
             * @default 0
             */
            tour_skipped: number;
            /**
             * Tour Failed
             * @default 0
             */
            tour_failed: number;
            /**
             * Feedback Yes
             * @default 0
             */
            feedback_yes: number;
            /**
             * Feedback No
             * @default 0
             */
            feedback_no: number;
        };
        /** LoginIn */
        LoginIn: {
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Password */
            password: string;
            /**
             * Tenant Slug
             * @description Slug do tenant. Obrigatorio quando o usuario tem mais de uma membership ativa.
             */
            tenant_slug?: string | null;
        };
        /** LogoutIn */
        LogoutIn: {
            /** Refresh Token */
            refresh_token: string;
        };
        /** LogoutOut */
        LogoutOut: {
            /** Revoked */
            revoked: boolean;
        };
        /**
         * MeOut
         * @description Identidade corrente derivada do JWT (API-03).
         *
         *     Serve como prova de vida do middleware de tenant: se o handler
         *     responde, o `SET LOCAL app.current_tenant` foi aplicado e o RLS
         *     esta ativo nesta request.
         */
        MeOut: {
            /** Tenant Id */
            tenant_id: string;
            /** User Id */
            user_id: string;
            /** Role */
            role: string;
            /** Memberships Visible */
            memberships_visible: number;
        };
        /**
         * OccurrenceAssignIn
         * @description Body de POST /occurrences/{id}/assign.
         */
        OccurrenceAssignIn: {
            /**
             * Assignee User Id
             * Format: uuid
             */
            assignee_user_id: string;
        };
        /**
         * OccurrenceListOut
         * @description Envelope paginado de GET /occurrences.
         */
        OccurrenceListOut: {
            /** Items */
            items: components["schemas"]["OccurrenceOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /**
         * OccurrenceOut
         * @description Representacao retornada pelos endpoints de leitura.
         */
        OccurrenceOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /**
             * Company Id
             * Format: uuid
             */
            company_id: string;
            /** Execution Id */
            execution_id?: string | null;
            /**
             * Severity
             * @enum {string}
             */
            severity: "info" | "warning" | "error" | "critical";
            /** Code */
            code: string;
            /** Title */
            title: string;
            /** Detail */
            detail?: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "open" | "ack" | "snoozed" | "resolved" | "ignored";
            /** Assignee User Id */
            assignee_user_id?: string | null;
            /**
             * First Seen At
             * Format: date-time
             */
            first_seen_at: string;
            /**
             * Last Seen At
             * Format: date-time
             */
            last_seen_at: string;
            /** Resolved At */
            resolved_at?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * OccurrenceResolveIn
         * @description Body de POST /occurrences/{id}/resolve.
         *
         *     A nota e obrigatoria pelo ticket — registrada em
         *     `audit_logs.metadata.note` (a tabela `occurrences` nao tem coluna
         *     dedicada nesta entrega; auditoria preserva o historico).
         */
        OccurrenceResolveIn: {
            /** Note */
            note: string;
        };
        /** RefreshIn */
        RefreshIn: {
            /** Refresh Token */
            refresh_token: string;
        };
        /**
         * ReprocessChildExecution
         * @description Item da resposta de POST /reprocess — 1 linha por execution filha.
         */
        ReprocessChildExecution: {
            /**
             * Execution Id
             * Format: uuid
             */
            execution_id: string;
            /**
             * Company Id
             * Format: uuid
             */
            company_id: string;
            /**
             * Period Start
             * Format: date
             */
            period_start: string;
            /**
             * Period End
             * Format: date
             */
            period_end: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "failed";
            /** Job Id */
            job_id?: string | null;
            /** Enqueue Error */
            enqueue_error?: string | null;
        };
        /**
         * ReprocessIn
         * @description Payload de `POST /reprocess` — exatamente 1 dos 3 escopos.
         */
        ReprocessIn: {
            /** Execution Item Ids */
            execution_item_ids?: string[] | null;
            /** Company Id */
            company_id?: string | null;
            /** Nsus */
            nsus?: number[] | null;
            period?: components["schemas"]["ReprocessPeriod"] | null;
            /** Statuses */
            statuses?: ("ok" | "failed" | "skipped" | "pending")[] | null;
            /**
             * Dry Run
             * @default false
             */
            dry_run: boolean;
        };
        /**
         * ReprocessOut
         * @description Representacao retornada por POST e GET /reprocess/{id}.
         */
        ReprocessOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
            /** Scope */
            scope: {
                [key: string]: unknown;
            };
            /** Result Execution Ids */
            result_execution_ids: string[];
            /** Error Summary */
            error_summary?: string | null;
            /** Created By User Id */
            created_by_user_id?: string | null;
            /** Started At */
            started_at?: string | null;
            /** Finished At */
            finished_at?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Created Executions */
            created_executions?: components["schemas"]["ReprocessChildExecution"][] | null;
            progress?: components["schemas"]["ReprocessProgress"] | null;
        };
        /**
         * ReprocessPeriod
         * @description Janela de competencia (alias das datas de `executions`).
         */
        ReprocessPeriod: {
            /**
             * Start
             * Format: date
             */
            start: string;
            /**
             * End
             * Format: date
             */
            end: string;
        };
        /**
         * ReprocessProgress
         * @description Contagens agregadas das executions filhas (derivadas em GET).
         */
        ReprocessProgress: {
            /** Total */
            total: number;
            /** Queued */
            queued: number;
            /** Running */
            running: number;
            /** Succeeded */
            succeeded: number;
            /** Failed */
            failed: number;
            /** Cancelled */
            cancelled: number;
            /** Partial */
            partial: number;
            /**
             * Effective Status
             * @enum {string}
             */
            effective_status: "queued" | "running" | "succeeded" | "partial" | "failed" | "cancelled";
        };
        /**
         * ScheduleIn
         * @description Payload de criacao (POST /schedules).
         */
        ScheduleIn: {
            /**
             * Cron Expr
             * @description Expressao cron 5 campos (ex.: '0 3 * * *').
             */
            cron_expr: string;
            /**
             * Timezone
             * @description Nome IANA (ex.: 'America/Sao_Paulo').
             * @default America/Sao_Paulo
             */
            timezone: string;
            /**
             * Company Id
             * @description Company alvo. Null = agenda valida para o tenant inteiro.
             */
            company_id?: string | null;
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
        };
        /**
         * ScheduleListOut
         * @description Envelope paginado de GET /schedules.
         */
        ScheduleListOut: {
            /** Items */
            items: components["schemas"]["ScheduleOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /**
         * ScheduleOut
         * @description Representacao retornada pelo CRUD.
         */
        ScheduleOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /** Company Id */
            company_id?: string | null;
            /** Cron Expr */
            cron_expr: string;
            /** Timezone */
            timezone: string;
            /** Enabled */
            enabled: boolean;
            /** Last Run At */
            last_run_at?: string | null;
            /** Next Run At */
            next_run_at?: string | null;
            /** Created By User Id */
            created_by_user_id?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** SchedulePresetListOut */
        SchedulePresetListOut: {
            /** Items */
            items: components["schemas"]["SchedulePresetOut"][];
        };
        /**
         * SchedulePresetOut
         * @description Sugestao de cron pronta para a UI (GET /schedules/presets).
         */
        SchedulePresetOut: {
            /** Id */
            id: string;
            /** Label */
            label: string;
            /** Cron Expr */
            cron_expr: string;
            /** Description */
            description: string;
        };
        /**
         * ScheduleUpdate
         * @description Payload de edicao (PATCH /schedules/{id}).
         *
         *     `extra="forbid"` impede o cliente de tocar campos read-only como
         *     `last_run_at`, `next_run_at`, `tenant_id`, `created_by_user_id`.
         *     Para pausar/resumir use `enabled`.
         */
        ScheduleUpdate: {
            /** Cron Expr */
            cron_expr?: string | null;
            /** Timezone */
            timezone?: string | null;
            /** Company Id */
            company_id?: string | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /**
         * SignupIn
         * @description Cria um tenant novo e um usuario owner em uma unica chamada.
         */
        SignupIn: {
            /** Tenant Name */
            tenant_name: string;
            /**
             * Tenant Slug
             * @description Slug unico do tenant (ex: 'acme-contabil').
             */
            tenant_slug: string;
            /** Name */
            name: string;
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Password */
            password: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    ready_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    version_version_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    signup_auth_signup_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignupIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refresh_auth_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RefreshIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LogoutIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LogoutOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    me_auth_me_get: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_companies_companies_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                status?: ("active" | "paused" | "disabled") | null;
                uf?: string | null;
            };
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CompanyListOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_company_companies_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CompanyIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CompanyOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_company_companies__company_id__get: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                company_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CompanyOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    soft_delete_company_companies__company_id__delete: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                company_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_company_companies__company_id__patch: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                company_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CompanyUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CompanyOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_company_executions_companies__company_id__executions_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                status?: ("queued" | "running" | "succeeded" | "failed" | "cancelled" | "partial") | null;
                /** @description Inicio do periodo (started_at >=). ISO 8601 UTC. */
                from?: string | null;
                /** @description Fim do periodo (started_at <). ISO 8601 UTC. */
                to?: string | null;
            };
            header?: {
                Authorization?: string | null;
            };
            path: {
                company_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExecutionListOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_credential_companies__company_id__credential_get: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                company_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CredentialOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_credential_companies__company_id__credential_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                company_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_credential_companies__company_id__credential_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CredentialOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_credential_companies__company_id__credential_delete: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                company_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_occurrences_occurrences_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                status?: ("open" | "ack" | "snoozed" | "resolved" | "ignored") | null;
                severity?: ("info" | "warning" | "error" | "critical") | null;
                company_id?: string | null;
            };
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OccurrenceListOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_occurrence_occurrences__occurrence_id__get: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                occurrence_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OccurrenceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    acknowledge_occurrence_occurrences__occurrence_id__acknowledge_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                occurrence_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OccurrenceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_occurrence_occurrences__occurrence_id__resolve_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                occurrence_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OccurrenceResolveIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OccurrenceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    assign_occurrence_occurrences__occurrence_id__assign_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                occurrence_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OccurrenceAssignIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OccurrenceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_presets_schedules_presets_get: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SchedulePresetListOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_schedules_schedules_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                enabled?: boolean | null;
                company_id?: string | null;
            };
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleListOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_schedule_schedules_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScheduleIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_schedule_schedules__schedule_id__get: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_schedule_schedules__schedule_id__delete: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_schedule_schedules__schedule_id__patch: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScheduleUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_files_files_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                kind?: ("nfse_xml" | "export" | "pfx" | "report" | "other") | null;
                /** @description Filtra por company via JOIN em executions. */
                company?: string | null;
                /** @description Inicio do periodo (created_at >=). ISO 8601 UTC. */
                from?: string | null;
                /** @description Fim do periodo (created_at <). ISO 8601 UTC. */
                to?: string | null;
            };
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FileListOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_file_download_url_files__file_id__url_get: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                file_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FileUrlOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_executions_executions_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                company_id?: string | null;
                status?: ("queued" | "running" | "succeeded" | "failed" | "cancelled" | "partial") | null;
                /** @description Inicio do periodo (started_at >=). ISO 8601 UTC. */
                from?: string | null;
                /** @description Fim do periodo (started_at <). ISO 8601 UTC. */
                to?: string | null;
            };
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExecutionListOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_executions_executions_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateExecutionsIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CreateExecutionsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_execution_executions__execution_id__get: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                execution_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExecutionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_execution_items_executions__execution_id__items_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                status?: ("ok" | "failed" | "skipped" | "pending") | null;
                nsu?: number | null;
                /** @description issued filtra pelo CNPJ emitente da empresa; all e diagnostico. */
                scope?: "issued" | "all";
            };
            header?: {
                Authorization?: string | null;
            };
            path: {
                execution_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExecutionItemListOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_export_exports_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateExportIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CreateExportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_export_exports__export_id__get: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                export_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    record_first_collection_done_onboarding_first_collection_done_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FirstCollectionDoneOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_reprocess_reprocess_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReprocessIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReprocessOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_reprocess_reprocess__reprocess_job_id__get: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path: {
                reprocess_job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReprocessOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    record_help_event_help_events_post: {
        parameters: {
            query?: never;
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HelpEventIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_help_insights_help_insights_get: {
        parameters: {
            query?: {
                days?: number;
            };
            header?: {
                Authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HelpInsightsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
