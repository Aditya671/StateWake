"use client";

import {
  Alert,
  Card,
  Descriptions,
  Empty,
  List,
  Skeleton,
  Space,
  Table,
  Tag,
  Timeline,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { getIncidentDetail } from "@/lib/api/client";
import type {
  IncidentDetail,
  IncidentEvidenceReferenceView,
} from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

function statusTag(status: string) {
  const color = status === "reverified" ? "success" : status === "recovered" ? "processing" : "warning";
  return <Tag color={color}>{status}</Tag>;
}

export function IncidentDetailPanel({ incidentId }: { incidentId: string }) {
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    getIncidentDetail(incidentId, controller.signal)
      .then((value) => {
        setDetail(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setDetail(null);
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load incident detail",
                "unexpected",
                "CLIENT_ERROR",
                null,
                false,
              ),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [incidentId]);

  const evidenceColumns = useMemo<ColumnsType<IncidentEvidenceReferenceView>>(
    () => [
      { title: "Kind", dataIndex: "kind", key: "kind", width: 150 },
      {
        title: "Identity",
        dataIndex: "identity",
        key: "identity",
        render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text>,
      },
      {
        title: "Digest",
        dataIndex: "digest",
        key: "digest",
        render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text>,
      },
      {
        title: "Source",
        dataIndex: "source_recorded",
        key: "source_recorded",
        width: 120,
        render: (value: boolean) => (value ? "recorded" : "not recorded"),
      },
    ],
    [],
  );

  if (loading) return <Skeleton active paragraph={{ rows: 10 }} />;
  if (error) {
    return (
      <Alert
        type={error.category === "not-found" ? "warning" : "error"}
        showIcon
        message="Incident detail is unavailable"
        description={error.message}
      />
    );
  }
  if (!detail) return <Empty description="No incident detail is available." />;

  const incident = detail.incident;
  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card className="sw-card" size="small">
        <Space direction="vertical" size={10} style={{ width: "100%" }}>
          <Space wrap>
            {statusTag(incident.status)}
            {incident.recovery.recorded && <Tag>recovery {incident.recovery.status}</Tag>}
            {detail.forensic_continuity.verified && <Tag color="success">forensic continuity verified</Tag>}
          </Space>
          <Typography.Title level={3} style={{ margin: 0 }}>{incident.category}</Typography.Title>
          <Typography.Text className="sw-machine">{incident.incident_id}</Typography.Text>
        </Space>
      </Card>

      <Card className="sw-card" size="small" title="Recorded incident context">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Event ID">{incident.event_id}</Descriptions.Item>
          <Descriptions.Item label="Actor">{incident.actor}</Descriptions.Item>
          <Descriptions.Item label="Detected at">{incident.detected_at}</Descriptions.Item>
          <Descriptions.Item label="Latest observation">{incident.latest_recorded_at}</Descriptions.Item>
          <Descriptions.Item label="Evidence references">{incident.evidence_ref_count}</Descriptions.Item>
          <Descriptions.Item label="Affected states">{incident.affected_state_count}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="sw-card" size="small" title="Lifecycle observations">
        <Timeline
          items={detail.lifecycle.map((item) => ({
            children: (
              <Space direction="vertical" size={2}>
                <Space wrap>{statusTag(item.status)}<Typography.Text>{item.recorded_at}</Typography.Text></Space>
                <Typography.Text type="secondary" className="sw-machine">record {item.sequence} · {item.record_digest}</Typography.Text>
              </Space>
            ),
          }))}
        />
        <Alert
          type="info"
          showIcon
          message="Timeline observations do not establish causality"
          description="The store records when StateWake preserved lifecycle observations. Status progression and timestamps do not prove why the incident occurred."
        />
      </Card>

      <Card className="sw-card" size="small" title="Preserved evidence references">
        <Table<IncidentEvidenceReferenceView>
          rowKey={(item) => `${item.kind}:${item.identity}:${item.digest}`}
          columns={evidenceColumns}
          dataSource={detail.evidence_refs}
          pagination={false}
          size="small"
          scroll={{ x: 800 }}
        />
      </Card>

      <Card className="sw-card" size="small" title="Recovery and post-recovery verification">
        {detail.recovery === null ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No recovery evidence is recorded." />
        ) : (
          <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Recovery ID">{detail.recovery.recovery_id}</Descriptions.Item>
            <Descriptions.Item label="Recovery status">{detail.recovery.status}</Descriptions.Item>
            <Descriptions.Item label="Recovery actor">{detail.recovery.actor}</Descriptions.Item>
            <Descriptions.Item label="Post-recovery verification">
              {detail.post_recovery === null ? "not recorded" : detail.post_recovery.status}
            </Descriptions.Item>
            {detail.post_recovery !== null && (
              <Descriptions.Item label="Verification performed at" span={2}>
                {detail.post_recovery.performed_at}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
        <Alert
          style={{ marginTop: 12 }}
          type={detail.forensic_continuity.verified ? "success" : "warning"}
          showIcon
          message={
            detail.forensic_continuity.verified
              ? "Recorded forensic-continuity relationships verify"
              : incident.status === "recovered"
                ? "Recovery is recorded, but post-recovery reverification is not complete"
                : "Forensic-continuity verification is not yet applicable"
          }
        />
      </Card>

      <Card className="sw-card" size="small" title="Affected trust state">
        {detail.affected_states.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No affected trust state is recorded." />
        ) : (
          <List
            dataSource={detail.affected_states}
            renderItem={(item) => (
              <List.Item>
                <Descriptions size="small" column={1} style={{ width: "100%" }}>
                  <Descriptions.Item label="State ID">{item.state_id}</Descriptions.Item>
                  <Descriptions.Item label="State digest"><span className="sw-machine">{item.state_digest}</span></Descriptions.Item>
                  <Descriptions.Item label="Trust context">{item.trust_context}</Descriptions.Item>
                  <Descriptions.Item label="Affected window">
                    {item.affected_window_start === null
                      ? "not recorded"
                      : `${item.affected_window_start} → ${item.affected_window_end}`}
                  </Descriptions.Item>
                </Descriptions>
              </List.Item>
            )}
          />
        )}
      </Card>

      {detail.key_compromise !== null && (
        <Card className="sw-card" size="small" title="Recorded key-compromise scope">
          <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Key identity">{detail.key_compromise.key_identity}</Descriptions.Item>
            <Descriptions.Item label="Affected version">{detail.key_compromise.affected_key_version}</Descriptions.Item>
            <Descriptions.Item label="Exposure start">{detail.key_compromise.exposure_start}</Descriptions.Item>
            <Descriptions.Item label="Exposure end">{detail.key_compromise.exposure_end ?? "open / not recorded"}</Descriptions.Item>
            <Descriptions.Item label="Affected attestations" span={2}>
              {detail.key_compromise.affected_attestation_ids.join(", ") || "none recorded"}
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      <Card className="sw-card" size="small" title="Residual uncertainty">
        {detail.uncertainty.length === 0 ? (
          <Typography.Text type="secondary">No uncertainty entries are recorded.</Typography.Text>
        ) : (
          <List dataSource={detail.uncertainty} renderItem={(item) => <List.Item>{item}</List.Item>} />
        )}
      </Card>

      {detail.limitations.map((item) => (
        <Alert key={item} type="info" showIcon message={item} />
      ))}
    </Space>
  );
}
