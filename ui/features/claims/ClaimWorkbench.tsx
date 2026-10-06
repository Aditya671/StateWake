"use client";

import {
  Alert,
  Card,
  Col,
  Descriptions,
  Empty,
  List,
  Row,
  Skeleton,
  Space,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { StateFacet } from "@/components/StateFacet";
import {
  StateChecklistCard,
  StateIdentityCard,
  StateMetricCard,
  StateStatusCard,
} from "@/components/cards/StateWakeCards";
import { ClaimHistoryPanel } from "@/features/claims/ClaimHistoryPanel";
import { EvidenceTracePanel } from "@/features/claims/EvidenceTracePanel";
import { ReviewBoundaryPanel } from "@/features/claims/ReviewBoundaryPanel";
import {
  getCanonicalJson,
  getCanonicalMarkdown,
  getClaimDetail,
} from "@/lib/api/client";
import type { ClaimDetail } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

function TextList({ values, empty }: { values: string[]; empty: string }) {
  if (values.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty} />;
  }
  return (
    <List
      size="small"
      dataSource={values}
      renderItem={(value) => (
        <List.Item>
          <span className="sw-machine">{value}</span>
        </List.Item>
      )}
    />
  );
}


function RawDocument({
  value,
  loading,
  error,
}: {
  value: string | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <Skeleton active />;
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="Canonical document unavailable"
        description={error}
      />
    );
  }
  if (value === null) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  return <pre className="sw-raw">{value}</pre>;
}

const TAB_KEYS = new Set([
  "summary",
  "checks",
  "evidence",
  "history",
  "reviews",
  "json",
  "report",
]);

