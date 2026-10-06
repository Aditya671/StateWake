import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { DecisionLineagePanel } from "@/features/decisions/DecisionLineagePanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function DecisionLineagePage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Explain · Decision basis and lineage</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Reliability Decision Basis, Reconciliation &amp; Lineage Investigation
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 960 }}>
            Reconstruct the exact digest-bound inputs behind one configured reliability decision, its discrepancy/reconciliation evidence, recovery binding when applicable, and the verified provenance path back to the declared run.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="Recorded decision evidence is not external truth or business authorization"
          description="This surface verifies StateWake's bounded identities, digests, reconciliation relationships, and lineage closure. It does not recompute the host decision, expose raw source files, or authorize publication or execution."
        />
        <DecisionLineagePanel />
      </Space>
    </AppShell>
  );
}
