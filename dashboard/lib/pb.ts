// Client-safe PocketBase constants. No server-only imports here — this module
// is imported by client components too (for the browser realtime client).
export const PB_URL =
  process.env.NEXT_PUBLIC_POCKETBASE_URL ?? 'http://localhost:8090';

export const PB_AUTH_COOKIE = 'pb_auth';
