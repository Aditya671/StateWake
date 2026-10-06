"use client";

import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  Skeleton,
  Space,
  Timeline,
  Typography,
} from "antd";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getClaimHistory } from "@/lib/api/client";
import type { ClaimHistory } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";
import { StateFacet } from "@/components/StateFacet";
import { StateIdentityCard, StateMetricCard } from "@/components/cards/StateWakeCards";

const RECORD_ID = /^[0-9a-f]{64}$/;

export function ClaimHistoryPanel({
  recordId,
  active,
}: {
  recordId: string;
  active: boolean;
}) {
  const router = useRouter();
  const [history, setHistory] = useState<ClaimHistory | null>(null);
  const [error, setError] = useState<StateWakeApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const [attempted, setAttempted] = useState(false);

  useEffect(() => {
    if (!active || attempted) return;
    const controller = new AbortController();
    setAttempted(true);
    setLoading(true);
    getClaimHistory(recordId, controller.signal)
      .then((value) => {
        setHistory(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load recorded history",
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
  }, [active, attempted, recordId]);

  if (loading) return <Skeleton active paragraph={{ rows: 6 }} />;
  if (error?.code === "HISTORY_NOT_CONFIGURED") {
    return (
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          message="Reliability-state history is not configured"
          description="StateWake is not inferring a timeline from report timestamps. Configure an existing authoritative reliability-state history file to enable this read-only view."
        />
        <CompareCard recordId={recordId} />
      </Space>
    );
  }
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="Recorded history could not be verified"
        description={`${error.code}: ${error.message}`}
      />
    );
  }
  if (!history) {
    return active ? <Empty description="No history response returned" /> : null;
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <div className="sw-summary-grid">
        <StateMetricCard
          label="Recorded transitions"
          value={history.recorded_count}
          helper="Exact candidate identity + digest matches only"
          tone={history.recorded_count > 0 ? "info" : "neutral"}
        />
        <StateMetricCard
          label="Timeline items shown"
          value={history.items.length}
          helper="Authoritative recorded transitions; no inferred events"
          tone={history.items.length > 0 ? "success" : "neutral"}
        />
        <StateIdentityCard label="Candidate" value={history.candidate.id} />
        <StateIdentityCard
          label="Profile"
          value={`${history.profile.id}@${history.profile.version}`}
        />
      </div>
      <Alert
        type="info"
        showIcon
        message="Candidate-bound recorded history"
        description="Only transitions whose recorded evidence-chain identity and digest match this exact report candidate are shown."
      />
      {history.items.length === 0 ? (
        <Empty description="No matching reliability-state transitions were recorded in the configured history" />
      ) : (
        <Timeline
          items={history.items.map((item) => ({
            children: (
              <Card size="small" className="sw-panel-card">
                <Space direction="vertical" size={8} style={{ width: "100%" }}>
                  <Space wrap>
                    <StateFacet value={item.decision} />
                    <Typography.Text strong>
                      {item.from_state} → {item.to_state}
                    </Typography.Text>
                  </Space>
                  <Descriptions size="small" column={{ xs: 1, md: 2 }}>
                    <Descriptions.Item label="Occurred at">
                      {item.occurred_at}
                    </Descriptions.Item>
                    <Descriptions.Item label="Actor">
                      <span className="mono sw-machine">{item.actor}</span>
                    </Descriptions.Item>
                    <Descriptions.Item label="Subject">
                      <span className="mono sw-machine">{item.subject_id}</span>
                    </Descriptions.Item>
                    <Descriptions.Item label="Transition digest">
                      <span className="mono sw-machine">{item.transition_digest}</span>
                    </Descriptions.Item>
                  </Descriptions>
                  {item.rationale.length > 0 && (
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      {item.rationale.join(" · ")}
                    </Typography.Paragraph>
                  )}
                </Space>
              </Card>
            ),
          }))}
        />
      )}
      <Alert
        type="warning"
        showIcon
        message="Timeline limitations"
        description={history.limitations.join(" ")}
      />
      <CompareCard recordId={recordId} />
    </Space>
  );
}

function CompareCard({ recordId }: { recordId: string }) {
  const router = useRouter();
  return (
    <Card size="small" title="Compare with another report" className="sw-card">
      <Typography.Paragraph type="secondary">
        Comparison is direct by two durable report receipt IDs. StateWake does not scan the workspace or choose a “latest” candidate on your behalf.
      </Typography.Paragraph>
      <Form<{ otherRecordId: string }>
        layout="vertical"
        onFinish={({ otherRecordId }) => {
          router.push(
            `/compare?left=${encodeURIComponent(recordId)}&right=${encodeURIComponent(otherRecordId.trim())}`,
          );
        }}
      >
        <Form.Item
          label="Other report receipt ID"
          name="otherRecordId"
          rules={[
            { required: true, message: "Enter another report receipt ID" },
            {
              validator: (_, value: string | undefined) =>
                value && RECORD_ID.test(value.trim())
                  ? Promise.resolve()
                  : Promise.reject(
                      new Error("Use a lowercase 64-character SHA-256 receipt identity"),
                    ),
            },
          ]}
        >
          <Input className="mono" autoComplete="off" spellCheck={false} />
        </Form.Item>
        <Button type="primary" htmlType="submit">
          Compare reports
        </Button>
      </Form>
    </Card>
  );
}
