import { NextRequest, NextResponse } from 'next/server';
import { PB_AUTH_COOKIE } from '@/lib/pb';

function clearAndRedirect(request: NextRequest): NextResponse {
  const url = new URL('/login', request.url);
  const response = NextResponse.redirect(url);
  response.cookies.delete(PB_AUTH_COOKIE);
  return response;
}

export function GET(request: NextRequest) {
  return clearAndRedirect(request);
}

export function POST(request: NextRequest) {
  return clearAndRedirect(request);
}
