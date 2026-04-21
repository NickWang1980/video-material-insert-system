export function required(v) {
  return v != null && String(v).trim() !== "";
}
