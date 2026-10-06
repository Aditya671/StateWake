"use client";

import { Tag } from "antd";
import { stateFacetPresentation } from "@/lib/semantics/state";

export function StateFacet({ value }: { value: string }) {
  const presentation = stateFacetPresentation(value);
  if (presentation.tone === "default") {
    return <Tag>{presentation.label}</Tag>;
  }
  return <Tag color={presentation.tone}>{presentation.label}</Tag>;
}
