import { Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { WorkspaceOperationsPanel } from "@/features/operate/WorkspaceOperationsPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function WorkspacePage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Operate · Workspace</div>
          <Title style={{ margin: "4px 0 8px" }}>Workspace Operations</Title>
          <Paragraph type="secondary" style={{ maxWidth: 800 }}>
            Inspect durable workspace integrity, storage, records, lifecycle, exports, and current operational limits through a genuinely read-only SQLite connection.
          </Paragraph>
        </div>
        <WorkspaceOperationsPanel />
      </Space>
    </AppShell>
  );
}
