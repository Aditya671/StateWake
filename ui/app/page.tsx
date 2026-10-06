import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { ClaimLookup } from "@/features/claims/ClaimLookup";
import { OverviewPanel } from "@/features/overview/OverviewPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function HomePage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Inspection</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Claim workbench
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 760 }}>
            Inspect one canonical StateWake verification report without changing its
            verification, approval, or publication state.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="Evidence-backed overview and human review"
          description="Overview cards are computed from canonical verification-report records. Claim detail, comparison, history, append-only review statements, and explicitly configured HumanApprovalContract writes remain separate from machine verification and publication."
        />
        <OverviewPanel />
        <ClaimLookup />
      </Space>
    </AppShell>
  );
}
