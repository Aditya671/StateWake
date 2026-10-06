import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { ClaimCatalogPanel } from "@/features/claims/ClaimCatalogPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function ClaimsPage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Portfolio investigation</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Claim catalog
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 840 }}>
            Discover canonical StateWake verification reports by recorded claim identity,
            decision, verification, approval status, profile, and candidate. Open exact
            reports or select two for evidence-preserving comparison.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="Discovery is bounded and evidence-backed"
          description="The catalog verifies canonical report artifacts through the same workspace authority used by the claim workbench. It is not a reliability score, search index, or authorization surface."
        />
        <ClaimCatalogPanel />
      </Space>
    </AppShell>
  );
}
