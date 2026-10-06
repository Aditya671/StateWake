import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { ReliabilityProofPanel } from "@/features/proofs/ReliabilityProofPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function ProofBundlePage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Verify · Portable reliability proof</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Reliability Proof Bundle & Portable Verification Investigation
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 960 }}>
            Inspect one explicitly configured portable reliability proof bundle after StateWake independently re-verifies its operational manifest, packaged evidence relationships, outcome verification, lineage, and format-specific completeness requirements.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="A verified proof is not publication authority or external factual truth"
          description="Reliability proof bundles are distinct from workspace portable dataset exports. Packaged trust material can establish internal portable consistency, but external trust in the packaged authority still belongs to the relying operator."
        />
        <ReliabilityProofPanel />
      </Space>
    </AppShell>
  );
}
