import { redirect } from "next/navigation";

/**
 * Compatibilidade com favoritos antigos. A operacao de notas emitidas fica
 * em Arquivos, onde o usuario filtra o periodo e gera Excel ou ZIP de XML.
 */
export default function LegacyNotasPage() {
  redirect("/arquivos");
}
