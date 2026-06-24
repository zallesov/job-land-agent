import { NextResponse } from 'next/server';
import { redirect } from 'next/navigation';
import { getServerPb } from './pb-server';

/**
 * Server-component guard for protected pages. Redirects to /login when the
 * request carries no valid PocketBase auth token. Pure UX — real data
 * protection is enforced by PocketBase API rules + the route-handler guard.
 */
export function requireAuthPage(): void {
  if (!getServerPb().authStore.isValid) {
    redirect('/login');
  }
}

/**
 * Route-handler guard. Returns a 401 JSON response if the request is not
 * carrying a valid PocketBase auth token, otherwise null (caller proceeds).
 *
 * Real data protection comes from PocketBase API rules; this just gives the
 * browser a clean 401 to react to instead of leaking PB error shapes.
 */
export function unauthorizedResponse(): NextResponse | null {
  if (getServerPb().authStore.isValid) return null;
  return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
}
