import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { DataGovernancePanel } from "@/features/governance/DataGovernancePanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function DataGovernancePage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Operate · Data governance</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Data Governance, Retention, Disclosure & Deletion Investigation
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 940 }}>
            Reconstruct one workspace-controlled object&apos;s lifecycle from the existing StateWake policy contract, durable retention/legal-hold metadata, deterministic lifecycle decision, and payload-free deletion tombstone.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="Read-only lifecycle reconstruction, not a deletion or compliance control plane"
          description="Retention expiry, legal hold, disclosure eligibility, encryption/TLS requirements, and deletion history are displayed as separate facts. This page does not delete data, disclose data, verify host encryption/TLS, or prove erasure of copies outside StateWake's managed boundary."
        />
        <DataGovernancePanel />
      </Space>
    </AppShell>
  );
}
