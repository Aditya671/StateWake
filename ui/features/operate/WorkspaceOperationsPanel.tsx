"use client";

import { Alert, Button, Card, Descriptions, List, Skeleton, Space, Table, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";
import { StateIdentityCard, StateMetricCard, StateStatusCard } from "@/components/cards/StateWakeCards";
import { getWorkspaceOperations } from "@/lib/api/client";
import type { WorkspaceOperationsView, WorkspaceRecordView } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

const PAGE_SIZE = 50;

function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  const units = ["KiB", "MiB", "GiB", "TiB"];
  let amount = value / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && amount >= 1024; index += 1) {
    amount /= 1024;
    unit = units[index];
  }
  return `${amount.toFixed(amount >= 10 ? 1 : 2)} ${unit}`;
}

function retentionLabel(record: WorkspaceRecordView): string {
  if (record.retention === null) return "not recorded";
  return record.retention.legal_hold ? "legal hold" : record.retention.policy_id;
}

export function WorkspaceOperationsPanel() {
  const [data, setData] = useState<WorkspaceOperationsView | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((nextOffset: number) => {
    const controller = new AbortController();
    setLoading(true);
    getWorkspaceOperations(PAGE_SIZE, nextOffset, controller.signal)
      .then((value) => {
        setData(value);
        setOffset(value.records.offset);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(caught instanceof StateWakeApiError ? caught.message : "Workspace operations could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return controller;
  }, []);

  useEffect(() => {
    const controller = load(0);
    return () => controller.abort();
  }, [load]);

  if (loading && data === null) return <Skeleton active paragraph={{ rows: 9 }} />;
  if (error && data === null) return <Alert type="error" showIcon message="Workspace operations unavailable" description={`${error} No workspace state is inferred or repaired.`} />;
  if (!data) return null;

  return (
    <Space direction="vertical" size={18} style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        message="Read-only operational inspection"
        description="This view opens the existing SQLite workspace in read-only mode. It does not create locks, enable WAL, migrate, restore, delete, export, repair, or mutate workspace state."
      />
      {error ? <Alert type="warning" showIcon message="Page refresh failed" description={error} /> : null}

      <div className="sw-overview-grid">
        <StateStatusCard title="Workspace health" value={data.health.healthy ? "verified" : "not-verified"} eyebrow="Integrity">
          <Typography.Text type="secondary">{data.health.status} · {data.health.issues.length} issue(s)</Typography.Text>
        </StateStatusCard>
        <StateMetricCard label="Records" value={data.records.total_count} helper={`${data.health.checked_records} checked`} tone="info" />
        <StateMetricCard label="Workspace storage" value={bytes(data.storage.total_bytes)} helper={`${bytes(data.storage.database_bytes)} database`} />
        <StateMetricCard label="Legal holds" value={data.lifecycle.legal_holds_in_page} helper={`Current page of ${data.records.total_count} records`} tone={data.lifecycle.legal_holds_in_page ? "warning" : "neutral"} />
      </div>

      <div className="sw-grid">
        <StateIdentityCard label="Workspace ID" value={data.workspace.workspace_id} tag={`${data.workspace.backend} · ${data.workspace.mode}`} />
        <StateIdentityCard label="Workspace schema" value={data.workspace.schema_version} tag={`API ${data.workspace.public_api_contract_version}`} />
      </div>

      <div className="sw-grid">
        <Card className="sw-panel-card" bordered={false} title="Integrity accounting">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Receipts checked">{data.health.checked_receipts}</Descriptions.Item>
            <Descriptions.Item label="Artifacts checked">{data.health.checked_artifacts}</Descriptions.Item>
            <Descriptions.Item label="Exports checked">{data.health.checked_exports}</Descriptions.Item>
            <Descriptions.Item label="Orphan artifacts">{data.health.orphan_counts.artifacts}</Descriptions.Item>
            <Descriptions.Item label="Orphan receipts">{data.health.orphan_counts.receipts}</Descriptions.Item>
            <Descriptions.Item label="Orphan exports">{data.health.orphan_counts.exports}</Descriptions.Item>
          </Descriptions>
        </Card>
        <Card className="sw-panel-card" bordered={false} title="Lifecycle & migration">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Migration status">{data.migration.status}</Descriptions.Item>
            <Descriptions.Item label="Schema version">{data.migration.current_schema_version}</Descriptions.Item>
            <Descriptions.Item label="Retention rows">{data.lifecycle.retention_rows_in_snapshot}</Descriptions.Item>
            <Descriptions.Item label="Deletion tombstones">{data.lifecycle.deletion_tombstones}</Descriptions.Item>
            <Descriptions.Item label="Backup history">{data.backup.history_status}</Descriptions.Item>
            <Descriptions.Item label="Restore eligibility">{data.backup.restore_eligibility}</Descriptions.Item>
          </Descriptions>
        </Card>
      </div>

      {data.health.issues.length ? (
        <Card className="sw-panel-card" bordered={false} title="Integrity issues">
          <List
            size="small"
            dataSource={data.health.issues}
            renderItem={(item) => (
              <List.Item>
                <Space direction="vertical" size={2}>
                  <Typography.Text strong>{item.severity.toUpperCase()} · {item.code}</Typography.Text>
                  <Typography.Text>{item.message}</Typography.Text>
                  {item.object_id ? <Typography.Text type="secondary" className="mono">{item.object_id}</Typography.Text> : null}
                </Space>
              </List.Item>
            )}
          />
        </Card>
      ) : null}

      <Card
        className="sw-panel-card"
        bordered={false}
        title="Workspace records"
        extra={(
          <Space>
            <Button disabled={offset === 0 || loading} onClick={() => load(Math.max(0, offset - PAGE_SIZE))}>Previous</Button>
            <Button disabled={!data.records.has_more || loading} onClick={() => load(data.records.next_offset ?? offset)}>Next</Button>
          </Space>
        )}
      >
        <Typography.Paragraph type="secondary">
          Showing {data.records.items.length} record(s) from offset {data.records.offset}. Server paths and raw source references are intentionally omitted.
        </Typography.Paragraph>
        <Table
          rowKey={(row) => row.record_id}
          pagination={false}
          dataSource={data.records.items}
          scroll={{ x: 1350 }}
          columns={[
            { title: "Record", dataIndex: "record_id", render: (value: string) => <Typography.Text className="mono sw-machine">{value}</Typography.Text> },
            { title: "Producer", render: (_, row) => <span>{row.producer_id}<br/><Typography.Text type="secondary">{row.producer_type}</Typography.Text></span> },
            { title: "Captured", dataIndex: "captured_at" },
            { title: "Sensitivity", dataIndex: "sensitivity" },
            { title: "Verification", dataIndex: "verification_status", render: (value: string | null) => value ?? "not recorded" },
            { title: "Reliability", dataIndex: "reliability_state", render: (value: string | null) => value ?? "not recorded" },
            { title: "Retention", render: (_, row) => retentionLabel(row) },
            { title: "Artifact", dataIndex: "artifact_digest", render: (value: string) => <Typography.Text className="mono sw-machine">{value}</Typography.Text> },
          ]}
        />
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Recorded exports">
        <Typography.Paragraph type="secondary">Supported formats: {data.exports.supported_formats.join(", ")}. Output paths and raw query definitions are intentionally omitted.</Typography.Paragraph>
        <Table
          rowKey={(row) => row.export_id}
          pagination={false}
          dataSource={data.exports.items}
          scroll={{ x: 920 }}
          columns={[
            { title: "Export", dataIndex: "export_id", render: (value: string) => <Typography.Text className="mono sw-machine">{value}</Typography.Text> },
            { title: "Format", dataIndex: "format" },
            { title: "Created", dataIndex: "created_at" },
            { title: "Rows", dataIndex: "row_count", render: (value: number | null) => value ?? "not recorded" },
            { title: "Max sensitivity", dataIndex: "disclosure_max_sensitivity" },
            { title: "Digest", dataIndex: "output_digest", render: (value: string | null) => value ? <Typography.Text className="mono sw-machine">{value}</Typography.Text> : "not recorded" },
          ]}
        />
      </Card>

      <div className="sw-grid">
        <Card className="sw-panel-card" bordered={false} title="Backup / restore authority">
          <Typography.Paragraph>{data.backup.note}</Typography.Paragraph>
        </Card>
        <Card className="sw-panel-card" bordered={false} title="Operational audit authority">
          <Typography.Paragraph>{data.operational_audit.note}</Typography.Paragraph>
        </Card>
      </div>

      <Card className="sw-panel-card" bordered={false} title="Limitations">
        <List size="small" dataSource={data.limitations} renderItem={(item) => <List.Item>{item}</List.Item>} />
      </Card>
    </Space>
  );
}
