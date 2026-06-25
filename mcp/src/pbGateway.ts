import PocketBase from 'pocketbase';
import type { McpTokenRecord } from './auth.js';
import type { CollectionName, JoblandRecordGateway, ListOptions } from './toolHandlers.js';
import { toJoblandDate } from './time.js';

export type PocketBaseConfig = {
  url: string;
  adminEmail: string;
  adminPassword: string;
};

export class JoblandPocketBaseGateway implements JoblandRecordGateway {
  private readonly pb: PocketBase;
  private authPromise: Promise<void> | null = null;

  constructor(private readonly config: PocketBaseConfig) {
    this.pb = new PocketBase(config.url);
    this.pb.autoCancellation(false);
  }

  private async ensureAuth(): Promise<void> {
    if (!this.authPromise) {
      this.authPromise = this.pb.collection('_superusers').authWithPassword(
        this.config.adminEmail,
        this.config.adminPassword,
      ).then(() => undefined).catch((error) => {
        this.authPromise = null;
        throw error;
      });
    }
    await this.authPromise;
  }

  async list(collection: CollectionName, options: Required<ListOptions>): Promise<unknown[]> {
    await this.ensureAuth();
    return this.pb.collection(collection).getList(options.page, options.perPage, {
      filter: options.filter,
      sort: options.sort,
    }).then((result) => result.items);
  }

  async get(collection: CollectionName, id: string): Promise<unknown> {
    await this.ensureAuth();
    return this.pb.collection(collection).getOne(id);
  }

  async create(collection: CollectionName, data: Record<string, unknown>): Promise<unknown> {
    await this.ensureAuth();
    return this.pb.collection(collection).create(data);
  }

  async update(collection: CollectionName, id: string, data: Record<string, unknown>): Promise<unknown> {
    await this.ensureAuth();
    return this.pb.collection(collection).update(id, data);
  }

  async delete(collection: CollectionName, id: string): Promise<void> {
    await this.ensureAuth();
    await this.pb.collection(collection).delete(id);
  }

  async findMcpTokenByHash(tokenHash: string): Promise<McpTokenRecord | null> {
    await this.ensureAuth();
    const safeHash = tokenHash.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    try {
      const result = await this.pb.collection('mcp_tokens').getList(1, 1, {
        filter: `token_hash = "${safeHash}"`,
      });
      return (result.items[0] as unknown as McpTokenRecord | undefined) ?? null;
    } catch (error) {
      if (error instanceof Error && error.message.includes('404')) return null;
      throw error;
    }
  }

  async markMcpTokenUsed(id: string, usedAt: Date): Promise<void> {
    await this.ensureAuth();
    await this.pb.collection('mcp_tokens').update(id, { last_used_at: toJoblandDate(usedAt) });
  }
}
