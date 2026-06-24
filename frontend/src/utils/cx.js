/** Joins truthy class name strings together. */
export function cx(...classes) {
  return classes.filter(Boolean).join(" ");
}
