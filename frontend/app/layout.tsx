import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Scout — Company Intelligence",
  description: "AI-powered company research agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="min-h-full flex flex-row antialiased">
        <Sidebar />
        <div className="flex-1 min-w-0 overflow-y-auto">
          {children}
        </div>
      </body>
    </html>
  );
}
