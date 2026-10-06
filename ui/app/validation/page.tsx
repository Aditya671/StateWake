import { Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { ValidationStudyPanel } from "@/features/operate/ValidationStudyPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function ValidationPage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Operate · Comparative validation</div>
          <Title style={{ margin: "4px 0 8px" }}>Validation Study</Title>
          <Paragraph type="secondary" style={{ maxWidth: 800 }}>
            Review one frozen deterministic comparative study with its actual denominators, fixture scope, injected faults, and limitations. No live benchmark runs from this page.
          </Paragraph>
        </div>
        <ValidationStudyPanel />
      </Space>
    </AppShell>
  );
}
