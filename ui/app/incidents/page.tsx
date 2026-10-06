import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { IncidentPortfolioPanel } from "@/features/incidents/IncidentPortfolioPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function IncidentsPage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Investigate · Incident recovery</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Incident & Recovery Investigation
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 860 }}>
            Inspect StateWake&apos;s canonical hash-linked incident evidence, lifecycle observations,
            affected trust state, recovery records, and post-recovery reverification without
            mutating the incident store or inferring causal claims that were never recorded.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="Evidence reconstruction, not incident-response automation"
          description="This surface reads the configured StateWake incident-evidence chain. It does not perform containment, remediation, ticketing, rollback, or external payload verification."
        />
        <IncidentPortfolioPanel />
      </Space>
    </AppShell>
  );
}
