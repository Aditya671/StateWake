import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { SecurityAssurancePanel } from "@/features/security/SecurityAssurancePanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function SecurityAssurancePage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Operate · Deployment security</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Security Audit & Deployment Assurance Investigation
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 920 }}>
            Inspect the configured hash-linked deployment-security audit chain and the repository’s protected-operation boundary without claiming visibility into unpersisted host security configuration.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="Observed audit evidence is not a deployment-security certification"
          description="StateWake can verify the integrity of recorded authentication, authorization, admission, HTTPS-rejection, and admitted-request events. TLS termination, real identity-provider correctness, tenant isolation, KMS/HSM custody, process isolation, quotas, and network controls remain deployment responsibilities unless independently evidenced elsewhere."
        />
        <SecurityAssurancePanel />
      </Space>
    </AppShell>
  );
}
