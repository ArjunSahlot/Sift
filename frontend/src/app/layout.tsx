import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sift",
  description: "Talking-head video dataset curator",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
