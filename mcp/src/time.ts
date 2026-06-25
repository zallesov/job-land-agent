export function toJoblandDate(date: Date): string {
  return date.toISOString().replace('T', ' ').slice(0, 19);
}
