import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { AssuranceDecisionPanel } from "@/features/security/AssuranceDecisionPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function AssuranceDecisionPage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Operate · Security assurance</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Security Assurance Decision & Operational Exception Investigation
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 920 }}>
            Inspect one explicitly configured StateWake assurance decision and optional operational exception with deterministic policy replay and exact decision binding.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="Operational exceptions preserve—not rewrite—the underlying assurance state"
          description="This surface does not infer factual correctness, publication permission, compliance certification, or broader host authorization."
        />
        <AssuranceDecisionPanel />
      </Space>
    </AppShell>
  );
}
