import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CCU Diagnostic Agent",
  description: "Chat with the CCU diagnostic agent",
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
