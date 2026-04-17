/**
 * Re-exports de tipos do OpenAPI gerado (DS-09).
 *
 * Expoe atalhos para os componentes `schemas` do OpenAPI e uma ajuda
 * generica para tipar payload/query/response de um operationId:
 *
 *   type Me = components["schemas"]["MeOut"];
 *   type CompaniesQuery = Operations["list_companies_companies_get"]["parameters"]["query"];
 */
import type { components, operations, paths } from "./generated/schema";

export type { components, operations, paths };
export type Components = components;
export type Operations = operations;
export type Paths = paths;
export type Schemas = components["schemas"];
