"use client";

import {
  Alert,
  Button,
  Card,
  Checkbox,
  Empty,
  Form,
  Input,
  List,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import { useEffect, useRef, useState } from "react";
import {
  StateIdentityCard,
  StateMetricCard,
  StateStatusCard,
} from "@/components/cards/StateWakeCards";
import {
  createHumanApproval,
  createReviewStatement,
  getHumanApprovals,
  getReviewCapabilities,
  getReviewThread,
  revokeHumanApproval,
  supersedeHumanApproval,
} from "@/lib/api/client";
import type {
  ClaimDetail,
  HumanApprovalInput,
  HumanApprovalLifecycleInput,
  HumanApprovalThread,
  ReviewCapabilities,
  ReviewCategory,
  ReviewStatementInput,
  ReviewThread,
} from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

interface ReviewFormValues {
  category: ReviewCategory;
  statement: string;
  finding_refs: string;
  limitation: string;
  scope: string;
}

interface ApprovalFormValues {
  reason: string;
  confirmed: boolean;
}

interface ApprovalLifecycleFormValues {
  reason: string;
  confirmed: boolean;
}

type ApprovalLifecycleAction = "revoke" | "supersede";

const CATEGORY_OPTIONS: { label: string; value: ReviewCategory }[] = [
  { label: "Observation", value: "observation" },
  { label: "Question", value: "question" },
  { label: "Change requested", value: "change_requested" },
  { label: "Finding", value: "finding" },
  { label: "Review complete", value: "review_complete" },
];

function errorMessage(error: unknown): string {
  if (error instanceof StateWakeApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Human review service request failed";
}

function assertSameBasis(
  detail: ClaimDetail,
  target: { report_digest: string; candidate_digest: string },
  kind: string,
): void {
  if (
    target.report_digest !== detail.report_digest ||
    target.candidate_digest !== detail.summary.candidate.digest
  ) {
    throw new Error(`${kind} basis does not match this verification report`);
  }
}

export function ReviewBoundaryPanel({ detail }: { detail: ClaimDetail }) {
  const human = detail.summary.human_decision;
  const [reviewForm] = Form.useForm<ReviewFormValues>();
  const [approvalForm] = Form.useForm<ApprovalFormValues>();
  const [lifecycleForm] = Form.useForm<ApprovalLifecycleFormValues>();
  const [capabilities, setCapabilities] = useState<ReviewCapabilities | null>(null);
  const [thread, setThread] = useState<ReviewThread | null>(null);
  const [approvalThread, setApprovalThread] = useState<HumanApprovalThread | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [approving, setApproving] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const [lifecycleTarget, setLifecycleTarget] = useState<{
    action: ApprovalLifecycleAction;
    receiptId: string;
  } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [approvalNotice, setApprovalNotice] = useState<string | null>(null);
  const [lifecycleNotice, setLifecycleNotice] = useState<string | null>(null);
  const reviewIdempotencyKey = useRef<string | null>(null);
  const approvalIdempotencyKey = useRef<string | null>(null);
  const lifecycleIdempotencyKey = useRef<string | null>(null);

  async function loadReviewState(signal?: AbortSignal): Promise<void> {
    const nextCapabilities = await getReviewCapabilities(signal);
    const nextThread = await getReviewThread(detail.source.record_id, signal);
    assertSameBasis(detail, nextThread.target, "Review thread");

    let nextApprovalThread: HumanApprovalThread | null = null;
    if (nextCapabilities.features.approval_read) {
      nextApprovalThread = await getHumanApprovals(detail.source.record_id, signal);
      assertSameBasis(detail, nextApprovalThread.target, "Approval evidence");
    }

    setCapabilities(nextCapabilities);
    setThread(nextThread);
    setApprovalThread(nextApprovalThread);
    setLoadError(null);
  }

  useEffect(() => {
    const controller = new AbortController();
    loadReviewState(controller.signal).catch((error: unknown) => {
      if (!controller.signal.aborted) setLoadError(errorMessage(error));
    });
    return () => controller.abort();
  }, [detail.source.record_id, detail.report_digest, detail.summary.candidate.digest]);

  async function submitReview(values: ReviewFormValues): Promise<void> {
    if (!capabilities?.features.review_write) return;
    setSubmitting(true);
    setSubmitError(null);
    setNotice(null);
    const requestKey = reviewIdempotencyKey.current ?? crypto.randomUUID();
    reviewIdempotencyKey.current = requestKey;
    const input: ReviewStatementInput = {
      schema_version: "review-statement-input.v1",
      candidate_digest: detail.summary.candidate.digest,
      report_digest: detail.report_digest,
      category: values.category,
      statement: values.statement.trim(),
      finding_refs: values.finding_refs
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
      limitation: values.limitation.trim() || null,
      scope: values.scope.trim(),
      supersedes_digest: null,
    };
    try {
      const result = await createReviewStatement(
        detail.source.record_id,
        input,
        requestKey,
      );
      setNotice(
        result.created
          ? "Review statement recorded against this exact report basis."
          : "The previous idempotent review result was returned; no duplicate was created.",
      );
      reviewForm.resetFields();
      reviewIdempotencyKey.current = null;
      await loadReviewState();
    } catch (error: unknown) {
      setSubmitError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitApproval(values: ApprovalFormValues): Promise<void> {
    if (!capabilities?.features.approval_write || !approvalThread) return;
    setApproving(true);
    setApprovalError(null);
    setApprovalNotice(null);
    const requestKey = approvalIdempotencyKey.current ?? crypto.randomUUID();
    approvalIdempotencyKey.current = requestKey;
    const input: HumanApprovalInput = {
      schema_version: "human-approval-input.v1",
      candidate_digest: detail.summary.candidate.digest,
      report_digest: detail.report_digest,
      reason: values.reason.trim(),
      confirmed: true,
    };
    try {
      const result = await createHumanApproval(
        detail.source.record_id,
        input,
        requestKey,
      );
      setApprovalNotice(
        result.created
          ? "Canonical HumanApprovalContract evidence was recorded for the configured action and scope."
          : "The previous idempotent approval result was returned; no duplicate approval was created.",
      );
      approvalForm.resetFields();
      approvalIdempotencyKey.current = null;
      await loadReviewState();
    } catch (error: unknown) {
      setApprovalError(errorMessage(error));
    } finally {
      setApproving(false);
    }
  }

  async function submitApprovalLifecycle(values: ApprovalLifecycleFormValues): Promise<void> {
    if (!lifecycleTarget || !approvalThread || !capabilities) return;
    const featureAllowed =
      lifecycleTarget.action === "revoke"
        ? capabilities.features.approval_revoke
        : capabilities.features.approval_supersede;
    if (!featureAllowed) return;
    setTransitioning(true);
    setLifecycleError(null);
    setLifecycleNotice(null);
    const requestKey = lifecycleIdempotencyKey.current ?? crypto.randomUUID();
    lifecycleIdempotencyKey.current = requestKey;
    const input: HumanApprovalLifecycleInput = {
      schema_version: "human-approval-lifecycle-input.v1",
      candidate_digest: detail.summary.candidate.digest,
      report_digest: detail.report_digest,
      reason: values.reason.trim(),
      confirmed: true,
    };
    try {
      const result =
        lifecycleTarget.action === "revoke"
          ? await revokeHumanApproval(
              detail.source.record_id,
              lifecycleTarget.receiptId,
              input,
              requestKey,
            )
          : await supersedeHumanApproval(
              detail.source.record_id,
              lifecycleTarget.receiptId,
              input,
              requestKey,
            );
      setLifecycleNotice(
        result.created
          ? lifecycleTarget.action === "revoke"
            ? "Canonical revocation evidence was recorded. The historical approval remains auditable but is no longer effective."
            : "A canonical replacement approval was recorded. The predecessor remains auditable as superseded history."
          : "The previous idempotent lifecycle result was returned; no duplicate evidence was created.",
      );
      lifecycleForm.resetFields();
      lifecycleIdempotencyKey.current = null;
      setLifecycleTarget(null);
      await loadReviewState();
    } catch (error: unknown) {
      setLifecycleError(errorMessage(error));
    } finally {
      setTransitioning(false);
    }
  }

  const activeApprovalItems =
    approvalThread?.items.filter((item) => item.lifecycle?.status === "active") ?? [];
  const approvalAlreadyRecorded = activeApprovalItems.length > 0;
  const approvalRequired = human.approval_status === "requires-human-approval";
  const approvalWriteAvailable = Boolean(
    capabilities?.features.approval_write && approvalThread && approvalRequired,
  );

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        message="Review and approval are separate authorities"
        description="Review statements preserve human reasoning. Human approval, when explicitly configured, is recorded as canonical HumanApprovalContract evidence for one exact report digest, action, and scope. Neither operation rewrites the machine verification report or publishes a release."
      />

      <div className="sw-overview-grid">
        <StateMetricCard
          label="Review statements"
          value={thread?.items.length ?? 0}
          helper="Append-only statements for this exact report basis"
          tone="info"
        />
        <StateMetricCard
          label="Active approvals"
          value={activeApprovalItems.length}
          helper={`${approvalThread?.items.length ?? 0} canonical approval record(s) retained as lifecycle history`}
          tone={approvalAlreadyRecorded ? "success" : approvalRequired ? "warning" : "neutral"}
        />
        <StateStatusCard
          title="Recorded human decision"
          value={human.approval_status}
          description="This is the immutable verification report state; later approval evidence does not rewrite it."
          eyebrow="Report authority"
        />
        {capabilities ? (
          <StateIdentityCard
            label="Authenticated reviewer"
            value={capabilities.actor.identity_ref}
            tag={capabilities.actor.role}
          />
        ) : (
          <StateMetricCard
            label="Secured review service"
            value="Unavailable"
            helper="Report inspection remains available without inventing reviewer identity"
            tone="warning"
          />
        )}
      </div>

      {human.required_actions.length > 0 ? (
        <Card bordered={false} className="sw-panel-card" title="Required human actions recorded by the report">
          <List
            size="small"
            dataSource={human.required_actions}
            renderItem={(value) => <List.Item>{value}</List.Item>}
          />
        </Card>
      ) : null}

      {loadError ? (
        <Alert
          type="warning"
          showIcon
          message="Secured human-review service unavailable"
          description={`${loadError}. Canonical report inspection remains available; review and approval writes are not assumed to exist.`}
        />
      ) : null}

      <Card bordered={false} title="Review statements" className="sw-panel-card">
        {thread && thread.items.length > 0 ? (
          <List
            itemLayout="vertical"
            dataSource={thread.items}
            renderItem={(item) => (
              <List.Item key={item.digest} className="sw-record-list-item">
                <Space direction="vertical" size={5} style={{ width: "100%" }}>
                  <Space wrap>
                    <Tag>{item.category}</Tag>
                    <Typography.Text strong>{item.actor_identity_ref}</Typography.Text>
                    <Typography.Text type="secondary">{item.actor_role}</Typography.Text>
                    <Typography.Text type="secondary">{item.created_at}</Typography.Text>
                  </Space>
                  <Typography.Text>{item.statement}</Typography.Text>
                  {item.finding_refs.length > 0 ? (
                    <Typography.Text type="secondary">
                      References: {item.finding_refs.join(", ")}
                    </Typography.Text>
                  ) : null}
                  {item.limitation ? (
                    <Typography.Text type="secondary">
                      Reviewer-described limitation: {item.limitation}
                    </Typography.Text>
                  ) : null}
                  <Typography.Text className="sw-machine" type="secondary">
                    Review digest: {item.digest}
                  </Typography.Text>
                </Space>
              </List.Item>
            )}
          />
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No review statements recorded for this exact report basis"
          />
        )}
      </Card>

      {capabilities?.features.review_write ? (
        <Card bordered={false} title="Record review statement" className="sw-panel-card">
          <Form<ReviewFormValues>
            form={reviewForm}
            layout="vertical"
            initialValues={{
              category: "observation",
              finding_refs: "",
              limitation: "",
              scope: "candidate review",
            }}
            onValuesChange={() => {
              reviewIdempotencyKey.current = null;
              setNotice(null);
              setSubmitError(null);
            }}
            onFinish={submitReview}
          >
            <div className="sw-grid">
              <Form.Item label="Exact candidate digest">
                <Input value={detail.summary.candidate.digest} readOnly className="sw-machine" />
              </Form.Item>
              <Form.Item label="Exact report digest">
                <Input value={detail.report_digest} readOnly className="sw-machine" />
              </Form.Item>
            </div>
            <Form.Item name="category" label="Review category" rules={[{ required: true }]}>
              <Select options={CATEGORY_OPTIONS} />
            </Form.Item>
            <Form.Item
              name="statement"
              label="Statement"
              rules={[
                { required: true, whitespace: true },
                { max: capabilities.limits.statement_chars },
              ]}
            >
              <Input.TextArea rows={5} maxLength={capabilities.limits.statement_chars} showCount />
            </Form.Item>
            <Form.Item name="finding_refs" label="Finding/evidence references (comma separated)">
              <Input placeholder="finding-12, retrieval-evidence" />
            </Form.Item>
            <Form.Item
              name="limitation"
              label="Reviewer-described limitation (optional)"
              rules={[{ max: capabilities.limits.limitation_chars }]}
            >
              <Input.TextArea rows={2} maxLength={capabilities.limits.limitation_chars} showCount />
            </Form.Item>
            <Form.Item
              name="scope"
              label="Review scope"
              rules={[{ required: true, whitespace: true }, { max: 512 }]}
            >
              <Input />
            </Form.Item>
            {submitError ? <Alert type="error" showIcon message={submitError} /> : null}
            {notice ? <Alert type="success" showIcon message={notice} /> : null}
            <Button type="primary" htmlType="submit" loading={submitting}>
              Record review statement
            </Button>
          </Form>
        </Card>
      ) : null}

      {approvalThread ? (
        <Card
          bordered={false}
          className={approvalAlreadyRecorded ? "sw-approval-card" : "sw-warning-card"}
          title="Human approval authority"
        >
          <Space direction="vertical" size={14} style={{ width: "100%" }}>
            <div className="sw-grid">
              <StateIdentityCard
                label="Configured approval action"
                value={approvalThread.authority.approval_action}
              />
              <StateIdentityCard label="Configured scope" value={approvalThread.authority.scope} />
            </div>
            <Typography.Text type="secondary">
              The server supplies this action and scope. The browser cannot replace them, choose the actor identity, or expand the authority represented by the approval evidence.
            </Typography.Text>

            {approvalThread.items.length > 0 ? (
              <List
                itemLayout="vertical"
                dataSource={approvalThread.items}
                renderItem={(item) => (
                  <List.Item key={item.receipt.receipt_id} className="sw-record-list-item">
                    <Space direction="vertical" size={5} style={{ width: "100%" }}>
                      <Space wrap>
                        <Tag
                          color={
                            item.lifecycle?.status === "active"
                              ? "success"
                              : item.lifecycle?.status === "revoked"
                                ? "error"
                                : "warning"
                          }
                        >
                          {item.lifecycle?.status === "active"
                            ? "Active approval"
                            : item.lifecycle?.status === "revoked"
                              ? "Revoked approval"
                              : "Superseded approval"}
                        </Tag>
                        <Typography.Text strong>
                          {item.contract.actor_identity_ref}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          {item.contract.role}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          {item.contract.captured_at}
                        </Typography.Text>
                      </Space>
                      <Typography.Text>
                        {item.contract.approval_action} · {item.contract.scope}
                      </Typography.Text>
                      <Typography.Text className="sw-machine" type="secondary">
                        Basis: {item.contract.approval_basis_digest}
                      </Typography.Text>
                      <Typography.Text className="sw-machine" type="secondary">
                        Receipt: {item.receipt.receipt_id}
                      </Typography.Text>
                      {item.lifecycle?.superseded_by_receipt_id ? (
                        <Typography.Text className="sw-machine" type="secondary">
                          Superseded by: {item.lifecycle.superseded_by_receipt_id}
                        </Typography.Text>
                      ) : null}
                      {item.lifecycle?.revocation ? (
                        <Typography.Text type="secondary">
                          Revoked by {item.lifecycle.revocation.contract.actor_identity_ref}: {item.lifecycle.revocation.contract.reason}
                        </Typography.Text>
                      ) : null}
                      {item.lifecycle?.status === "active" ? (
                        <Space wrap>
                          {capabilities?.features.approval_supersede ? (
                            <Button
                              onClick={() => {
                                setLifecycleTarget({
                                  action: "supersede",
                                  receiptId: item.receipt.receipt_id,
                                });
                                lifecycleForm.resetFields();
                                lifecycleIdempotencyKey.current = null;
                                setLifecycleError(null);
                                setLifecycleNotice(null);
                              }}
                            >
                              Supersede approval
                            </Button>
                          ) : null}
                          {capabilities?.features.approval_revoke ? (
                            <Button
                              danger
                              onClick={() => {
                                setLifecycleTarget({
                                  action: "revoke",
                                  receiptId: item.receipt.receipt_id,
                                });
                                lifecycleForm.resetFields();
                                lifecycleIdempotencyKey.current = null;
                                setLifecycleError(null);
                                setLifecycleNotice(null);
                              }}
                            >
                              Revoke approval
                            </Button>
                          ) : null}
                        </Space>
                      ) : null}
                    </Space>
                  </List.Item>
                )}
              />
            ) : (
              <Alert
                type={approvalRequired ? "warning" : "info"}
                showIcon
                message={
                  approvalRequired
                    ? "This report requires human approval; none is recorded for this exact basis."
                    : "No HumanApprovalContract evidence is recorded for this exact report basis."
                }
              />
            )}

            {lifecycleTarget ? (
              <Card
                size="small"
                title={
                  lifecycleTarget.action === "revoke"
                    ? "Revoke active human approval"
                    : "Supersede active human approval"
                }
              >
                <Form<ApprovalLifecycleFormValues>
                  form={lifecycleForm}
                  layout="vertical"
                  initialValues={{ confirmed: false, reason: "" }}
                  onValuesChange={() => {
                    lifecycleIdempotencyKey.current = null;
                    setLifecycleError(null);
                    setLifecycleNotice(null);
                  }}
                  onFinish={submitApprovalLifecycle}
                >
                  <Typography.Paragraph type="secondary">
                    This appends canonical lifecycle evidence against approval receipt {" "}
                    <Typography.Text className="sw-machine">
                      {lifecycleTarget.receiptId}
                    </Typography.Text>
                    . The predecessor bytes remain immutable.
                  </Typography.Paragraph>
                  <Form.Item
                    name="reason"
                    label={
                      lifecycleTarget.action === "revoke"
                        ? "Revocation reason"
                        : "Replacement approval reason"
                    }
                    rules={[
                      { required: true, whitespace: true },
                      { max: capabilities?.limits.approval_reason_chars ?? 2000 },
                    ]}
                  >
                    <Input.TextArea
                      rows={4}
                      maxLength={capabilities?.limits.approval_reason_chars ?? 2000}
                      showCount
                    />
                  </Form.Item>
                  <Form.Item
                    name="confirmed"
                    valuePropName="checked"
                    rules={[
                      {
                        validator: (_, value: boolean | undefined) =>
                          value === true
                            ? Promise.resolve()
                            : Promise.reject(
                                new Error(
                                  "Confirm the exact approval receipt and immutable report basis before recording this lifecycle transition.",
                                ),
                              ),
                      },
                    ]}
                  >
                    <Checkbox>
                      I confirm this {lifecycleTarget.action} operation for the exact configured
                      action, scope, candidate, approval receipt, and report digest shown here.
                    </Checkbox>
                  </Form.Item>
                  {lifecycleError ? <Alert type="error" showIcon message={lifecycleError} /> : null}
                  {lifecycleNotice ? (
                    <Alert type="success" showIcon message={lifecycleNotice} />
                  ) : null}
                  <Space wrap>
                    <Button
                      type="primary"
                      danger={lifecycleTarget.action === "revoke"}
                      htmlType="submit"
                      loading={transitioning}
                    >
                      {lifecycleTarget.action === "revoke"
                        ? "Record canonical revocation"
                        : "Record superseding approval"}
                    </Button>
                    <Button
                      disabled={transitioning}
                      onClick={() => {
                        setLifecycleTarget(null);
                        lifecycleForm.resetFields();
                        lifecycleIdempotencyKey.current = null;
                        setLifecycleError(null);
                      }}
                    >
                      Cancel
                    </Button>
                  </Space>
                </Form>
              </Card>
            ) : null}

            {approvalWriteAvailable && !approvalAlreadyRecorded ? (
              <Form<ApprovalFormValues>
                form={approvalForm}
                layout="vertical"
                initialValues={{ confirmed: false, reason: "" }}
                onValuesChange={() => {
                  approvalIdempotencyKey.current = null;
                  setApprovalNotice(null);
                  setApprovalError(null);
                }}
                onFinish={submitApproval}
              >
                <Form.Item
                  name="reason"
                  label="Approval reason"
                  rules={[
                    { required: true, whitespace: true },
                    { max: capabilities?.limits.approval_reason_chars ?? 2000 },
                  ]}
                >
                  <Input.TextArea
                    rows={4}
                    maxLength={capabilities?.limits.approval_reason_chars ?? 2000}
                    showCount
                  />
                </Form.Item>
                <Form.Item
                  name="confirmed"
                  valuePropName="checked"
                  rules={[
                    {
                      validator: (_, value: boolean | undefined) =>
                        value === true
                          ? Promise.resolve()
                          : Promise.reject(
                              new Error(
                                "Confirm the exact action, scope, candidate, and report basis before recording approval.",
                              ),
                            ),
                    },
                  ]}
                >
                  <Checkbox>
                    I confirm approval only for <strong>{approvalThread.authority.approval_action}</strong> within <strong>{approvalThread.authority.scope}</strong>, bound to this exact immutable report digest.
                  </Checkbox>
                </Form.Item>
                {approvalError ? <Alert type="error" showIcon message={approvalError} /> : null}
                {approvalNotice ? <Alert type="success" showIcon message={approvalNotice} /> : null}
                <Button type="primary" htmlType="submit" loading={approving}>
                  Record scoped human approval
                </Button>
              </Form>
            ) : null}
          </Space>
        </Card>
      ) : null}

      <Card bordered={false} title="Recorded decision rationale" className="sw-panel-card">
        {detail.decision_rationale.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No decision rationale recorded" />
        ) : (
          <List
            size="small"
            dataSource={detail.decision_rationale}
            renderItem={(value) => <List.Item>{value}</List.Item>}
          />
        )}
      </Card>

      <Alert
        type="warning"
        showIcon
        message="Bounded approval does not mean publication"
        description="Human approval lifecycle changes append canonical revocation or supersession evidence and preserve the historical approval bytes. They do not publish a release, execute an external side effect, or retroactively mutate the verification report. Fresh release-proof reconciliation consumes only the currently active approval lifecycle state."
      />
    </Space>
  );
}
