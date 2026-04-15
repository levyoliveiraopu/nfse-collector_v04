/**
 * Validacao e formatacao de CNPJ (DS-07).
 *
 * Porta do algoritmo oficial usado em `apps/api/api/companies/cnpj.py`:
 * pesos oficiais, soma ponderada, resto da divisao por 11 para calcular
 * os dois digitos verificadores. Rejeita sequencias com todos os digitos
 * iguais (ex.: `00000000000000`), que passam pelo calculo matematico mas
 * sao invalidas por convencao da Receita.
 *
 * Normalizacao e validacao sao separadas:
 * - `normalizeCnpj` remove qualquer caractere nao-digito.
 * - `isValidCnpj` faz a checagem de DV sobre um CNPJ ja normalizado.
 * - `formatCnpj` aplica a mascara `00.000.000/0000-00`.
 */

const ONLY_DIGITS = /\D+/g;

const WEIGHTS_DV1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] as const;
const WEIGHTS_DV2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] as const;

export function normalizeCnpj(raw: string | null | undefined): string {
  if (raw == null) return "";
  return raw.replace(ONLY_DIGITS, "");
}

function checkDigit(digits: string, weights: readonly number[]): string {
  let total = 0;
  for (let i = 0; i < weights.length; i += 1) {
    total += Number(digits[i]) * weights[i];
  }
  const rest = total % 11;
  return rest < 2 ? "0" : String(11 - rest);
}

export function isValidCnpj(cnpj: string): boolean {
  if (typeof cnpj !== "string") return false;
  if (cnpj.length !== 14) return false;
  if (!/^\d{14}$/.test(cnpj)) return false;
  if (cnpj === cnpj[0].repeat(14)) return false;
  const dv1 = checkDigit(cnpj.slice(0, 12), WEIGHTS_DV1);
  if (cnpj[12] !== dv1) return false;
  const dv2 = checkDigit(cnpj.slice(0, 13), WEIGHTS_DV2);
  return cnpj[13] === dv2;
}

/**
 * Aplica a mascara `00.000.000/0000-00` sobre ate 14 digitos. Aceita
 * entradas parciais (usado em `onChange` para dar feedback enquanto o
 * usuario digita) — nao valida comprimento nem DV.
 */
export function formatCnpj(raw: string): string {
  const digits = normalizeCnpj(raw).slice(0, 14);
  const parts: string[] = [];
  if (digits.length <= 2) return digits;
  parts.push(digits.slice(0, 2));
  if (digits.length <= 5) {
    parts.push(digits.slice(2));
    return parts.join(".");
  }
  parts.push(digits.slice(2, 5));
  if (digits.length <= 8) {
    parts.push(digits.slice(5));
    return `${parts[0]}.${parts[1]}.${parts[2]}`;
  }
  parts.push(digits.slice(5, 8));
  if (digits.length <= 12) {
    parts.push(digits.slice(8));
    return `${parts[0]}.${parts[1]}.${parts[2]}/${parts[3]}`;
  }
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12, 14)}`;
}
