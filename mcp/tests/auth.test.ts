import { describe, expect, it, vi } from 'vitest';
import { authorizeBearerToken, hashToken, type McpTokenRecord } from '../src/auth.js';

const now = new Date('2026-06-24T12:00:00.000Z');

function tokenRecord(token: string, overrides: Partial<McpTokenRecord> = {}): McpTokenRecord {
  return {
    id: 'tok_1',
    name: 'Hermes',
    token_hash: hashToken(token),
    scopes: ['jobs:*', 'interviews:*'],
    enabled: true,
    expires_at: '',
    last_used_at: '',
    ...overrides,
  };
}

describe('authorizeBearerToken', () => {
  it('rejects missing Authorization header', async () => {
    const result = await authorizeBearerToken({
      authorization: undefined,
      envToken: 'env-secret',
      findDbTokenByHash: vi.fn(),
      markTokenUsed: vi.fn(),
      now,
    });

    expect(result.ok).toBe(false);
    expect(result.ok ? '' : result.status).toBe(401);
  });

  it('accepts the bootstrap MCP_API_TOKEN with full scopes', async () => {
    const result = await authorizeBearerToken({
      authorization: 'Bearer env-secret',
      envToken: 'env-secret',
      findDbTokenByHash: vi.fn(),
      markTokenUsed: vi.fn(),
      now,
    });

    expect(result).toEqual({
      ok: true,
      auth: {
        tokenId: 'env:MCP_API_TOKEN',
        name: 'MCP_API_TOKEN',
        scopes: ['jobs:*', 'interviews:*'],
      },
    });
  });

  it('accepts an enabled non-expired database token and updates last_used_at', async () => {
    const record = tokenRecord('db-secret');
    const markTokenUsed = vi.fn();

    const result = await authorizeBearerToken({
      authorization: 'Bearer db-secret',
      envToken: 'env-secret',
      findDbTokenByHash: vi.fn(async () => record),
      markTokenUsed,
      now,
    });

    expect(result.ok).toBe(true);
    expect(result.ok ? result.auth : null).toEqual({
      tokenId: 'tok_1',
      name: 'Hermes',
      scopes: ['jobs:*', 'interviews:*'],
    });
    expect(markTokenUsed).toHaveBeenCalledWith('tok_1', now);
  });

  it('rejects disabled database tokens', async () => {
    const result = await authorizeBearerToken({
      authorization: 'Bearer db-secret',
      envToken: '',
      findDbTokenByHash: vi.fn(async () => tokenRecord('db-secret', { enabled: false })),
      markTokenUsed: vi.fn(),
      now,
    });

    expect(result.ok).toBe(false);
    expect(result.ok ? '' : result.status).toBe(403);
  });

  it('rejects expired database tokens', async () => {
    const result = await authorizeBearerToken({
      authorization: 'Bearer db-secret',
      envToken: '',
      findDbTokenByHash: vi.fn(async () => tokenRecord('db-secret', { expires_at: '2026-06-24 11:59:59' })),
      markTokenUsed: vi.fn(),
      now,
    });

    expect(result.ok).toBe(false);
    expect(result.ok ? '' : result.status).toBe(403);
  });
});
