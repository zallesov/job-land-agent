import PocketBase from 'pocketbase';

export const PB_URL =
  process.env.NEXT_PUBLIC_POCKETBASE_URL ?? 'http://localhost:8090';

const g = global as typeof global & { _pb?: PocketBase };

export function getServerPb(): PocketBase {
  if (!g._pb) {
    g._pb = new PocketBase(PB_URL);
    const email = process.env.POCKETBASE_ADMIN_EMAIL;
    const password = process.env.POCKETBASE_ADMIN_PASSWORD;
    if (email && password) {
      g._pb.collection('_superusers').authWithPassword(email, password).catch(() => {
        g._pb = undefined;
      });
    }
  }
  return g._pb;
}
