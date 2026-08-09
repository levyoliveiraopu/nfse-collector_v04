import { redirect } from "next/navigation";

/**
 * Compatibilidade com favoritos antigos. Certificados pertencem a uma empresa
 * e sao gerenciados a partir da listagem de Empresas.
 */
export default function LegacyCertificadosPage() {
  redirect("/empresas");
}
