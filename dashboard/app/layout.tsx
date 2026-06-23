import type { Metadata } from "next";
import { Outfit, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "JobLandAgent",
  description: "Automated job search pipeline",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${outfit.variable} ${mono.variable}`}>
        <nav style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }} className="flex items-center gap-1 px-4 py-2 text-sm">
          <Link href="/" className="px-3 py-1 rounded hover:bg-white/5 transition-colors" style={{ color: "var(--text-2)" }}>Jobs</Link>
          <Link href="/interviews" className="px-3 py-1 rounded hover:bg-white/5 transition-colors" style={{ color: "var(--text-2)" }}>Interviews</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
