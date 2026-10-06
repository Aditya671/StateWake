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
import {
  getSecurityAssurance,
  type SecurityAssuranceRequest,
} from "@/lib/api/client";
import type {
  SecurityAssuranceView,
  SecurityAuditItemView,
} from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

interface SecurityFilters {
  event?: string;
  operation?: string;
  reason?: string;
  method?: string;
}

const DEFAULT_PAGE_SIZE = 25;

function recordKey(item: SecurityAuditItemView) {
  return `${item.sequence}:${item.digest}`;
}

function eventTag(event: SecurityAuditItemView["event"]) {
  if (event === "request_admitted") return <Tag color="success">request admitted</Tag>;
  if (event === "authentication_failed") return <Tag color="error">authentication failed</Tag>;
  if (event === "authorization_denied") return <Tag color="error">authorization denied</Tag>;
  return <Tag color="warning">request rejected</Tag>;
}

export function SecurityAssurancePanel() {
  const screens = Grid.useBreakpoint();
  const [form] = Form.useForm<SecurityFilters>();
  const [filters, setFilters] = useState<SecurityFilters>({});
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [view, setView] = useState<SecurityAssuranceView | null>(null);
  const [selected, setSelected] = useState<SecurityAuditItemView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const request: SecurityAssuranceRequest = { limit: pageSize, offset };
    if (filters.event) request.event = filters.event;
    if (filters.operation) request.operation = filters.operation;
    if (filters.reason) request.reason = filters.reason;
    if (filters.method) request.method = filters.method;
    setLoading(true);
    setError(null);
    getSecurityAssurance(request, controller.signal)
      .then((value) => {
        if (value.items.length === 0 && value.page.matched > 0 && value.page.offset > 0) {
          setOffset(0);
          return;
        }
        setView(value);
        if (selected !== null && !value.items.some((item) => item.sequence === selected.sequence)) {
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
                "Unable to load deployment-security audit evidence",
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

  const columns = useMemo<ColumnsType<SecurityAuditItemView>>(
    () => [
      { title: "Seq", dataIndex: "sequence", key: "sequence", width: 80 },
      {
        title: "Event",
        dataIndex: "event",
        key: "event",
        render: (value: SecurityAuditItemView["event"]) => eventTag(value),
      },
      {
        title: "Operation",
        dataIndex: "operation",
        key: "operation",
        render: (value: string | null) =>
          value === null ? <Typography.Text type="secondary">none</Typography.Text> : <Typography.Text className="sw-machine">{value}</Typography.Text>,
      },
      { title: "Method", dataIndex: "method", key: "method", width: 90 },
      { title: "Route", dataIndex: "route_kind", key: "route_kind" },
      { title: "Reason", dataIndex: "reason", key: "reason" },
      {
        title: "Inspect",
        key: "inspect",
        width: 90,
        render: (_value, item) => (
          <Button type="link" style={{ paddingInline: 0 }} onClick={() => setSelected(item)}>
            Details
          </Button>
        ),
      },
    ],
    [],
  );

  if (loading && view === null) return <Skeleton active paragraph={{ rows: 12 }} />;
  if (error) {
    const unconfigured = error.code === "SECURITY_AUDIT_SOURCE_NOT_CONFIGURED";
    const auditOversized = error.code === "SECURITY_AUDIT_SOURCE_TOO_LARGE";
    const runtimeInvalid = error.code === "INVALID_RUNTIME_CONTAINMENT_SNAPSHOT";
    const runtimeOversized = error.code === "RUNTIME_CONTAINMENT_SNAPSHOT_TOO_LARGE";
    return (
      <Alert
        type={unconfigured ? "warning" : "error"}
        showIcon
        message={
          unconfigured
            ? "Security assurance evidence is not configured"
            : runtimeInvalid
              ? "Runtime-containment configuration evidence is invalid"
              : runtimeOversized
                ? "Runtime-containment configuration exceeds the configured read boundary"
                : auditOversized
                  ? "Deployment security audit exceeds the configured read boundary"
                  : "Security assurance evidence is unavailable"
        }
        description={error.message}
      />
    );
  }
  if (view === null) return <Empty description="No security assurance view is available." />;

  const noEvents = view.observations.recorded_event_count === 0;
  const eventOptions = view.aggregates.by_event.map((item) => ({ value: item.event, label: `${item.event} (${item.count})` }));
  const operationOptions = view.aggregates.by_operation.map((item) => ({ value: item.operation, label: `${item.operation} (${item.count})` }));
  const reasonOptions = view.aggregates.by_reason.map((item) => ({ value: item.reason, label: `${item.reason} (${item.count})` }));
  const methodOptions = view.aggregates.by_method.map((item) => ({ value: item.method, label: `${item.method} (${item.count})` }));

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Alert
        type={noEvents ? "info" : "warning"}
        showIcon
        message={
          noEvents
            ? view.source.configured
              ? "No deployment-security events are recorded in this configured journal"
              : view.runtime_containment.snapshot_observed
                ? "Runtime-containment configuration is observed; no security-audit journal is configured"
                : "No deployment-security evidence is configured"
            : `${view.observations.recorded_event_count} deployment-security events are recorded`
        }
        description="Recorded audit events and the verification-service runtime snapshot are separate evidence. Neither is a security score or proof that live host identity, authorization, process isolation, quotas, or network controls are correctly configured."
      />

      <Row gutter={[12, 12]}>
        <Col xs={24} md={6}><Card className="sw-card" size="small"><Statistic title="Recorded events" value={view.observations.recorded_event_count} /></Card></Col>
        <Col xs={24} md={6}><Card className="sw-card" size="small"><Statistic title="Authentication failures" value={view.observations.authentication_failed_count} /></Card></Col>
        <Col xs={24} md={6}><Card className="sw-card" size="small"><Statistic title="Authorization denials" value={view.observations.authorization_denied_count} /></Card></Col>
        <Col xs={24} md={6}><Card className="sw-card" size="small"><Statistic title="Admitted requests" value={view.observations.request_admitted_count} /></Card></Col>
      </Row>

      <Card className="sw-card" size="small" title="Audit source boundary">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Audit source configured">{view.source.configured ? "yes" : "no"}</Descriptions.Item>
          <Descriptions.Item label="Audit file observed">{view.source.exists ? "yes" : "no"}</Descriptions.Item>
          <Descriptions.Item label="Chain integrity">{view.source.chain_integrity}</Descriptions.Item>
          <Descriptions.Item label="Journal bytes">{view.source.byte_size}</Descriptions.Item>
          <Descriptions.Item label="Read limit bytes">{view.source.read_limit_bytes}</Descriptions.Item>
          <Descriptions.Item label="Record limit">{view.source.record_limit}</Descriptions.Item>
          <Descriptions.Item label="Source path exposed">no</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="sw-card" size="small" title="Verification runtime containment">
        {!view.runtime_containment.snapshot_observed ? (
          <Alert
            type="info"
            showIcon
            message="Effective verification-service containment configuration is not observed"
            description="No runtime snapshot was explicitly supplied to this read API. Repository defaults are not presented as active deployment configuration."
          />
        ) : (
          <>
            <Alert
              type="info"
              showIcon
              message="Effective VerificationServiceConfig snapshot verified"
              description="This snapshot was emitted when the verification application was constructed. It proves the recorded configuration digest, not current process liveness or host-level isolation."
              style={{ marginBottom: 12 }}
            />
            <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
              <Descriptions.Item label="Recorded at">{view.runtime_containment.recorded_at_utc}</Descriptions.Item>
              <Descriptions.Item label="Configuration digest"><span className="sw-machine">{view.runtime_containment.configuration_digest}</span></Descriptions.Item>
              <Descriptions.Item label="Request body ceiling">{view.runtime_containment.verification_service.max_request_bytes} bytes</Descriptions.Item>
              <Descriptions.Item label="Read-only">yes</Descriptions.Item>
              <Descriptions.Item label="HTTPS required">{view.runtime_containment.verification_service.require_https ? "yes" : "no"}</Descriptions.Item>
              <Descriptions.Item label="Insecure HTTP explicitly allowed">{view.runtime_containment.verification_service.allow_insecure_http ? "yes" : "no"}</Descriptions.Item>
              <Descriptions.Item label="Configured artifact roots">{view.runtime_containment.verification_service.artifact_root_count}</Descriptions.Item>
              <Descriptions.Item label="Artifact root paths exposed">no</Descriptions.Item>
            </Descriptions>

            <Typography.Text strong style={{ display: "block", marginTop: 16 }}>Configured containment limits</Typography.Text>
            <Descriptions bordered size="small" column={{ xs: 1, md: 2 }} style={{ marginTop: 8 }}>
              <Descriptions.Item label="Input bytes">{view.runtime_containment.limits.max_input_bytes}</Descriptions.Item>
              <Descriptions.Item label="JSON depth">{view.runtime_containment.limits.max_json_depth}</Descriptions.Item>
              <Descriptions.Item label="JSON nodes">{view.runtime_containment.limits.max_json_nodes}</Descriptions.Item>
              <Descriptions.Item label="JSON string bytes">{view.runtime_containment.limits.max_string_bytes}</Descriptions.Item>
              <Descriptions.Item label="Archive members">{view.runtime_containment.limits.max_archive_members}</Descriptions.Item>
              <Descriptions.Item label="Archive expanded bytes">{view.runtime_containment.limits.max_archive_uncompressed_bytes}</Descriptions.Item>
              <Descriptions.Item label="Archive ratio">{view.runtime_containment.limits.max_archive_compression_ratio}</Descriptions.Item>
              <Descriptions.Item label="Graph nodes">{view.runtime_containment.limits.max_graph_nodes}</Descriptions.Item>
              <Descriptions.Item label="Verification seconds">{view.runtime_containment.limits.max_verification_seconds}</Descriptions.Item>
              <Descriptions.Item label="Concurrency">{view.runtime_containment.limits.max_concurrency}</Descriptions.Item>
              <Descriptions.Item label="Temporary bytes">{view.runtime_containment.limits.max_temporary_bytes}</Descriptions.Item>
            </Descriptions>

            <Typography.Text strong style={{ display: "block", marginTop: 16 }}>Enforcement boundary</Typography.Text>
            <Row gutter={[12, 12]} style={{ marginTop: 8 }}>
              <Col xs={24} lg={12}>
                <Alert
                  type="success"
                  showIcon
                  message="Verification-service enforced"
                  description="Request-body bytes plus bounded JSON input size, nesting depth, node count, and string/key byte size are wired to the active verification-service request boundary."
                />
              </Col>
              <Col xs={24} lg={12}>
                <Alert
                  type="warning"
                  showIcon
                  message="Configured does not mean service-enforced"
                  description="Archive limits are domain controls but are not wired to this service's custom runtime limits. Graph-node, cooperative deadline, concurrency, and temporary-byte values are configuration/policy ceilings and are not claimed as active verification-service enforcement."
                />
              </Col>
            </Row>
          </>
        )}
      </Card>

      <Card className="sw-card" size="small" title="Deployment-security contract boundary">
        <Alert
          type="info"
          showIcon
          message="StateWake does not persist a canonical live deployment-configuration snapshot"
          description="The contract below describes what the repository expects. It is not evidence that the current host configured those providers correctly."
          style={{ marginBottom: 12 }}
        />
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Authentication provider">{view.deployment_boundary.authentication_provider}</Descriptions.Item>
          <Descriptions.Item label="Authorization provider">{view.deployment_boundary.authorization_provider}</Descriptions.Item>
          <Descriptions.Item label="Request admission">{view.deployment_boundary.request_admission_provider}</Descriptions.Item>
          <Descriptions.Item label="Security event sink">{view.deployment_boundary.security_event_sink}</Descriptions.Item>
          <Descriptions.Item label="HTTPS default requirement">yes</Descriptions.Item>
          <Descriptions.Item label="Live configuration observed">no</Descriptions.Item>
        </Descriptions>
        <Typography.Text strong style={{ display: "block", marginTop: 16 }}>Protected operations</Typography.Text>
        <Space wrap style={{ marginTop: 8 }}>
          {view.deployment_boundary.protected_operations.map((item) => <Tag key={item}>{item}</Tag>)}
        </Space>
        <Typography.Text strong style={{ display: "block", marginTop: 16 }}>Host/deployment responsibilities not verified by this view</Typography.Text>
        <Space wrap style={{ marginTop: 8 }}>
          {view.deployment_boundary.host_responsibilities.map((item) => <Tag key={item}>{item}</Tag>)}
        </Space>
      </Card>

      <Card className="sw-card" size="small" title="Recorded security-event investigation">
        <Form<SecurityFilters>
          form={form}
          layout={screens.lg ? "inline" : "vertical"}
          onFinish={(values) => {
            setFilters(values);
            setOffset(0);
            setSelected(null);
          }}
        >
          <Form.Item name="event" label="Event"><Select allowClear options={eventOptions} style={{ minWidth: screens.lg ? 220 : undefined }} placeholder="All events" /></Form.Item>
          <Form.Item name="operation" label="Operation"><Select allowClear options={operationOptions} style={{ minWidth: screens.lg ? 220 : undefined }} placeholder="All operations" /></Form.Item>
          <Form.Item name="reason" label="Reason"><Select allowClear options={reasonOptions} style={{ minWidth: screens.lg ? 220 : undefined }} placeholder="All reasons" /></Form.Item>
          <Form.Item name="method" label="Method"><Select allowClear options={methodOptions} style={{ minWidth: screens.lg ? 120 : undefined }} placeholder="All" /></Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">Apply</Button>
              <Button onClick={() => { form.resetFields(); setFilters({}); setOffset(0); setSelected(null); }}>Clear</Button>
            </Space>
          </Form.Item>
        </Form>

        <div style={{ marginTop: 16 }}>
          {view.items.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={view.page.matched === 0 ? "No recorded security events match these exact filters." : "No events are present on this page."} />
          ) : screens.md ? (
            <Table<SecurityAuditItemView>
              rowKey={recordKey}
              columns={columns}
              dataSource={view.items}
              pagination={false}
              size="small"
              scroll={{ x: 1050 }}
            />
          ) : (
            <Space direction="vertical" size={10} style={{ width: "100%" }}>
              {view.items.map((item) => (
                <Card key={recordKey(item)} size="small">
                  <Space direction="vertical" size={6}>
                    {eventTag(item.event)}
                    <Typography.Text strong>{item.route_kind}</Typography.Text>
                    <Typography.Text type="secondary">{item.method} · {item.operation ?? "no mapped operation"}</Typography.Text>
                    <Typography.Text type="secondary">{item.occurred_at}</Typography.Text>
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
          onChange={(page, size) => {
            setPageSize(size);
            setOffset((page - 1) * size);
            setSelected(null);
          }}
        />
      </Card>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card className="sw-card" size="small" title="Events by outcome">
            {view.aggregates.by_event.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> : (
              <Table rowKey="event" size="small" pagination={false} dataSource={view.aggregates.by_event} columns={[{ title: "Event", dataIndex: "event", key: "event" }, { title: "Count", dataIndex: "count", key: "count", width: 90 }]} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="sw-card" size="small" title="Events by protected operation">
            {view.aggregates.by_operation.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> : (
              <Table rowKey="operation" size="small" pagination={false} dataSource={view.aggregates.by_operation} columns={[{ title: "Operation", dataIndex: "operation", key: "operation" }, { title: "Count", dataIndex: "count", key: "count", width: 90 }]} />
            )}
          </Card>
        </Col>
      </Row>

      <Card className="sw-card" size="small" title="Selected audit record">
        {selected === null ? (
          <Typography.Text type="secondary">Select one recorded event to inspect the exact privacy-safe audit fields.</Typography.Text>
        ) : (
          <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Sequence">{selected.sequence}</Descriptions.Item>
            <Descriptions.Item label="Occurred at">{selected.occurred_at}</Descriptions.Item>
            <Descriptions.Item label="Event">{selected.event}</Descriptions.Item>
            <Descriptions.Item label="Operation">{selected.operation ?? "none"}</Descriptions.Item>
            <Descriptions.Item label="Method">{selected.method}</Descriptions.Item>
            <Descriptions.Item label="Route category">{selected.route_kind}</Descriptions.Item>
            <Descriptions.Item label="Reason">{selected.reason}</Descriptions.Item>
            <Descriptions.Item label="Raw path">not exposed</Descriptions.Item>
            <Descriptions.Item label="Path digest"><span className="sw-machine">{selected.path_digest}</span></Descriptions.Item>
            <Descriptions.Item label="Reason digest"><span className="sw-machine">{selected.reason_digest}</span></Descriptions.Item>
            <Descriptions.Item label="Previous digest"><span className="sw-machine">{selected.previous_digest ?? "genesis"}</span></Descriptions.Item>
            <Descriptions.Item label="Record digest"><span className="sw-machine">{selected.digest}</span></Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      {view.limitations.map((item) => <Alert key={item} type="info" showIcon message={item} />)}
    </Space>
  );
}
