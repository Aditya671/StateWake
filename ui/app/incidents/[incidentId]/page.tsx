import { Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { IncidentDetailPanel } from "@/features/incidents/IncidentDetailPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default async function IncidentDetailPage({
  params,
}: {
  params: Promise<{ incidentId: string }>;
}) {
  const { incidentId } = await params;
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Investigate · Incident detail</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Incident reconstruction
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 860 }}>
            Reconstruct recorded lifecycle, preserved evidence references, affected state,
            recovery, and post-recovery verification for one deterministic incident identity.
          </Paragraph>
        </div>
        <IncidentDetailPanel incidentId={incidentId} />
      </Space>
    </AppShell>
  );
}
