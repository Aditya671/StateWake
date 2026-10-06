"use client";

import { Layout, Menu, Tag, Typography } from "antd";
import type { ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

const { Sider, Content } = Layout;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const selected = pathname.startsWith("/data-governance")
    ? "data-governance"
    : pathname.startsWith("/authorization-policy")
      ? "authorization-policy"
    : pathname.startsWith("/assurance-decision")
      ? "assurance-decision"
    : pathname.startsWith("/proof-bundle")
    ? "proof-bundle"
    : pathname.startsWith("/security-assurance")
      ? "security-assurance"
    : pathname.startsWith("/decision-lineage")
      ? "decision-lineage"
    : pathname.startsWith("/attestation-trust")
    ? "attestation-trust"
    : pathname.startsWith("/capture-health")
    ? "capture-health"
    : pathname.startsWith("/incidents")
      ? "incidents"
    : pathname === "/claims"
    ? "catalog"
    : pathname.startsWith("/claims/")
      ? "claim"
    : pathname.startsWith("/compare")
      ? "compare"
      : pathname.startsWith("/release-trust")
        ? "release-trust"
        : pathname.startsWith("/validation")
          ? "validation"
          : pathname.startsWith("/workspace")
            ? "workspace"
            : "lookup";

  return (
    <Layout className="sw-shell">
      <Sider className="sw-sidebar" width={248} breakpoint="lg" collapsedWidth={0}>
        <div className="sw-brand">
          <div className="sw-brand-name">StateWake</div>
          <div className="sw-brand-subtitle">v0.5.0 · evidence + operational trust</div>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={[
            { key: "lookup", label: "Claim lookup" },
            { key: "catalog", label: "Claim catalog" },
            { key: "incidents", label: "Incident investigation" },
            { key: "capture-health", label: "Capture health" },
            { key: "security-assurance", label: "Security assurance" },
            { key: "assurance-decision", label: "Assurance decision" },
            { key: "authorization-policy", label: "Access & authorization" },
            { key: "data-governance", label: "Data governance" },
            { key: "attestation-trust", label: "Attestation trust" },
            { key: "proof-bundle", label: "Reliability proof" },
            { key: "decision-lineage", label: "Decision lineage" },
            {
              key: "claim",
              label: "Claim workbench",
              disabled: !pathname.startsWith("/claims/"),
            },
            {
              key: "evidence",
              label: "Evidence explorer",
              disabled: !pathname.startsWith("/claims/"),
            },
            { key: "compare", label: "Compare reports" },
            { type: "divider" },
            { key: "release-trust", label: "Release Trust" },
            { key: "validation", label: "Validation Study" },
            { key: "workspace", label: "Workspace Operations" },
          ]}
          onClick={({ key }) => {
            if (key === "lookup") router.push("/");
            if (key === "catalog") router.push("/claims");
            if (key === "incidents") router.push("/incidents");
            if (key === "capture-health") router.push("/capture-health");
            if (key === "security-assurance") router.push("/security-assurance");
            if (key === "assurance-decision") router.push("/assurance-decision");
            if (key === "authorization-policy") router.push("/authorization-policy");
            if (key === "data-governance") router.push("/data-governance");
            if (key === "attestation-trust") router.push("/attestation-trust");
            if (key === "proof-bundle") router.push("/proof-bundle");
            if (key === "decision-lineage") router.push("/decision-lineage");
            if (key === "claim" && pathname.startsWith("/claims/")) router.push(pathname);
            if (key === "evidence" && pathname.startsWith("/claims/")) {
              router.push(`${pathname}?tab=evidence`);
            }
            if (key === "compare") router.push("/compare");
            if (key === "release-trust") router.push("/release-trust");
            if (key === "validation") router.push("/validation");
            if (key === "workspace") router.push("/workspace");
          }}
        />
        <div style={{ padding: 20 }}>
          <Tag bordered={false}>Evidence-first</Tag>
          <Typography.Paragraph
            style={{ color: "#9ba8b8", marginTop: 12, fontSize: 12 }}
          >
            Canonical evidence, decision lineage, incident recovery, capture failures, deployment security audit, assurance decisions, identity-bound authorization, data governance, attestation trust, portable reliability proofs, release trust, validation studies, workspace operations,
            history, and comparison remain bounded by their source authorities. Review statements
            are append-only; scoped approval and publication authority remain separate.
          </Typography.Paragraph>
        </div>
      </Sider>
      <Layout>
        <Content className="sw-main">
          <div className="sw-page-width">{children}</div>
        </Content>
      </Layout>
    </Layout>
  );
}
