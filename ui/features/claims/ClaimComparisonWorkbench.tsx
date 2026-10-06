"use client";

import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Row,
  Skeleton,
  Space,
  Typography,
} from "antd";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StateFacet } from "@/components/StateFacet";
import { StateIdentityCard, StateStatusCard } from "@/components/cards/StateWakeCards";
import { getClaimComparison } from "@/lib/api/client";
import type { ClaimComparison, StringDelta } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

const RECORD_ID = /^[0-9a-f]{64}$/;

function Delta({ label, value }: { label: string; value: StringDelta }) {
  if (value.added.length === 0 && value.removed.length === 0) return null;
  return (
    <Card size="small" title={label} className="sw-card">
      <Row gutter={[16, 8]}>
        <Col xs={24} md={12}>
          <Typography.Text strong>Added</Typography.Text>
          {value.added.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="None" />
          ) : (
            <List size="small" dataSource={value.added} renderItem={(item) => <List.Item>{item}</List.Item>} />
          )}
        </Col>
        <Col xs={24} md={12}>
          <Typography.Text strong>Removed</Typography.Text>
          {value.removed.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="None" />
          ) : (
            <List size="small" dataSource={value.removed} renderItem={(item) => <List.Item>{item}</List.Item>} />
          )}
        </Col>
      </Row>
    </Card>
  );
}

export function ClaimComparisonWorkbench({
  initialLeft,
  initialRight,
}: {
  initialLeft: string;
  initialRight: string;
}) {
  const router = useRouter();
  const valid = RECORD_ID.test(initialLeft) && RECORD_ID.test(initialRight);
  const [comparison, setComparison] = useState<ClaimComparison | null>(null);
  const [error, setError] = useState<StateWakeApiError | null>(null);
  const [loading, setLoading] = useState(valid);

  useEffect(() => {
    if (!valid) return;
    const controller = new AbortController();
    setLoading(true);
    getClaimComparison(initialLeft, initialRight, controller.signal)
      .then((value) => {
        setComparison(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to compare reports",
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
  }, [initialLeft, initialRight, valid]);

  return (
    <AppShell>
      <Space direction="vertical" size={18} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">History & versions</div>
          <Typography.Title style={{ margin: "4px 0 8px" }}>
            Candidate comparison
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ maxWidth: 820 }}>
            Compare two exact canonical report records. The view reports recorded differences only; it does not infer why bytes changed or assign a severity score.
          </Typography.Paragraph>
        </div>
        <CompareForm left={initialLeft} right={initialRight} />
        {!valid && (
          <Alert
            type="info"
            showIcon
            message="Enter two report receipt IDs"
            description="Both values must be lowercase 64-character receipt identities."
          />
        )}
        {loading && <Skeleton active paragraph={{ rows: 10 }} />}
        {error && (
          <Alert
            type="error"
            showIcon
            message="Comparison unavailable"
            description={`${error.code}: ${error.message}`}
          />
        )}
        {comparison && <ComparisonResult comparison={comparison} router={router} />}
      </Space>
    </AppShell>
  );
}

function CompareForm({ left, right }: { left: string; right: string }) {
  const router = useRouter();
  return (
    <Card className="sw-card" size="small">
      <Form<{ left: string; right: string }>
        layout="vertical"
        initialValues={{ left, right }}
        onFinish={(values) => {
          router.push(
            `/compare?left=${encodeURIComponent(values.left.trim())}&right=${encodeURIComponent(values.right.trim())}`,
          );
        }}
      >
        <Row gutter={16}>
          {(["left", "right"] as const).map((name) => (
            <Col xs={24} lg={12} key={name}>
              <Form.Item
                label={`${name === "left" ? "Left" : "Right"} report receipt ID`}
                name={name}
                rules={[
                  { required: true, message: "Enter a report receipt ID" },
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
            </Col>
          ))}
        </Row>
        <Button type="primary" htmlType="submit">
          Compare exact reports
        </Button>
      </Form>
    </Card>
  );
}

function ComparisonResult({
  comparison,
  router,
}: {
  comparison: ClaimComparison;
  router: ReturnType<typeof useRouter>;
}) {
  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {!comparison.semantic_scope_same && (
        <Alert
          type="warning"
          showIcon
          message="Reports are not semantically equivalent"
          description={`Comparison is descriptive only: ${comparison.non_equivalence_warnings.join(", ")}.`}
        />
      )}
      <Row gutter={[16, 16]}>
        {([comparison.left, comparison.right] as const).map((side, index) => (
          <Col xs={24} lg={12} key={side.record_id}>
            <Card
              className="sw-panel-card"
              title={index === 0 ? "Left report" : "Right report"}
              extra={
                <Button type="link" onClick={() => router.push(`/claims/${side.record_id}`)}>
                  Open
                </Button>
              }
            >
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <div className="sw-grid">
                  <StateStatusCard
                    title="Verification"
                    value={side.verified ? "verified" : "not-verified"}
                    eyebrow={index === 0 ? "Left" : "Right"}
                  />
                  <StateStatusCard
                    title="Decision"
                    value={side.decision}
                    description={`Human decision: ${side.approval_status}`}
                    eyebrow="Claim profile"
                  />
                </div>
                <StateIdentityCard
                  label="Candidate digest"
                  value={side.candidate.digest}
                  tag={`${side.profile.id}@${side.profile.version}`}
                />
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="Report digest">
                    <span className="mono sw-machine">{side.report_digest}</span>
                  </Descriptions.Item>
                  <Descriptions.Item label="Generated at">{side.generated_at}</Descriptions.Item>
                  <Descriptions.Item label="Captured at">{side.captured_at}</Descriptions.Item>
                </Descriptions>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
      <Card className="sw-panel-card" title="Recorded state changes">
        <Descriptions column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Candidate bytes changed">
            {comparison.changes.candidate_digest_changed ? "Yes" : "No"}
          </Descriptions.Item>
          <Descriptions.Item label="Claim decision">
            {comparison.changes.decision.before} → {comparison.changes.decision.after}
          </Descriptions.Item>
          <Descriptions.Item label="Verification">
            {String(comparison.changes.verified.before)} → {String(comparison.changes.verified.after)}
          </Descriptions.Item>
          <Descriptions.Item label="Approval status">
            {comparison.changes.approval_status.before} → {comparison.changes.approval_status.after}
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Delta label="Passed checks" value={comparison.changes.checks.passed} />
      <Delta label="Failed checks" value={comparison.changes.checks.failed} />
      <Delta label="Unrun checks" value={comparison.changes.checks.unrun} />
      <Delta label="Unknown checks" value={comparison.changes.checks.unknown} />
      <Delta label="Included evidence" value={comparison.changes.evidence.included} />
      <Delta label="Missing evidence" value={comparison.changes.evidence.missing} />
      <Delta label="Omitted evidence" value={comparison.changes.evidence.omitted} />
      <Delta label="Caveats" value={comparison.changes.caveats} />
      <Delta label="Residual risks" value={comparison.changes.residual_risks} />
      <Delta
        label="Human decisions required"
        value={comparison.changes.human_decisions_required}
      />
      <Alert
        type="info"
        showIcon
        message="Comparison limitations"
        description={comparison.limitations.join(" ")}
      />
    </Space>
  );
}
