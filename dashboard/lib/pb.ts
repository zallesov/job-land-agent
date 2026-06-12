import PocketBase from 'pocketbase';

export const PB_URL =
  process.env.NEXT_PUBLIC_POCKETBASE_URL ?? 'http://72.61.183.105:8090';

// Server-side singleton — survives Next.js hot reloads
const g = global as typeof global & { _pb?: PocketBase };

export function getServerPb(): PocketBase {
  if (!g._pb) g._pb = new PocketBase(PB_URL);
  return g._pb;
}
