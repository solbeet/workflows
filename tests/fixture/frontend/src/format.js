/**
 * Utilidades del fixture frontend. Existen solo para que lint, typecheck,
 * test y build tengan código real cuando el selftest llama a python-react.yml.
 */

/**
 * Formatea un monto en centavos como texto con dos decimales.
 *
 * @param {number} cents Monto entero en centavos.
 * @returns {string} Monto con dos decimales, por ejemplo "12.50".
 * @throws {TypeError} Si `cents` no es un entero.
 */
export function formatCents(cents) {
  if (!Number.isInteger(cents)) {
    throw new TypeError("cents debe ser un entero");
  }
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}
