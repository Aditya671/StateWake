import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { AccessAuthorizationPanel } from "@/features/security/AccessAuthorizationPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function AuthorizationPolicyPage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Operate · Identity-bound access</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Identity-Bound Access & Authorization Policy Investigation
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 920 }}>
            Reconstruct one StateWake authorization decision from an explicitly configured principal, least-privilege grant policy, and resource request without turning StateWake into an identity provider or IAM database.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="Authorization consumes an externally authenticated principal"
          description="This view verifies StateWake's deny-by-default role/operation/resource-state policy replay. It does not authenticate the caller, validate MFA/session/TLS, prove tenant isolation, or grant broader business authority."
        />
        <AccessAuthorizationPanel />
      </Space>
    </AppShell>
  );
}
