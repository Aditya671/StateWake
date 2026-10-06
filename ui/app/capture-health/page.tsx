import { Alert, Space } from "antd";
import { AppShell } from "@/components/AppShell";
import { CaptureHealthPanel } from "@/features/capture/CaptureHealthPanel";
import { Paragraph, Title } from "@/components/AntdTypography";

export default function CaptureHealthPage() {
  return (
    <AppShell>
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Operate · Producer capture</div>
          <Title style={{ margin: "4px 0 8px" }}>
            Producer Capture Health & Failure Journal Investigation
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 900 }}>
            Inspect the configured native capture failure journal, its bounded redacted failure records,
            aggregate stages, and declared journal-capacity context without attaching to or mutating a live capture sink.
          </Paragraph>
        </div>
        <Alert
          type="info"
          showIcon
          message="Recorded failures are evidence; missing failures are not proof of success"
          description="NativeCaptureSink stores only stage and exception type in the failure journal. This page does not infer complete capture, workspace durability, event timestamps, or downstream acknowledgement from journal contents."
        />
        <CaptureHealthPanel />
      </Space>
    </AppShell>
  );
}
