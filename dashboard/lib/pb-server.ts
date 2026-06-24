import PocketBase from 'pocketbase';
import { headers } from 'next/headers';
import { PB_URL, PB_AUTH_COOKIE } from './pb';

export { PB_URL, PB_AUTH_COOKIE };

/**
 * Build a per-request PocketBase client authenticated as the logged-in user.
 *
 * Canonical PocketBase SSR pattern: load the auth state from the `pb_auth`
 * cookie that the login action set. Every query then runs with the user's
 * token, so PocketBase API rules (locked to `@request.auth.id != ""`) enforce
 * access — no superuser, no custom session layer.
 *
 * Must be called within a request scope (Server Component / Route Handler /
 * Server Action), since it reads the request headers via next/headers.
 */
export function getServerPb(): PocketBase {
  const pb = new PocketBase(PB_URL);
  // Pass the full raw Cookie header — loadFromCookie parses + url-decodes it
  // itself, matching what the login action's exportToCookie produced.
  pb.authStore.loadFromCookie(headers().get('cookie') ?? '');
  return pb;
}

/** True if the current request carries a non-expired PocketBase auth token. */
export function isAuthed(): boolean {
  return getServerPb().authStore.isValid;
}