export function ClaimWorkbench({ recordId }: { recordId: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const activeTab =
    requestedTab && TAB_KEYS.has(requestedTab) ? requestedTab : "summary";
  const [detail, setDetail] = useState<ClaimDetail | null>(null);
  const [error, setError] = useState<StateWakeApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [json, setJson] = useState<string | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [documentError, setDocumentError] = useState<string | null>(null);
  const [documentLoading, setDocumentLoading] = useState<"json" | "markdown" | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    getClaimDetail(recordId, controller.signal)
      .then((value) => {
        setDetail(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load claim detail",
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
  }, [recordId]);

  const tabs = useMemo(() => {
    if (!detail) return [];
    return [
      {
        key: "summary",
        label: "Summary",
        children: (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <div className="sw-overview-grid">
              <StateStatusCard
                title="Verification"
                value={detail.summary.verification.verified ? "verified" : "not-verified"}
                description="Recorded verification state from the canonical report."
                eyebrow="Machine verification"
              />
              <StateStatusCard
                title="Claim decision"
                value={detail.summary.decision}
                description="Bounded claim-profile decision; not a human approval."
                eyebrow="Profile result"
              />
              <StateStatusCard
                title="Human decision"
                value={detail.summary.human_decision.approval_status}
                description="Recorded human-decision boundary in this immutable report."
                eyebrow="Approval state"
              />
              <StateIdentityCard
                label="Candidate identity"
                value={detail.summary.candidate.id}
                tag={`${detail.summary.profile.id}@${detail.summary.profile.version}`}
              />
            </div>
            <div className="sw-summary-grid">
              <StateMetricCard
                label="Checks passed"
                value={detail.summary.verification.passed}
                helper="Recorded passed checks"
                tone="success"
              />
              <StateMetricCard
                label="Checks failed"
                value={detail.summary.verification.failed}
                helper="Recorded failed checks"
                tone={detail.summary.verification.failed > 0 ? "danger" : "neutral"}
              />
              <StateMetricCard
                label="Unrun / unknown"
                value={
                  detail.summary.verification.unrun +
                  detail.summary.verification.unknown
                }
                helper="Checks without a completed known result"
                tone={
                  detail.summary.verification.unrun + detail.summary.verification.unknown > 0
                    ? "warning"
                    : "neutral"
                }
              />
              <StateMetricCard
                label="Missing / omitted evidence"
                value={detail.summary.evidence.missing + detail.summary.evidence.omitted}
                helper="Evidence entries recorded missing or intentionally omitted"
                tone={
                  detail.summary.evidence.missing + detail.summary.evidence.omitted > 0
                    ? "danger"
                    : "neutral"
                }
              />
            </div>
            <StateChecklistCard
              title="Verification boundary"
              items={[
                {
                  label: `${detail.summary.verification.passed} checks passed`,
                  state: detail.summary.verification.passed > 0 ? "success" : "neutral",
                },
                {
                  label:
                    detail.summary.verification.failed > 0
                      ? `${detail.summary.verification.failed} checks failed`
                      : "No failed checks recorded",
                  state: detail.summary.verification.failed > 0 ? "danger" : "success",
                },
                {
                  label:
                    detail.summary.evidence.missing > 0
                      ? `${detail.summary.evidence.missing} evidence entries missing`
                      : "No missing evidence entries recorded",
                  state: detail.summary.evidence.missing > 0 ? "danger" : "success",
                },
                {
                  label:
                    detail.summary.human_decision.required_actions.length > 0
                      ? `${detail.summary.human_decision.required_actions.length} human action(s) required`
                      : "No human action recorded as required",
                  state:
                    detail.summary.human_decision.required_actions.length > 0
                      ? "warning"
                      : "neutral",
                },
              ]}
            />
            <div className="sw-grid">
              <Card size="small" title="What StateWake evaluated" className="sw-card">
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="Claim">
                    {detail.summary.claim}
                  </Descriptions.Item>
                  <Descriptions.Item label="Profile">
                    <span className="mono">
                      {detail.summary.profile.id}@{detail.summary.profile.version}
                    </span>
                  </Descriptions.Item>
                  <Descriptions.Item label="Candidate">
                    <span className="mono sw-machine">
                      {detail.summary.candidate.id}
                    </span>
                  </Descriptions.Item>
                </Descriptions>
              </Card>
              <Card
                size="small"
                title="What prevented stronger verification"
                className="sw-card"
              >
                {detail.summary.reasons.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="No recorded blockers in this report"
                  />
                ) : (
                  <List
                    size="small"
                    dataSource={detail.summary.reasons}
                    renderItem={(reason) => (
                      <List.Item>
                        <Space direction="vertical" size={0}>
                          <Tag>{reason.kind}</Tag>
                          <span className="sw-machine">{reason.text}</span>
                        </Space>
                      </List.Item>
                    )}
                  />
                )}
              </Card>
              <Card size="small" title="What human action remains" className="sw-card">
                <Space direction="vertical">
                  <StateFacet value={detail.summary.human_decision.approval_status} />
                  {detail.summary.human_decision.required_actions.length ? (
                    <TextList
                      values={detail.summary.human_decision.required_actions}
                      empty="No recorded human action"
                    />
                  ) : (
                    <Typography.Text type="secondary">
                      No recorded human action in this report.
                    </Typography.Text>
                  )}
                </Space>
              </Card>
              <Card size="small" title="Allowed and prohibited use" className="sw-card">
                <Typography.Text strong>Allowed</Typography.Text>
                <TextList
                  values={detail.allowed_use}
                  empty="No allowed-use statement recorded"
                />
                <Typography.Text strong>Prohibited</Typography.Text>
                <TextList
                  values={detail.prohibited_use}
                  empty="No prohibited-use statement recorded"
                />
              </Card>
            </div>
            {(detail.summary.caveats.length > 0 ||
              detail.summary.residual_risks.length > 0) && (
              <Alert
                type="warning"
                showIcon
                message="Recorded caveats and residual risks"
                description={
                  <TextList
                    values={[
                      ...detail.summary.caveats,
                      ...detail.summary.residual_risks,
                    ]}
                    empty="None recorded"
                  />
                }
              />
            )}
          </Space>
        ),
      },
      {
        key: "checks",
        label: "Checks",
        children: (
          <Row gutter={[16, 16]}>
            {(["passed", "failed", "unrun", "unknown"] as const).map((kind) => (
              <Col xs={24} lg={12} key={kind}>
                <Card
                  size="small"
                  title={`${kind[0]?.toUpperCase()}${kind.slice(1)} (${detail.checks[kind].length})`}
                  className="sw-card"
                >
                  <TextList
                    values={detail.checks[kind]}
                    empty={`No ${kind} checks recorded`}
                  />
                </Card>
              </Col>
            ))}
          </Row>
        ),
      },
      {
        key: "evidence",
        label: "Evidence explorer",
        children: (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Row gutter={[16, 16]}>
              {(["included", "missing", "omitted"] as const).map((kind) => (
                <Col xs={24} lg={8} key={kind}>
                  <Card
                    size="small"
                    title={`${kind[0]?.toUpperCase()}${kind.slice(1)} (${detail.evidence[kind].length})`}
                    className="sw-card"
                  >
                    <TextList
                      values={detail.evidence[kind]}
                      empty={`No ${kind} evidence recorded`}
                    />
                  </Card>
                </Col>
              ))}
            </Row>
            <EvidenceTracePanel recordId={recordId} active={activeTab === "evidence"} />
          </Space>
        ),
      },
      {
        key: "history",
        label: "History",
        children: (
          <ClaimHistoryPanel recordId={recordId} active={activeTab === "history"} />
        ),
      },
      {
        key: "reviews",
        label: "Review boundary",
        children: <ReviewBoundaryPanel detail={detail} />,
      },
      {
        key: "json",
        label: "JSON",
        children: (
          <RawDocument
            value={json}
            loading={documentLoading === "json"}
            error={documentError}
          />
        ),
      },
      {
        key: "report",
        label: "Report",
        children: (
          <RawDocument
            value={markdown}
            loading={documentLoading === "markdown"}
            error={documentError}
          />
        ),
      },
    ];
  }, [activeTab, detail, documentError, documentLoading, json, markdown, recordId]);

  if (loading) {
    return (
      <AppShell>
        <Skeleton active paragraph={{ rows: 10 }} />
      </AppShell>
    );
  }
  if (error || !detail) {
    return (
      <AppShell>
        <Alert
          type="error"
          showIcon
          message="Unable to open verification report"
          description={
            error ? `${error.code}: ${error.message}` : "No report detail returned"
          }
        />
      </AppShell>
    );
  }

  const verificationState = detail.summary.verification.verified
    ? "verified"
    : "not-verified";
  return (
    <AppShell>
      <Space direction="vertical" size={18} style={{ width: "100%" }}>
        <div>
          <div className="sw-kicker">Claim detail</div>
          <Typography.Title style={{ margin: "4px 0 8px" }}>
            {detail.summary.claim}
          </Typography.Title>
          <Space wrap>
            <StateFacet value={verificationState} />
            <StateFacet value={detail.summary.decision} />
            <StateFacet value={detail.summary.human_decision.approval_status} />
          </Space>
        </div>
        <Card className="sw-card" size="small">
          <Descriptions size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Receipt ID">
              <span className="mono sw-machine">{detail.source.record_id}</span>
            </Descriptions.Item>
            <Descriptions.Item label="Report digest">
              <span className="mono sw-machine">{detail.report_digest}</span>
            </Descriptions.Item>
            <Descriptions.Item label="Candidate digest">
              <span className="mono sw-machine">{detail.summary.candidate.digest}</span>
            </Descriptions.Item>
            <Descriptions.Item label="Generated at">{detail.generated_at}</Descriptions.Item>
            <Descriptions.Item label="Source captured at">
              {detail.source.captured_at}
            </Descriptions.Item>
            <Descriptions.Item label="As of">
              <Typography.Text type="secondary">
                Not asserted by this projection
              </Typography.Text>
            </Descriptions.Item>
          </Descriptions>
        </Card>
        <Tabs
          activeKey={activeTab}
          items={tabs}
          onChange={(key) => {
            const nextParams = new URLSearchParams(searchParams.toString());
            if (key === "summary") nextParams.delete("tab");
            else nextParams.set("tab", key);
            const query = nextParams.toString();
            router.replace(query ? `${pathname}?${query}` : pathname, {
              scroll: false,
            });
            if (key === "json" && json === null) {
              setDocumentLoading("json");
              setDocumentError(null);
              void getCanonicalJson(detail.links.canonical_json)
                .then(setJson)
                .catch((caught: unknown) =>
                  setDocumentError(
                    caught instanceof Error
                      ? caught.message
                      : "Unable to load canonical JSON",
                  ),
                )
                .finally(() => setDocumentLoading(null));
            }
            if (key === "report" && markdown === null) {
              setDocumentLoading("markdown");
              setDocumentError(null);
              void getCanonicalMarkdown(detail.links.canonical_markdown)
                .then(setMarkdown)
                .catch((caught: unknown) =>
                  setDocumentError(
                    caught instanceof Error
                      ? caught.message
                      : "Unable to load canonical Markdown",
                  ),
                )
                .finally(() => setDocumentLoading(null));
            }
          }}
        />
      </Space>
    </AppShell>
  );
}
