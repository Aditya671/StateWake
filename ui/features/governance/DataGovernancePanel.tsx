"use client";

import { Alert, Card, Col, Descriptions, Empty, Row, Skeleton, Space, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { getDataGovernance } from "@/lib/api/client";
import type { DataGovernanceView, DataLifecycleDecisionView } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

function decisionTag(value: boolean, positive: string, negative: string) {
  return value ? <Tag color="success">{positive}</Tag> : <Tag>{negative}</Tag>;
}

function LifecycleDecisionCard({
  title,
  decision,
}: {
  title: string;
  decision: DataLifecycleDecisionView;
}) {
  return (
    <Card className="sw-card" size="small" title={title}>
      <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
        <Descriptions.Item label="Sensitivity">{decision.sensitivity}</Descriptions.Item>
        <Descriptions.Item label="Policy">{decision.policy_id}</Descriptions.Item>
        <Descriptions.Item label="Retention deadline">{decision.retain_until ?? "no maximum retention"}</Descriptions.Item>
        <Descriptions.Item label="Expired">{decisionTag(decision.expired, "yes", "no")}</Descriptions.Item>
        <Descriptions.Item label="Storage">{decisionTag(decision.storage_allowed, "allowed", "blocked")}</Descriptions.Item>
        <Descriptions.Item label="Telemetry">{decisionTag(decision.telemetry_allowed, "allowed", "excluded")}</Descriptions.Item>
        <Descriptions.Item label="Disclosure">{decisionTag(decision.disclosure_allowed, "allowed", "blocked")}</Descriptions.Item>
        <Descriptions.Item label="Deletion eligibility">{decisionTag(decision.deletion_allowed, "eligible", "not eligible")}</Descriptions.Item>
      </Descriptions>
      {decision.reasons.length > 0 ? (
        <Space direction="vertical" size={4} style={{ marginTop: 12 }}>
          <Typography.Text strong>Decision reasons</Typography.Text>
          {decision.reasons.map((reason) => (
            <Typography.Text key={reason} type="secondary">• {reason}</Typography.Text>
          ))}
        </Space>
      ) : null}
    </Card>
  );
}

export function DataGovernancePanel() {
  const [view, setView] = useState<DataGovernanceView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getDataGovernance(controller.signal)
      .then((value) => {
        setView(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load data governance context",
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

  if (loading) return <Skeleton active paragraph={{ rows: 14 }} />;
  if (error) {
    const unconfigured = error.code === "DATA_GOVERNANCE_SOURCE_NOT_CONFIGURED";
    const oversized = error.code === "DATA_GOVERNANCE_SOURCE_TOO_LARGE";
    return (
      <Alert
        type={unconfigured ? "warning" : "error"}
        showIcon
        message={
          unconfigured
            ? "Data lifecycle context is not configured"
            : oversized
              ? "Lifecycle context exceeds the configured read boundary"
              : "Lifecycle policy context could not be verified against workspace state"
        }
        description={error.message}
      />
    );
  }
  if (view === null) return <Empty description="No data-governance investigation is available." />;

  const current = view.current_decision;
  const deletion = view.deletion;
  const lifecycleMessage = view.durable_retention.legal_hold
    ? "Legal hold is active; retention expiry does not permit deletion."
    : deletion.present
      ? "A payload-free deletion tombstone is recorded for this workspace object."
      : current.deletion_allowed
        ? "The recorded lifecycle policy currently makes this object eligible for deletion, but this read-only view does not perform deletion."
        : "The object is not currently eligible for deletion under the recorded lifecycle policy.";

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Alert
        type={view.durable_retention.legal_hold ? "warning" : deletion.present ? "info" : current.deletion_allowed ? "warning" : "info"}
        showIcon
        message={lifecycleMessage}
        description="Storage, telemetry, disclosure, retention expiry, legal hold, and deletion eligibility remain independent lifecycle facts."
      />

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card className="sw-card" size="small" title="Governed workspace object">
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="Object kind">{view.object.kind}</Descriptions.Item>
              <Descriptions.Item label="Object identity"><span className="sw-machine">SHA-256 {view.object.object_id_digest}</span></Descriptions.Item>
              <Descriptions.Item label="Sensitivity">{view.object.sensitivity}</Descriptions.Item>
              <Descriptions.Item label="Created">{view.object.created_at}</Descriptions.Item>
              <Descriptions.Item label="Original digest">{view.object.original_digest ? <span className="sw-machine">{view.object.original_digest}</span> : "not recorded"}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="sw-card" size="small" title="Lifecycle policy">
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="Policy ID">{view.policy.policy_id}</Descriptions.Item>
              <Descriptions.Item label="Purpose">{view.policy.purpose}</Descriptions.Item>
              <Descriptions.Item label="Maximum retention">{view.policy.max_retention_days === null ? "unbounded" : `${view.policy.max_retention_days} day(s)`}</Descriptions.Item>
              <Descriptions.Item label="Storage ceiling">{view.policy.storage_max_sensitivity}</Descriptions.Item>
              <Descriptions.Item label="Telemetry ceiling">{view.policy.telemetry_max_sensitivity}</Descriptions.Item>
              <Descriptions.Item label="Disclosure ceiling">{view.policy.disclosure_max_sensitivity}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      <Card className="sw-card" size="small" title="Runtime privacy & evidence governance">
        {view.privacy_governance_runtime.observed ? (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Alert
              type="success"
              showIcon
              message="A digest-verified runtime policy snapshot was observed"
              description="The snapshot proves the policy configuration recorded by the runtime integration. It does not prove process liveness or that every external telemetry exporter is bound to the same configuration."
            />
            <Descriptions bordered size="small" column={{ xs: 1, lg: 2 }}>
              <Descriptions.Item label="Snapshot digest"><span className="sw-machine">{view.privacy_governance_runtime.snapshot_digest}</span></Descriptions.Item>
              <Descriptions.Item label="Metadata privacy policy">{view.privacy_governance_runtime.privacy_policy.policy_id}</Descriptions.Item>
              <Descriptions.Item label="Redacted metadata keys">{view.privacy_governance_runtime.privacy_policy.redact_key_count}</Descriptions.Item>
              <Descriptions.Item label="Regex redaction rules">{view.privacy_governance_runtime.privacy_policy.regex_rule_count}</Descriptions.Item>
              <Descriptions.Item label="Evidence governance policy">{view.privacy_governance_runtime.evidence_policy.policy_id}</Descriptions.Item>
              <Descriptions.Item label="Storage ceiling">{view.privacy_governance_runtime.evidence_policy.storage_max_sensitivity}</Descriptions.Item>
              <Descriptions.Item label="Telemetry ceiling">{view.privacy_governance_runtime.evidence_policy.telemetry_max_sensitivity}</Descriptions.Item>
              <Descriptions.Item label="Digest-required sensitivities">{view.privacy_governance_runtime.evidence_policy.require_digest_for.join(", ") || "none"}</Descriptions.Item>
              <Descriptions.Item label="Metadata redaction before receipt identity"><Tag color="success">enforced</Tag></Descriptions.Item>
              <Descriptions.Item label="Storage governance before artifact write"><Tag color="success">enforced</Tag></Descriptions.Item>
              <Descriptions.Item label="Workspace sensitivity indexing"><Tag color="success">enforced</Tag></Descriptions.Item>
              <Descriptions.Item label="Telemetry manifest filtering"><Tag color="processing">supported</Tag></Descriptions.Item>
              <Descriptions.Item label="Live telemetry binding observed"><Tag>no</Tag></Descriptions.Item>
              <Descriptions.Item label="Opaque content secret scanning"><Tag>not performed</Tag></Descriptions.Item>
            </Descriptions>
          </Space>
        ) : (
          <Alert
            type="warning"
            showIcon
            message="Runtime privacy/evidence-governance configuration was not observed"
            description="StateWake does not substitute repository defaults or infer active redaction/storage policy when no runtime snapshot is configured."
          />
        )}
      </Card>

      <Card className="sw-card" size="small" title="Durable retention authority">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Policy cross-check">verified</Descriptions.Item>
          <Descriptions.Item label="Sensitivity">{view.durable_retention.sensitivity}</Descriptions.Item>
          <Descriptions.Item label="Retain until">{view.durable_retention.retain_until ?? "no maximum retention"}</Descriptions.Item>
          <Descriptions.Item label="Legal hold">{view.durable_retention.legal_hold ? <Tag color="warning">active</Tag> : <Tag>not active</Tag>}</Descriptions.Item>
        </Descriptions>
      </Card>

      <LifecycleDecisionCard title="Current deterministic lifecycle decision" decision={current} />

      {view.recorded_decision.present ? (
        <Card className="sw-card" size="small" title="Recorded lifecycle decision">
          <Typography.Paragraph type="secondary">
            Recorded at {view.recorded_decision.evaluated_at}. The server replayed the same policy and verified this persisted decision exactly.
          </Typography.Paragraph>
          <LifecycleDecisionCard title="Recorded decision details" decision={view.recorded_decision.decision} />
        </Card>
      ) : (
        <Alert type="info" showIcon message="No persisted lifecycle decision was supplied" description="The current decision is still deterministically replayed from the configured policy and durable workspace retention state." />
      )}

      <Card className="sw-card" size="small" title="Deletion history">
        {deletion.present ? (
          <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Tombstone">verified</Descriptions.Item>
            <Descriptions.Item label="Deleted at">{deletion.deleted_at}</Descriptions.Item>
            <Descriptions.Item label="Policy">{deletion.policy_id}</Descriptions.Item>
            <Descriptions.Item label="Sensitivity">{deletion.sensitivity}</Descriptions.Item>
            <Descriptions.Item label="Original digest"><span className="sw-machine">{deletion.digest}</span></Descriptions.Item>
            <Descriptions.Item label="Reason">{deletion.reason}</Descriptions.Item>
            <Descriptions.Item label="Payload retained in tombstone">no</Descriptions.Item>
            <Descriptions.Item label="External-copy erasure evaluated">no</Descriptions.Item>
          </Descriptions>
        ) : (
          <Typography.Text type="secondary">No deletion tombstone is recorded for this object.</Typography.Text>
        )}
      </Card>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card className="sw-card" size="small" title="Confidentiality requirements">
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="Encryption at rest">{view.confidentiality_requirements.encryption_at_rest_required ? "required" : "not required by this policy"}</Descriptions.Item>
              <Descriptions.Item label="TLS">{view.confidentiality_requirements.tls_required ? "required" : "not required by this policy"}</Descriptions.Item>
              <Descriptions.Item label="Host satisfaction verified">no</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="sw-card" size="small" title="Read-only authority boundary">
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="Deletion performed">no</Descriptions.Item>
              <Descriptions.Item label="Disclosure performed">no</Descriptions.Item>
              <Descriptions.Item label="Business authorization inferred">no</Descriptions.Item>
              <Descriptions.Item label="Compliance certified">no</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      {view.limitations.map((item) => <Alert key={item} type="info" showIcon message={item} />)}
    </Space>
  );
}
