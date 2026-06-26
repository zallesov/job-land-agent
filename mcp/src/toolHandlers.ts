import { hasScope, type AuthInfo } from './auth.js';
import { toJoblandDate } from './time.js';

export type { AuthInfo } from './auth.js';

export type CollectionName = 'jobs' | 'interviews';

export type ListOptions = {
  filter?: string;
  sort?: string;
  page?: number;
  perPage?: number;
};

export type JoblandRecordGateway = {
  list: (collection: CollectionName, options: Required<ListOptions>) => Promise<unknown[]>;
  get: (collection: CollectionName, id: string) => Promise<unknown>;
  create: (collection: CollectionName, data: Record<string, unknown>) => Promise<unknown>;
  update: (collection: CollectionName, id: string, data: Record<string, unknown>) => Promise<unknown>;
  delete: (collection: CollectionName, id: string) => Promise<void>;
};

export type JoblandToolHandlers = ReturnType<typeof createJoblandToolHandlers>;

export type JobSearchInput = {
  url?: string;
  id?: string;
  company?: string;
  title?: string;
  page?: number;
  perPage?: number;
};

const SYSTEM_FIELDS = new Set(['id', 'collectionId', 'collectionName', 'created', 'updated']);

function assertScope(auth: AuthInfo, collection: CollectionName, action: 'read' | 'write'): void {
  if (!hasScope(auth, collection, action)) {
    throw new Error(`Missing scope: ${collection}:${action}`);
  }
}

function assertPatchFields(fields: unknown): asserts fields is Record<string, unknown> {
  if (!fields || typeof fields !== 'object' || Array.isArray(fields)) {
    throw new Error('fields must be an object');
  }
  for (const field of Object.keys(fields)) {
    if (SYSTEM_FIELDS.has(field)) {
      throw new Error(`Cannot patch system field: ${field}`);
    }
  }
}

function esc(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

function listOptions(input: ListOptions, defaults: { sort: string; perPage?: number }): Required<ListOptions> {
  return {
    filter: input.filter ?? '',
    sort: input.sort ?? defaults.sort,
    page: input.page ?? 1,
    perPage: input.perPage ?? defaults.perPage ?? 50,
  };
}

function textSearchFilter(fields: string[], query: string): string {
  const safe = esc(query);
  return `(${fields.map((field) => `${field} ~ "${safe}"`).join(' || ')})`;
}

function assertNonEmptyIds(ids: string[]): void {
  if (!Array.isArray(ids) || ids.length === 0) {
    throw new Error('ids must contain at least one id');
  }
}

function jobSearchFilter(input: JobSearchInput): string {
  const selectors = [
    input.url ? { field: 'url', value: input.url, op: '=' } : null,
    input.id ? { field: 'id', value: input.id, op: '=' } : null,
    input.company ? { field: 'posted_company_name', value: input.company, op: '~' } : null,
    input.title ? { field: 'title', value: input.title, op: '~' } : null,
  ].filter((selector): selector is { field: string; value: string; op: '=' | '~' } => selector !== null);

  if (selectors.length !== 1) {
    throw new Error('Provide exactly one of: url, id, company, title');
  }

  const selector = selectors[0];
  return `${selector.field} ${selector.op} "${esc(selector.value)}" && deleted_at = null`;
}

export function createJoblandToolHandlers(
  pb: JoblandRecordGateway,
  auth: AuthInfo,
  now: () => Date = () => new Date(),
) {
  return {
    async jobs_list(input: ListOptions & { origin?: string; status?: string } = {}) {
      assertScope(auth, 'jobs', 'read');
      const clauses: string[] = [];
      if (input.filter) clauses.push(`(${input.filter})`);
      if (input.origin) clauses.push(`provider = "${esc(input.origin)}"`);
      if (input.status) clauses.push(`status = "${esc(input.status)}"`);
      clauses.push('deleted_at = null');
      const filter = clauses.join(' && ');
      return pb.list('jobs', listOptions({ ...input, filter }, { sort: '-created_at', perPage: 100 }));
    },

    async jobs_get(input: { id: string }) {
      assertScope(auth, 'jobs', 'read');
      return pb.get('jobs', input.id);
    },

    async jobs_create(input: { fields: Record<string, unknown> }) {
      assertScope(auth, 'jobs', 'write');
      assertPatchFields(input.fields);
      return pb.create('jobs', input.fields);
    },

    async jobs_update(input: { id: string; fields: Record<string, unknown> }) {
      assertScope(auth, 'jobs', 'write');
      assertPatchFields(input.fields);
      return pb.update('jobs', input.id, input.fields);
    },

    async jobs_delete(input: { id: string }) {
      assertScope(auth, 'jobs', 'write');
      const stamp = toJoblandDate(now());
      return pb.update('jobs', input.id, { deleted_at: stamp, updated_at: stamp });
    },

    async jobs_delete_batch(input: { ids: string[] }) {
      assertScope(auth, 'jobs', 'write');
      assertNonEmptyIds(input.ids);
      const stamp = toJoblandDate(now());
      await Promise.all(input.ids.map((id) => (
        pb.update('jobs', id, { deleted_at: stamp, updated_at: stamp })
      )));
      return { ok: true, deleted: input.ids };
    },

    async jobs_find_by_url(input: { url: string }) {
      assertScope(auth, 'jobs', 'read');
      const items = await pb.list('jobs', {
        filter: `url = "${esc(input.url)}" && deleted_at = null`,
        page: 1,
        perPage: 1,
        sort: '-created_at',
      });
      return items[0] ?? null;
    },

    async jobs_search(input: JobSearchInput) {
      assertScope(auth, 'jobs', 'read');
      const filter = jobSearchFilter(input);
      return pb.list('jobs', listOptions({ filter, page: input.page, perPage: input.perPage }, { sort: '-updated_at' }));
    },

    async interviews_list(input: ListOptions = {}) {
      assertScope(auth, 'interviews', 'read');
      return pb.list('interviews', listOptions(input, { sort: '-updated_at', perPage: 100 }));
    },

    async interviews_get(input: { id: string }) {
      assertScope(auth, 'interviews', 'read');
      return pb.get('interviews', input.id);
    },

    async interviews_create(input: { fields: Record<string, unknown> }) {
      assertScope(auth, 'interviews', 'write');
      assertPatchFields(input.fields);
      return pb.create('interviews', input.fields);
    },

    async interviews_update(input: { id: string; fields: Record<string, unknown> }) {
      assertScope(auth, 'interviews', 'write');
      assertPatchFields(input.fields);
      return pb.update('interviews', input.id, input.fields);
    },

    async interviews_delete(input: { id: string }) {
      assertScope(auth, 'interviews', 'write');
      await pb.delete('interviews', input.id);
      return { ok: true };
    },

    async interviews_search(input: { query: string; page?: number; perPage?: number }) {
      assertScope(auth, 'interviews', 'read');
      const filter = textSearchFilter(['company_name', 'job_title', 'job_url', 'comments', 'contacts'], input.query);
      return pb.list('interviews', listOptions({ filter, page: input.page, perPage: input.perPage }, { sort: '-updated_at' }));
    },
  };
}
