'use server';

import PocketBase from 'pocketbase';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { PB_URL, PB_AUTH_COOKIE } from '@/lib/pb';

// PocketBase's default auth token lifetime is ~2 weeks; mirror it on the cookie.
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 14;

export async function loginAction(formData: FormData) {
  const email = (formData.get('email') as string | null)?.trim() ?? '';
  const password = (formData.get('password') as string | null) ?? '';

  if (!email || !password) {
    redirect('/login?error=1');
  }

  // Fresh client per request.
  const pb = new PocketBase(PB_URL);

  try {
    await pb.collection('users').authWithPassword(email, password);
  } catch {
    redirect('/login?error=1');
  }

  if (!pb.authStore.isValid) {
    redirect('/login?error=1');
  }

  // Single canonical PocketBase cookie holding {token, record} JSON — the exact
  // shape pb.authStore.loadFromCookie() expects (used by both the SSR client in
  // lib/pb-server.ts and the browser realtime client).
  //
  // We set the JSON value directly rather than via exportToCookie(): Next's
  // cookies().set() URL-encodes the value itself, and exportToCookie() ALSO
  // url-encodes, which double-encodes and breaks loadFromCookie's single decode.
  const value = JSON.stringify({
    token: pb.authStore.token,
    record: pb.authStore.record,
  });

  cookies().set(PB_AUTH_COOKIE, value, {
    httpOnly: false, // browser PB client reads it for realtime
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: COOKIE_MAX_AGE_SECONDS,
  });

  redirect('/');
}
