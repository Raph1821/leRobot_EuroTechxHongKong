import type { Metadata } from "next";
import { Bricolage_Grotesque, Instrument_Sans } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";
import AppShell from "@/components/shell/AppShell";

// logo face — Aquatico: geometric caps, bar-less triangular A
const logo = localFont({
  src: "./fonts/Aquatico-Regular.otf",
  variable: "--font-logo",
  weight: "400",
});

const display = Bricolage_Grotesque({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "600", "700", "800"],
});

const body = Instrument_Sans({
  variable: "--font-body",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ELDA - App",
  description:
    "Elda — an AI-powered robotic arm assistant for elderly care. SO-101 control, monitoring, medication and emergencies. EuroTech Hong Kong Hackathon, Munich 2026.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${body.variable} ${logo.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
