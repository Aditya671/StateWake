import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { AttestationTrustPanel } from "@/features/trust/AttestationTrustPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function AttestationTrustPage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Operate · Cryptographic trust</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Attestation Trust & Key Lifecycle Investigation
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 920 }}>
            Inspect the integrity of recorded reliability attestations, authenticate the configured current trust-state snapshot when an independent authority store is available, and distinguish active, revoked, superseded, untrusted, and unresolved signing-key references.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="Attestation integrity, signer authentication, current trust, and historical validity are separate questions"
          description="The canonical attestation store records signing-key references but not signed-envelope bytes. This page therefore does not claim attestation-signature authenticity or reconstruct historical key status that StateWake did not persist."
        />
        <AttestationTrustPanel />
      </Space>
    </AppShell>
  );
}
