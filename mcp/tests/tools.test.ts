import { describe, expect, it, vi } from 'vitest';
import { createJoblandToolHandlers, type AuthInfo, type JoblandRecordGateway } from '../src/toolHandlers.js';

const fullAuth: AuthInfo = {
  tokenId: 'env:MCP_API_TOKEN',
  name: 'MCP_API_TOKEN',
  scopes: ['jobs:*', 'interviews:*'],
};

function gateway(): JoblandRecordGateway {
  return {
    list: vi.fn(async () => [{ id: 'job_1', title: 'AI Engineer' }]),
    get: vi.fn(async (_collection, id) => ({ id, title: 'AI Engineer' })),
    create: vi.fn(async (_collection, data) => ({ id: 'new_id', ...data })),
    update: vi.fn(async (_collection, id, data) => ({ id, ...data })),
    delete: vi.fn(async () => undefined),
  };
}

describe('jobland tool handlers', () => {
  it('patches arbitrary job fields except system fields', async () => {
    const pb = gateway();
    const tools = createJoblandToolHandlers(pb, fullAuth, () => new Date('2026-06-24T12:00:00.000Z'));

    await expect(tools.jobs_update({
      id: 'job_1',
      fields: { title: 'Staff AI Engineer', user_status: 'interesting' },
    })).resolves.toEqual({
      id: 'job_1',
      title: 'Staff AI Engineer',
      user_status: 'interesting',
    });

    expect(pb.update).toHaveBeenCalledWith('jobs', 'job_1', {
      title: 'Staff AI Engineer',
      user_status: 'interesting',
    });
  });

  it('rejects job patches that contain system fields', async () => {
    const tools = createJoblandToolHandlers(gateway(), fullAuth);

    await expect(tools.jobs_update({
      id: 'job_1',
      fields: { id: 'other' },
    })).rejects.toThrow('Cannot patch system field: id');
  });

  it('soft-deletes jobs by setting deleted_at and updated_at', async () => {
    const pb = gateway();
    const now = new Date('2026-06-24T12:00:00.000Z');
    const tools = createJoblandToolHandlers(pb, fullAuth, () => now);

    await tools.jobs_delete({ id: 'job_1' });

    expect(pb.update).toHaveBeenCalledWith('jobs', 'job_1', {
      deleted_at: '2026-06-24 12:00:00',
      updated_at: '2026-06-24 12:00:00',
    });
    expect(pb.delete).not.toHaveBeenCalled();
  });

  it('hard-deletes interviews', async () => {
    const pb = gateway();
    const tools = createJoblandToolHandlers(pb, fullAuth);

    await expect(tools.interviews_delete({ id: 'int_1' })).resolves.toEqual({ ok: true });

    expect(pb.delete).toHaveBeenCalledWith('interviews', 'int_1');
  });

  it('enforces read/write scopes per collection', async () => {
    const readOnlyAuth: AuthInfo = { tokenId: 'tok_1', name: 'Read only', scopes: ['jobs:read'] };
    const tools = createJoblandToolHandlers(gateway(), readOnlyAuth);

    await expect(tools.jobs_list({})).resolves.toEqual([{ id: 'job_1', title: 'AI Engineer' }]);
    await expect(tools.jobs_update({ id: 'job_1', fields: { title: 'New' } })).rejects.toThrow('Missing scope');
    await expect(tools.interviews_list({})).rejects.toThrow('Missing scope');
  });

  it('builds exact-url and text search filters', async () => {
    const pb = gateway();
    const tools = createJoblandToolHandlers(pb, fullAuth);

    await tools.jobs_find_by_url({ url: 'https://example.com/jobs/1' });
    await tools.interviews_search({ query: 'acme' });

    expect(pb.list).toHaveBeenNthCalledWith(1, 'jobs', {
      filter: 'url = "https://example.com/jobs/1" && deleted_at = null',
      page: 1,
      perPage: 1,
      sort: '-created_at',
    });
    expect(pb.list).toHaveBeenNthCalledWith(2, 'interviews', {
      filter: '(company_name ~ "acme" || job_title ~ "acme" || job_url ~ "acme" || comments ~ "acme" || contacts ~ "acme")',
      page: 1,
      perPage: 50,
      sort: '-updated_at',
    });
  });
});
