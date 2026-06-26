import PocketBase from 'pocketbase';
import type { McpTokenRecord } from './auth.js';
import type { CollectionName, JoblandRecordGateway, ListOptions } from './toolHandlers.js';
import { toJoblandDate } from './time.js';

export type PocketBaseConfig = {
  url: string;
  adminEmail: string;
  adminPassword: string;
};

// Force a re-login if the cached superuser token is older than this, even if
// PocketBase hasn't started rejecting it yet. Belt-and-suspenders alongside the
// reactive 401/403 retry below.
const REAUTH_AFTER_MS = 24 * 60 * 60 * 1000;

function isAuthError(error: unknown): boolean {
  const status = (error as { status?: unknown } | null)?.status;
  return status === 401 || status === 403;
}

export class JoblandPocketBaseGateway implements JoblandRecordGateway {
  private readonly pb: PocketBase;
  private authPromise: Promise<void> | null = null;
  private authedAt = 0;

  constructor(private readonly config: PocketBaseConfig) {
    this.pb = new PocketBase(config.url);
    this.pb.autoCancellation(false);
  }

  private async ensureAuth(force = false): Promise<void> {
    const stale = Date.now() - this.authedAt > REAUTH_AFTER_MS;
    if (force || stale || !this.pb.authStore.isValid) {
      this.authPromise = null;
    }
    if (!this.authPromise) {
      this.authPromise = this.pb.collection('_superusers').authWithPassword(
        this.config.adminEmail,
        this.config.adminPassword,
      ).then(() => {
        this.authedAt = Date.now();
      }).catch((error) => {
        this.authPromise = null;
        throw error;
      });
    }
    await this.authPromise;
  }

  // Runs a PocketBase operation under a valid superuser session. If PocketBase
  // rejects with 401/403 (e.g. the cached admin token expired), force a fresh
  // login and retry the operation once.
  private async withAuth<T>(op: () => Promise<T>): Promise<T> {
    await this.ensureAuth();
    try {
      return await op();
    } catch (error) {
      if (!isAuthError(error)) throw error;
      await this.ensureAuth(true);
      return op();
    }
  }

  async list(collection: CollectionName, options: Required<ListOptions>): Promise<unknown[]> {
    return this.withAuth(() => this.pb.collection(collection).getList(options.page, options.perPage, {
      filter: options.filter,
      sort: options.sort,
    }).then((result) => result.items));
  }

  async get(collection: CollectionName, id: string): Promise<unknown> {
    return this.withAuth(() => this.pb.collection(collection).getOne(id));
  }

  async create(collection: CollectionName, data: Record<string, unknown>): Promise<unknown> {
    return this.withAuth(() => this.pb.collection(collection).create(data));
  }

  async update(collection: CollectionName, id: string, data: Record<string, unknown>): Promise<unknown> {
    return this.withAuth(() => this.pb.collection(collection).update(id, data));
  }

  async delete(collection: CollectionName, id: string): Promise<void> {
    await this.withAuth(() => this.pb.collection(collection).delete(id));
  }

  async findMcpTokenByHash(tokenHash: string): Promise<McpTokenRecord | null> {
    const safeHash = tokenHash.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    return this.withAuth(async () => {
      try {
        const result = await this.pb.collection('mcp_tokens').getList(1, 1, {
          filter: `token_hash = "${safeHash}"`,
        });
        return (result.items[0] as unknown as McpTokenRecord | undefined) ?? null;
      } catch (error) {
        if (error instanceof Error && error.message.includes('404')) return null;
        throw error;
      }
    });
  }

  async markMcpTokenUsed(id: string, usedAt: Date): Promise<void> {
    await this.withAuth(() => this.pb.collection('mcp_tokens').update(id, { last_used_at: toJoblandDate(usedAt) }));
  }
}
