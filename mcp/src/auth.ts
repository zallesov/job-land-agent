import { createHash, timingSafeEqual } from 'node:crypto';

export type AuthInfo = {
  tokenId: string;
  name: string;
  scopes: string[];
};

export type McpTokenRecord = {
  id: string;
  name?: string;
  token_hash?: string;
  scopes?: unknown;
  enabled?: boolean;
  expires_at?: string;
  last_used_at?: string;
};

export type AuthSuccess = { ok: true; auth: AuthInfo };
export type AuthFailure = { ok: false; status: 401 | 403; error: string };
export type AuthResult = AuthSuccess | AuthFailure;

export type AuthorizeOptions = {
  authorization: string | undefined;
  envToken: string | undefined;
  findDbTokenByHash: (hash: string) => Promise<McpTokenRecord | null>;
  markTokenUsed: (id: string, usedAt: Date) => Promise<void>;
  now?: Date;
};

const FULL_SCOPES = ['jobs:*', 'interviews:*'];

export function hashToken(token: string): string {
  return createHash('sha256').update(token, 'utf8').digest('hex');
}

function constantTimeEqual(a: string, b: string): boolean {
  const left = Buffer.from(a, 'utf8');
  const right = Buffer.from(b, 'utf8');
  if (left.length !== right.length) return false;
  return timingSafeEqual(left, right);
}

function parseBearer(authorization: string | undefined): string | null {
  if (!authorization) return null;
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  return match?.[1]?.trim() || null;
}

function parseScopes(scopes: unknown): string[] {
  if (Array.isArray(scopes)) return scopes.filter((scope): scope is string => typeof scope === 'string');
  if (typeof scopes === 'string') {
    try {
      const parsed = JSON.parse(scopes) as unknown;
      if (Array.isArray(parsed)) return parsed.filter((scope): scope is string => typeof scope === 'string');
    } catch {
      return scopes.split(',').map((scope) => scope.trim()).filter(Boolean);
    }
  }
  return [];
}

function isExpired(expiresAt: string | undefined, now: Date): boolean {
  if (!expiresAt) return false;
  const normalized = expiresAt.includes('T') ? expiresAt : `${expiresAt.replace(' ', 'T')}Z`;
  const expires = new Date(normalized);
  return Number.isFinite(expires.getTime()) && expires.getTime() <= now.getTime();
}

export async function authorizeBearerToken(options: AuthorizeOptions): Promise<AuthResult> {
  const token = parseBearer(options.authorization);
  if (!token) return { ok: false, status: 401, error: 'Missing bearer token' };

  if (options.envToken && constantTimeEqual(token, options.envToken)) {
    return {
      ok: true,
      auth: {
        tokenId: 'env:MCP_API_TOKEN',
        name: 'MCP_API_TOKEN',
        scopes: FULL_SCOPES,
      },
    };
  }

  const tokenHash = hashToken(token);
  const record = await options.findDbTokenByHash(tokenHash);
  if (!record) return { ok: false, status: 401, error: 'Invalid bearer token' };
  if (!record.enabled) return { ok: false, status: 403, error: 'Token is disabled' };

  const now = options.now ?? new Date();
  if (isExpired(record.expires_at, now)) return { ok: false, status: 403, error: 'Token is expired' };

  await options.markTokenUsed(record.id, now);

  return {
    ok: true,
    auth: {
      tokenId: record.id,
      name: record.name || record.id,
      scopes: parseScopes(record.scopes),
    },
  };
}

export function hasScope(auth: AuthInfo, collection: 'jobs' | 'interviews', action: 'read' | 'write'): boolean {
  return auth.scopes.includes(`${collection}:*`) || auth.scopes.includes(`${collection}:${action}`);
}

