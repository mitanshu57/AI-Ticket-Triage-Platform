import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Ticket Triage",
  description: "Auto-classify, prioritize, route, and draft replies for tickets.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
