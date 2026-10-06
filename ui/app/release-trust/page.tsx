import { Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { ReleaseTrustPanel } from "@/features/operate/ReleaseTrustPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function ReleaseTrustPage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Operate · Release trust</div>
          <Title style={{ margin: "4px 0 8px" }}>Release Trust</Title>
          <Paragraph type="secondary" style={{ maxWidth: 800 }}>
            Inspect structural release evidence, independently checked bytes, signer-authentication status, and human release decision without converting any one signal into publication authority.
          </Paragraph>
        </div>
        <ReleaseTrustPanel />
      </Space>
    </AppShell>
  );
}
