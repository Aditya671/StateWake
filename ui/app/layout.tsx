import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { StateWakeThemeProvider } from "@/components/StateWakeThemeProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "StateWake inspection",
  description: "StateWake verification report inspection and bounded human review",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AntdRegistry><StateWakeThemeProvider>{children}</StateWakeThemeProvider></AntdRegistry>
      </body>
    </html>
  );
}
