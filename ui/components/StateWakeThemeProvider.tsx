"use client";

import { ConfigProvider, theme } from "antd";
import type { ReactNode } from "react";

export function StateWakeThemeProvider({ children }: { children: ReactNode }) {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorBgBase: "#0b0e13",
          colorBgContainer: "#151a22",
          colorBgElevated: "#1b212b",
          colorBorder: "#2a3442",
          colorText: "#f4f7fb",
          colorTextSecondary: "#9aa8b8",
          borderRadius: 16,
          borderRadiusLG: 22,
          controlHeight: 40,
          fontSize: 15,
        },
        components: {
          Card: {
            headerBg: "transparent",
          },
          Layout: {
            bodyBg: "#0b0e13",
            siderBg: "#090c11",
          },
          Menu: {
            darkItemBg: "#090c11",
            darkSubMenuItemBg: "#090c11",
            darkItemSelectedBg: "#182334",
          },
        },
      }}
    >
      {children}
    </ConfigProvider>
  );
}
