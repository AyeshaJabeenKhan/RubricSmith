import type { Metadata } from "next";
import "@fontsource/fraunces/600.css";
import "@fontsource/work-sans/400.css";
import "@fontsource/work-sans/600.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "RubricSmith",
  description: "Grade LLM answers against known-good answers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
