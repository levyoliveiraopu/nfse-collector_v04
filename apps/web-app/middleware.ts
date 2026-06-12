import { NextResponse, type NextRequest } from "next/server";

const REFRESH_COOKIE_NAME = "nfse_refresh";
const LOGIN_PATH = "/login";

export function middleware(request: NextRequest) {
  const hasRefreshCookie = Boolean(request.cookies.get(REFRESH_COOKIE_NAME)?.value);
  if (hasRefreshCookie) {
    return NextResponse.next();
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = LOGIN_PATH;
  loginUrl.searchParams.set(
    "next",
    `${request.nextUrl.pathname}${request.nextUrl.search}`,
  );
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/empresas/:path*",
    "/execucoes/:path*",
    "/agendamentos/:path*",
    "/ocorrencias/:path*",
    "/arquivos/:path*",
    "/usuarios/:path*",
  ],
};
