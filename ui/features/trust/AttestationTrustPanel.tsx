"use client";

import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Grid,
  Input,
  Pagination,
  Row,
  Select,
  Skeleton,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { getAttestationTrust, type AttestationTrustRequest } from "@/lib/api/client";
import type {
  AttestationTrustAnchorView,
  AttestationTrustItem,
  AttestationTrustView,
} from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

interface TrustFilters {
  decision?: string;
  reliabilityState?: string;
  keyStatus?: string;
  text?: string;
}

const DEFAULT_PAGE_SIZE = 25;

function statusTag(status: string) {
  const color = status === "active" ? "success" : status === "revoked" ? "error" : status === "superseded" ? "warning" : "default";
  return <Tag color={color}>{status}</Tag>;
}

function trustedText(value: boolean | null) {
  if (value === true) return <Tag color="success">yes</Tag>;
  if (value === false) return <Tag color="error">no</Tag>;
  return <Tag>not evaluated</Tag>;
}

function observedText(value: boolean | null) {
  if (value === true) return <Tag color="success">observed</Tag>;
  if (value === false) return <Tag>not observed</Tag>;
  return <Tag>not established</Tag>;
}

export function AttestationTrustPanel() {
  const screens = Grid.useBreakpoint();
  const [form] = Form.useForm<TrustFilters>();
  const [filters, setFilters] = useState<TrustFilters>({});
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [view, setView] = useState<AttestationTrustView | null>(null);
  const [selected, setSelected] = useState<AttestationTrustItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const request: AttestationTrustRequest = { limit: pageSize, offset };
    if (filters.decision) request.decision = filters.decision;
    if (filters.reliabilityState) request.reliabilityState = filters.reliabilityState;
    if (filters.keyStatus) request.keyStatus = filters.keyStatus;
    if (filters.text?.trim()) request.text = filters.text.trim();
    setLoading(true);
    setError(null);
    getAttestationTrust(request, controller.signal)
      .then((value) => {
        if (value.items.length === 0 && value.page.matched > 0 && value.page.offset > 0) {
          setOffset(0);
          return;
        }
        setView(value);
        if (selected && !value.items.some((item) => item.attestation_id === selected.attestation_id)) {
          setSelected(null);
        }
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setView(null);
        setSelected(null);
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load attestation trust evidence",
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
  }, [filters, offset, pageSize]);

  const columns = useMemo<ColumnsType<AttestationTrustItem>>(
    () => [
      {
        title: "Attestation",
        dataIndex: "attestation_id",
        key: "attestation_id",
        render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text>,
      },
      { title: "Decision", dataIndex: "decision", key: "decision", width: 100, render: (value: string) => <Tag>{value}</Tag> },
      { title: "Reliability", dataIndex: "reliability_state", key: "reliability_state", width: 120 },
      {
        title: "Signed binding",
        key: "signed_binding",
        width: 150,
        render: (_value, item) => item.signing_trust_context.authentication.authenticated === true
          ? <Tag color="success">verified</Tag>
          : item.signature_envelope_recorded
            ? <Tag color="warning">recorded</Tag>
            : <Tag>not recorded</Tag>,
      },
      {
        title: "Current key status",
        key: "key_status",
        width: 180,
        render: (_value, item) => statusTag(item.key_context.effective_current_status),
      },
      {
        title: "Trusted now",
        key: "trusted",
        width: 130,
        render: (_value, item) => trustedText(item.key_context.currently_trusted_for_signing),
      },
      {
        title: "Inspect",
        key: "inspect",
        width: 90,
        render: (_value, item) => <Button type="link" style={{ paddingInline: 0 }} onClick={() => setSelected(item)}>Details</Button>,
      },
    ],
    [],
  );

  if (loading && view === null) return <Skeleton active paragraph={{ rows: 12 }} />;
  if (error) {
    const unconfigured = error.code === "ATTESTATION_TRUST_SOURCE_NOT_CONFIGURED";
    return (
      <Alert
        type={unconfigured ? "warning" : "error"}
        showIcon
        message={unconfigured ? "Attestation trust sources are not configured" : "Attestation trust evidence is unavailable"}
        description={error.message}
      />
    );
  }
  if (view === null) return <Empty description="No attestation trust investigation view is available." />;

  const auth = view.sources.trust_state.authentication;
  const authType = auth.status === "verified" ? "success" : auth.status === "failed" ? "error" : "warning";
  const authMessage = auth.status === "verified"
    ? "Current trust-state snapshot is authenticated"
    : auth.status === "failed"
      ? "Current trust-state authentication failed"
      : auth.status === "dependency-unavailable"
        ? "Trust-state authentication dependency is unavailable"
        : "Current trust-state authentication is not configured";
  const history = view.sources.trust_history;
  const historyType = history.lifecycle_authoritative ? "success" : history.configured ? "warning" : "info";
  const historyMessage = history.lifecycle_authoritative
    ? `Authenticated trust history verified through version ${history.latest_version}`
    : history.authentication_status === "authority-not-configured"
      ? "Trust history is structurally valid but not authenticated"
      : history.authentication_status === "dependency-unavailable"
        ? "Trust-history authentication dependency is unavailable"
        : history.authentication_status === "not-present"
        ? "Configured trust history is not present"
        : history.authentication_status === "empty"
          ? "Configured trust history is empty"
          : "Canonical trust history is not configured";

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Alert type={authType} showIcon message={authMessage} description={auth.reason} />
      <Alert
        type={historyType}
        showIcon
        message={historyMessage}
        description={history.lifecycle_authoritative
          ? "Lifecycle transitions are derived only from authority-authenticated, predecessor-linked trust snapshots. Signed attestation records may additionally bind the exact trust-state version/digest used for signature verification, without claiming an external trusted timestamp for occurred_at."
          : "No historical lifecycle conclusion is derived unless the canonical history is independently authenticated."}
      />

      <Row gutter={[12, 12]}>
        <Col xs={12} lg={6}><Card className="sw-card" size="small"><Statistic title="Attestations" value={view.summary.total_attestations} /></Card></Col>
        <Col xs={12} lg={6}><Card className="sw-card" size="small"><Statistic title="Signed envelopes" value={view.summary.signed_envelope_records} /></Card></Col>
        <Col xs={12} lg={6}><Card className="sw-card" size="small"><Statistic title="Verified bindings" value={view.summary.verified_signed_bindings} /></Card></Col>
        <Col xs={12} lg={6}><Card className="sw-card" size="small"><Statistic title="Revoked refs" value={view.summary.revoked_key_references} /></Card></Col>
      </Row>
      <Row gutter={[12, 12]}>
        <Col xs={12} lg={6}><Card className="sw-card" size="small"><Statistic title="History states" value={history.state_count} /></Card></Col>
        <Col xs={12} lg={6}><Card className="sw-card" size="small"><Statistic title="Lifecycle transitions" value={history.transitions.length} /></Card></Col>
        <Col xs={12} lg={6}><Card className="sw-card" size="small"><Statistic title="Historically observed refs" value={view.summary.historically_observed_key_references} /></Card></Col>
        <Col xs={12} lg={6}><Card className="sw-card" size="small"><Statistic title="Ever-active refs" value={view.summary.historically_active_key_references} /></Card></Col>
      </Row>

      <Card className="sw-card" size="small" title="Trust authority boundary">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Attestation chain integrity">{view.sources.attestation_store.chain_integrity}</Descriptions.Item>
          <Descriptions.Item label="Attestation-store bytes">{view.sources.attestation_store.byte_size}</Descriptions.Item>
          <Descriptions.Item label="Trust-state snapshot">{view.sources.trust_state.present ? `version ${view.sources.trust_state.version}` : "not present"}</Descriptions.Item>
          <Descriptions.Item label="Trust-state authentication">{auth.status}</Descriptions.Item>
          <Descriptions.Item label="Authority key ID">{view.sources.trust_state.authority_key_id ?? "not recorded"}</Descriptions.Item>
          <Descriptions.Item label="Authority key digest"><span className="sw-machine">{auth.authority_key_digest ?? "not available"}</span></Descriptions.Item>
          <Descriptions.Item label="Trust-state predecessor"><span className="sw-machine">{view.sources.trust_state.previous_digest ?? "none recorded"}</span></Descriptions.Item>
          <Descriptions.Item label="Current state source">{view.sources.trust_state.derived_from_history ? (history.lifecycle_authoritative ? "authenticated history tip" : "history tip (diagnostic only)") : view.sources.trust_state.configured ? "configured current snapshot" : "not observed"}</Descriptions.Item>
          <Descriptions.Item label="History chain integrity">{history.chain_integrity}</Descriptions.Item>
          <Descriptions.Item label="History authentication">{history.authentication_status}</Descriptions.Item>
          <Descriptions.Item label="History/current alignment">{history.current_tip_alignment}</Descriptions.Item>
          <Descriptions.Item label="History bytes">{history.byte_size}</Descriptions.Item>
          <Descriptions.Item label="Raw authority keys exposed">no</Descriptions.Item>
          <Descriptions.Item label="Signed bindings recorded">{view.sources.attestation_store.signed_binding_count}</Descriptions.Item>
          <Descriptions.Item label="Signed attestation envelopes available">{view.summary.signed_envelope_records} canonical binding{view.summary.signed_envelope_records === 1 ? "" : "s"}</Descriptions.Item>
          <Descriptions.Item label="Trusted event timestamp reconstructed">no — signing context does not provide an external trusted timestamp for occurred_at</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="sw-card" size="small" title="Current trust anchors">
        {view.sources.trust_state.anchors.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No anchors are present in the configured current trust-state snapshot." />
        ) : (
          <Table<AttestationTrustAnchorView>
            rowKey="key_id"
            size="small"
            pagination={false}
            dataSource={view.sources.trust_state.anchors}
            scroll={{ x: 760 }}
            columns={[
              { title: "Key ID", dataIndex: "key_id", key: "key_id", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
              { title: "Recorded status", dataIndex: "recorded_status", key: "recorded_status", width: 140, render: statusTag },
              { title: "Superseded by", dataIndex: "superseded_by", key: "superseded_by", render: (value: string | null) => value ? <Typography.Text className="sw-machine">{value}</Typography.Text> : "—" },
              { title: "Current authority", dataIndex: "current_trust_applicable", key: "current_trust_applicable", width: 140, render: (value: boolean) => value ? <Tag color="success">applicable</Tag> : <Tag>diagnostic only</Tag> },
              { title: "Public-key SHA-256", dataIndex: "public_key_digest", key: "public_key_digest", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
            ]}
          />
        )}
      </Card>

      <Card className="sw-card" size="small" title="Authenticated trust migration history">
        {!history.lifecycle_authoritative ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No authenticated canonical trust history is available for lifecycle reconstruction." />
        ) : history.transitions.length === 0 ? (
          <Alert type="info" showIcon message="The authenticated history contains a single trust state; no migration transition has occurred." />
        ) : screens.md ? (
          <Table
            rowKey={(item) => `${item.from_version}-${item.to_version}-${item.to_digest}`}
            size="small"
            pagination={false}
            dataSource={history.transitions}
            scroll={{ x: 980 }}
            columns={[
              { title: "Versions", key: "versions", width: 110, render: (_value, item) => `${item.from_version} → ${item.to_version}` },
              { title: "Issued", dataIndex: "issued_at", key: "issued_at", width: 220 },
              { title: "Authority", dataIndex: "authority_key_id", key: "authority_key_id", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
              { title: "Activated", key: "activated", render: (_value, item) => item.activated_key_ids.length ? item.activated_key_ids.map((key) => <Tag key={key} color="success">{key}</Tag>) : "—" },
              { title: "Revoked", key: "revoked", render: (_value, item) => item.revoked_key_ids.length ? item.revoked_key_ids.map((key) => <Tag key={key} color="error">{key}</Tag>) : "—" },
              { title: "Superseded", key: "superseded", render: (_value, item) => item.superseded_keys.length ? item.superseded_keys.map((entry) => <Tag key={entry.key_id} color="warning">{entry.key_id} → {entry.superseded_by ?? "?"}</Tag>) : "—" },
            ]}
          />
        ) : (
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            {history.transitions.map((item) => (
              <Card key={`${item.from_version}-${item.to_version}-${item.to_digest}`} size="small">
                <Space direction="vertical" size={6}>
                  <Typography.Text strong>Trust state {item.from_version} → {item.to_version}</Typography.Text>
                  <Typography.Text type="secondary">{item.issued_at}</Typography.Text>
                  <Typography.Text>Authority: <span className="sw-machine">{item.authority_key_id}</span>{item.authority_changed ? " (changed)" : ""}</Typography.Text>
                  <Space wrap>
                    {item.activated_key_ids.map((key) => <Tag key={`a-${key}`} color="success">activated {key}</Tag>)}
                    {item.revoked_key_ids.map((key) => <Tag key={`r-${key}`} color="error">revoked {key}</Tag>)}
                    {item.superseded_keys.map((entry) => <Tag key={`s-${entry.key_id}`} color="warning">{entry.key_id} → {entry.superseded_by ?? "?"}</Tag>)}
                  </Space>
                </Space>
              </Card>
            ))}
          </Space>
        )}
      </Card>

      <Card className="sw-card" size="small" title="Attestation investigation">
        <Form<TrustFilters>
          form={form}
          layout={screens.lg ? "inline" : "vertical"}
          onFinish={(values) => { setFilters(values); setOffset(0); setSelected(null); }}
        >
          <Form.Item name="decision" label="Decision"><Select allowClear options={["accept", "review", "reject"].map((value) => ({ value, label: value }))} style={{ minWidth: 130 }} /></Form.Item>
          <Form.Item name="reliabilityState" label="Reliability"><Select allowClear options={["reliable", "degraded", "unreliable", "recovered"].map((value) => ({ value, label: value }))} style={{ minWidth: 150 }} /></Form.Item>
          <Form.Item name="keyStatus" label="Key status"><Select allowClear options={["active", "revoked", "superseded", "untrusted", "unsigned", "trust-state-unauthenticated", "trust-state-unconfigured"].map((value) => ({ value, label: value }))} style={{ minWidth: 210 }} /></Form.Item>
          <Form.Item name="text" label="Search"><Input allowClear maxLength={200} placeholder="ID, subject, actor, key ref" /></Form.Item>
          <Form.Item><Space><Button type="primary" htmlType="submit">Apply</Button><Button onClick={() => { form.resetFields(); setFilters({}); setOffset(0); setSelected(null); }}>Clear</Button></Space></Form.Item>
        </Form>

        <div style={{ marginTop: 16 }}>
          {view.items.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={view.page.matched === 0 ? "No attestations match these bounded filters." : "No attestations are present on this page."} />
          ) : screens.md ? (
            <Table<AttestationTrustItem> rowKey="attestation_id" size="small" pagination={false} dataSource={view.items} columns={columns} scroll={{ x: 1050 }} />
          ) : (
            <Space direction="vertical" size={10} style={{ width: "100%" }}>
              {view.items.map((item) => (
                <Card key={item.attestation_id} size="small">
                  <Space direction="vertical" size={6}>
                    <Typography.Text strong className="sw-machine">{item.attestation_id}</Typography.Text>
                    <Space wrap><Tag>{item.decision}</Tag><Tag>{item.reliability_state}</Tag>{statusTag(item.key_context.effective_current_status)}{item.signing_trust_context.authentication.authenticated === true ? <Tag color="success">signed binding verified</Tag> : item.signature_envelope_recorded ? <Tag color="warning">signed binding recorded</Tag> : <Tag>unsigned binding</Tag>}</Space>
                    <Typography.Text type="secondary">Subject: {item.subject_id}</Typography.Text>
                    <Button type="link" style={{ paddingInline: 0 }} onClick={() => setSelected(item)}>Details</Button>
                  </Space>
                </Card>
              ))}
            </Space>
          )}
        </div>
        <Pagination
          style={{ marginTop: 16 }}
          current={Math.floor(view.page.offset / view.page.limit) + 1}
          pageSize={view.page.limit}
          total={view.page.matched}
          showSizeChanger
          pageSizeOptions={[10, 25, 50, 100, 200]}
          onChange={(page, size) => { setPageSize(size); setOffset((page - 1) * size); setSelected(null); }}
        />
      </Card>

      <Card className="sw-card" size="small" title="Selected attestation trust context">
        {selected === null ? (
          <Typography.Text type="secondary">Select an attestation to inspect its recorded key reference and current authenticated trust context.</Typography.Text>
        ) : (
          <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Attestation"><span className="sw-machine">{selected.attestation_id}</span></Descriptions.Item>
            <Descriptions.Item label="Subject">{selected.subject_id}</Descriptions.Item>
            <Descriptions.Item label="Occurred at">{selected.occurred_at}</Descriptions.Item>
            <Descriptions.Item label="Actor">{selected.actor}</Descriptions.Item>
            <Descriptions.Item label="Decision">{selected.decision}</Descriptions.Item>
            <Descriptions.Item label="Reliability state">{selected.reliability_state}</Descriptions.Item>
            <Descriptions.Item label="Signing key ID"><span className="sw-machine">{selected.key_context.signing_key_id ?? "unsigned"}</span></Descriptions.Item>
            <Descriptions.Item label="Effective current status">{statusTag(selected.key_context.effective_current_status)}</Descriptions.Item>
            <Descriptions.Item label="Currently trusted for signing">{trustedText(selected.key_context.currently_trusted_for_signing)}</Descriptions.Item>
            <Descriptions.Item label="Recorded anchor status">{selected.key_context.recorded_anchor_status ?? "not recorded"}</Descriptions.Item>
            <Descriptions.Item label="Superseded by"><span className="sw-machine">{selected.key_context.superseded_by ?? "—"}</span></Descriptions.Item>
            <Descriptions.Item label="Public-key SHA-256"><span className="sw-machine">{selected.key_context.public_key_digest ?? "not available"}</span></Descriptions.Item>
            <Descriptions.Item label="Observed in authenticated history">{observedText(selected.key_context.historical_context.observed_in_authenticated_history)}</Descriptions.Item>
            <Descriptions.Item label="Ever observed active">{observedText(selected.key_context.historical_context.ever_observed_active)}</Descriptions.Item>
            <Descriptions.Item label="Historical statuses">{selected.key_context.historical_context.observed_statuses.length ? selected.key_context.historical_context.observed_statuses.map(statusTag) : "not established"}</Descriptions.Item>
            <Descriptions.Item label="Observed history versions">{selected.key_context.historical_context.first_observed_version === null ? "not established" : `${selected.key_context.historical_context.first_observed_version} → ${selected.key_context.historical_context.last_observed_version}`}</Descriptions.Item>
            <Descriptions.Item label="Signed envelope">{selected.signature_envelope_recorded ? "recorded" : "not recorded"}</Descriptions.Item>
            <Descriptions.Item label="Signing context verification">{selected.signing_trust_context.authentication.authenticated === true ? <Tag color="success">verified</Tag> : <Tag>{selected.signing_trust_context.authentication.status}</Tag>}</Descriptions.Item>
            <Descriptions.Item label="Bound trust-state version">{selected.signing_trust_context.trust_state_version ?? "not recorded"}</Descriptions.Item>
            <Descriptions.Item label="Bound trust-state digest"><span className="sw-machine">{selected.signing_trust_context.trust_state_digest ?? "not recorded"}</span></Descriptions.Item>
            <Descriptions.Item label="Bound signing-key digest"><span className="sw-machine">{selected.signing_trust_context.signing_key_digest ?? "not recorded"}</span></Descriptions.Item>
            <Descriptions.Item label="Bound authority key"><span className="sw-machine">{selected.signing_trust_context.authority_key_id ?? "not recorded"}</span></Descriptions.Item>
            <Descriptions.Item label="Bound authority-key digest"><span className="sw-machine">{selected.signing_trust_context.authority_key_digest ?? "not recorded"}</span></Descriptions.Item>
            <Descriptions.Item label="Signing-time key status">{selected.signing_trust_context.signing_time_key_status ?? "not verified"}</Descriptions.Item>
            <Descriptions.Item label="Trusted event timestamp">not recorded — the signature binds occurred_at as data but does not provide an external trusted timestamp</Descriptions.Item>
            <Descriptions.Item label="Attestation digest"><span className="sw-machine">{selected.attestation_digest}</span></Descriptions.Item>
            <Descriptions.Item label="Previous attestation digest"><span className="sw-machine">{selected.previous_digest}</span></Descriptions.Item>
            <Descriptions.Item label="Key version/provider">not persisted by canonical attestation record</Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      {view.limitations.map((item) => <Alert key={item} type="info" showIcon message={item} />)}
    </Space>
  );
}
