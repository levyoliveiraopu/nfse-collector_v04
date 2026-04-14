import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Toaster } from "sonner";
import { AuthProvider } from "@/components/auth/auth-provider";
import { AppQueryClientProvider } from "@/components/providers/query-client-provider";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "NFS-e SaaS — Painel",
  description: "Painel logado da plataforma NFS-e SaaS.",
};

// Script inline para evitar FOUC ao resolver o tema (light/dark) antes da
// hidratacao. Le preferencia persistida em localStorage ou cai em
// `prefers-color-scheme`.
const themeInitScript = `
(function () {
  try {
    var stored = localStorage.getItem("theme");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var theme = stored || (prefersDark ? "dark" : "light");
    if (theme === "dark") document.documentElement.classList.add("dark");
  } catch (_) {}
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="pt-BR"
      suppressHydrationWarning
      className={`${inter.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <AppQueryClientProvider>
          <AuthProvider>{children}</AuthProvider>
        </AppQueryClientProvider>
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
