"use client";

import { Alert, Card, Descriptions, Empty, Skeleton, Space, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { getAssuranceDecision } from "@/lib/api/client";
import type { AssuranceDecisionView } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

function decisionTag(value: string) {
  const color = value === "ALLOW" ? "success" : value === "ALLOW_WITH_LIMITATIONS" ? "warning" : "error";
  return <Tag color={color}>{value}</Tag>;
}

export function AssuranceDecisionPanel() {
  const [view, setView] = useState<AssuranceDecisionView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getAssuranceDecision(controller.signal)
      .then(setView)
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load assurance decision evidence",
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
  }, []);

  if (loading) return <Skeleton active paragraph={{ rows: 10 }} />;
  if (error) {
    const unconfigured = error.code === "ASSURANCE_DECISION_SOURCE_NOT_CONFIGURED";
    return (
      <Alert
        type={unconfigured ? "warning" : "error"}
        showIcon
        message={unconfigured ? "Assurance decision evidence is not configured" : "Assurance decision evidence is unavailable"}
        description={error.message}
      />
    );
  }
  if (view === null) return <Empty description="No assurance decision view is available." />;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        message="A deterministic assurance decision is not a factual or business authorization decision"
        description="This view replays StateWake's bounded assurance policy and, when present, verifies an operational exception without rewriting the underlying assurance state."
      />

      <Card className="sw-card" size="small" title="Assurance decision">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Decision">{decisionTag(view.decision.decision)}</Descriptions.Item>
          <Descriptions.Item label="Policy">{view.decision.policy_id} · v{view.decision.policy_version}</Descriptions.Item>
          <Descriptions.Item label="Policy rule">{view.decision.policy_rule}</Descriptions.Item>
          <Descriptions.Item label="Generated at">{view.decision.generated_at}</Descriptions.Item>
          <Descriptions.Item label="Reliability state">{view.decision.source_reliability_state}</Descriptions.Item>
          <Descriptions.Item label="Verification status">{view.decision.source_verification_status}</Descriptions.Item>
          <Descriptions.Item label="Semantic replay">verified</Descriptions.Item>
          <Descriptions.Item label="System state changed">no</Descriptions.Item>
          <Descriptions.Item label="Decision digest" span={2}><span className="sw-machine">{view.decision.digest}</span></Descriptions.Item>
          <Descriptions.Item label="Subject identity" span={2}><span className="sw-machine">SHA-256 {view.decision.subject_id_digest}</span></Descriptions.Item>
        </Descriptions>
        {view.decision.residual_risk.length > 0 && (
          <Space wrap style={{ marginTop: 12 }}>
            <Typography.Text strong>Residual risk:</Typography.Text>
            {view.decision.residual_risk.map((item) => <Tag key={item}>{item}</Tag>)}
          </Space>
        )}
      </Card>

      <Card className="sw-card" size="small" title="Operational exception">
        {!view.exception.present ? (
          <Typography.Text type="secondary">No operational exception artifact is configured.</Typography.Text>
        ) : (
          <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Status"><Tag color={view.exception.status === "active" ? "warning" : "default"}>{view.exception.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="Binding">{view.exception.binding}</Descriptions.Item>
            <Descriptions.Item label="Created">{view.exception.created_at}</Descriptions.Item>
            <Descriptions.Item label="Expires">{view.exception.expires_at}</Descriptions.Item>
            <Descriptions.Item label="Compensating control">{view.exception.compensating_control}</Descriptions.Item>
            <Descriptions.Item label="Reverification">{view.exception.reverification_required}</Descriptions.Item>
            <Descriptions.Item label="Underlying state preserved">yes</Descriptions.Item>
            <Descriptions.Item label="Authorizer identity"><span className="sw-machine">SHA-256 {view.exception.authorized_by_digest}</span></Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      {view.limitations.map((item) => <Alert key={item} type="info" showIcon message={item} />)}
    </Space>
  );
}
