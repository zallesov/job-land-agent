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

  it('soft-deletes a batch of jobs with one timestamp', async () => {
    const pb = gateway();
    const now = new Date('2026-06-24T12:00:00.000Z');
    const tools = createJoblandToolHandlers(pb, fullAuth, () => now);

    await expect(tools.jobs_delete_batch({ ids: ['job_1', 'job_2'] })).resolves.toEqual({
      ok: true,
      deleted: ['job_1', 'job_2'],
    });

    expect(pb.update).toHaveBeenCalledTimes(2);
    expect(pb.update).toHaveBeenNthCalledWith(1, 'jobs', 'job_1', {
      deleted_at: '2026-06-24 12:00:00',
      updated_at: '2026-06-24 12:00:00',
    });
    expect(pb.update).toHaveBeenNthCalledWith(2, 'jobs', 'job_2', {
      deleted_at: '2026-06-24 12:00:00',
      updated_at: '2026-06-24 12:00:00',
    });
    expect(pb.delete).not.toHaveBeenCalled();
  });

  it('rejects empty batch job deletes', async () => {
    const tools = createJoblandToolHandlers(gateway(), fullAuth);

    await expect(tools.jobs_delete_batch({ ids: [] })).rejects.toThrow('ids must contain at least one id');
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

  it('combines origin, status, and raw filter into the jobs_list filter', async () => {
    const pb = gateway();
    const tools = createJoblandToolHandlers(pb, fullAuth);

    await tools.jobs_list({ origin: 'csvfeed', status: 'screened', filter: 'salary_max > 100' });

    expect(pb.list).toHaveBeenCalledWith('jobs', {
      filter: '(salary_max > 100) && provider = "csvfeed" && status = "screened" && deleted_at = null',
      page: 1,
      perPage: 100,
      sort: '-created_at',
    });
  });

  it('keeps jobs_list behavior identical when origin/status are absent', async () => {
    const pb = gateway();
    const tools = createJoblandToolHandlers(pb, fullAuth);

    await tools.jobs_list({});

    expect(pb.list).toHaveBeenCalledWith('jobs', {
      filter: 'deleted_at = null',
      page: 1,
      perPage: 100,
      sort: '-created_at',
    });
  });

  it('escapes quotes in origin/status values', async () => {
    const pb = gateway();
    const tools = createJoblandToolHandlers(pb, fullAuth);

    await tools.jobs_list({ origin: 'we"ll', status: 'lis"ted' });

    expect(pb.list).toHaveBeenCalledWith('jobs', {
      filter: 'provider = "we\\"ll" && status = "lis\\"ted" && deleted_at = null',
      page: 1,
      perPage: 100,
      sort: '-created_at',
    });
  });

  it('builds exact-url, exact-id, company, and title job search filters', async () => {
    const pb = gateway();
    const tools = createJoblandToolHandlers(pb, fullAuth);

    await tools.jobs_find_by_url({ url: 'https://example.com/jobs/1' });
    await tools.jobs_search({ url: 'https://example.com/jobs/1' });
    await tools.jobs_search({ id: 'job_1' });
    await tools.jobs_search({ company: 'acme' });
    await tools.jobs_search({ title: 'engineer' });

    expect(pb.list).toHaveBeenNthCalledWith(1, 'jobs', {
      filter: 'url = "https://example.com/jobs/1" && deleted_at = null',
      page: 1,
      perPage: 1,
      sort: '-created_at',
    });
    expect(pb.list).toHaveBeenNthCalledWith(2, 'jobs', {
      filter: 'url = "https://example.com/jobs/1" && deleted_at = null',
      page: 1,
      perPage: 50,
      sort: '-updated_at',
    });
    expect(pb.list).toHaveBeenNthCalledWith(3, 'jobs', {
      filter: 'id = "job_1" && deleted_at = null',
      page: 1,
      perPage: 50,
      sort: '-updated_at',
    });
    expect(pb.list).toHaveBeenNthCalledWith(4, 'jobs', {
      filter: 'posted_company_name ~ "acme" && deleted_at = null',
      page: 1,
      perPage: 50,
      sort: '-updated_at',
    });
    expect(pb.list).toHaveBeenNthCalledWith(5, 'jobs', {
      filter: 'title ~ "engineer" && deleted_at = null',
      page: 1,
      perPage: 50,
      sort: '-updated_at',
    });
  });

  it('requires exactly one job search selector', async () => {
    const tools = createJoblandToolHandlers(gateway(), fullAuth);

    await expect(tools.jobs_search({})).rejects.toThrow('Provide exactly one of: url, id, company, title');
    await expect(tools.jobs_search({ id: 'job_1', title: 'engineer' })).rejects.toThrow('Provide exactly one of: url, id, company, title');
  });

  it('builds interview text search filters', async () => {
    const pb = gateway();
    const tools = createJoblandToolHandlers(pb, fullAuth);

    await tools.interviews_search({ query: 'acme' });

    expect(pb.list).toHaveBeenNthCalledWith(1, 'interviews', {
      filter: '(company_name ~ "acme" || job_title ~ "acme" || job_url ~ "acme" || comments ~ "acme" || contacts ~ "acme")',
      page: 1,
      perPage: 50,
      sort: '-updated_at',
    });
  });
});
