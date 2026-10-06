"use client";

import { Alert, Card, Col, Descriptions, Empty, Row, Skeleton, Space, Table, Tag, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { useEffect, useMemo, useState } from "react";
import { getAccessAuthorization } from "@/lib/api/client";
import type { AccessAuthorizationView } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

type Grant = AccessAuthorizationView["policy"]["grants"][number];
type Scope = AccessAuthorizationView["principal"]["resource_scopes"][number];

export function AccessAuthorizationPanel() {
  const [view, setView] = useState<AccessAuthorizationView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getAccessAuthorization(controller.signal)
      .then(setView)
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load authorization policy context",
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

  const grantColumns = useMemo<TableColumnsType<Grant>>(
    () => [
      { title: "Role", dataIndex: "role", key: "role" },
      { title: "Operation", dataIndex: "operation", key: "operation" },
      {
        title: "Allowed resource states",
        dataIndex: "allowed_states",
        key: "allowed_states",
        render: (states: string[]) => <Space wrap>{states.map((state) => <Tag key={state}>{state}</Tag>)}</Space>,
      },
    ],
    [],
  );
  const scopeColumns = useMemo<TableColumnsType<Scope>>(
    () => [
      {
        title: "Resource-domain digest",
        dataIndex: "resource_domain_digest",
        key: "resource_domain_digest",
        render: (value: string) => <span className="sw-machine">{value}</span>,
      },
      { title: "Resources", dataIndex: "resource_count", key: "resource_count", width: 110 },
    ],
    [],
  );

  if (loading) return <Skeleton active paragraph={{ rows: 12 }} />;
  if (error) {
    const unconfigured = error.code === "AUTHORIZATION_CONTEXT_SOURCE_NOT_CONFIGURED";
    const oversized = error.code === "AUTHORIZATION_CONTEXT_SOURCE_TOO_LARGE";
    return (
      <Alert
        type={unconfigured ? "warning" : "error"}
        showIcon
        message={
          unconfigured
            ? "Authorization context is not configured"
            : oversized
              ? "Authorization context exceeds the configured read boundary"
              : "Authorization context could not be replay-verified"
        }
        description={error.message}
      />
    );
  }
  if (view === null) return <Empty description="No authorization policy investigation is available." />;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Alert
        type={view.decision.allowed ? "success" : "warning"}
        showIcon
        message={view.decision.allowed ? "StateWake policy replay allowed this exact request" : "StateWake policy replay denied this exact request"}
        description={`Reason: ${view.decision.reason}. This is a StateWake resource/operation/state authorization result over an externally authenticated principal—not authentication, IAM, or business approval.`}
      />

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card className="sw-card" size="small" title="Principal + request context">
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="Principal identity"><span className="sw-machine">SHA-256 {view.principal.principal_id_digest}</span></Descriptions.Item>
              <Descriptions.Item label="Principal status">{view.principal.status}</Descriptions.Item>
              <Descriptions.Item label="Active at request">{view.principal.active_at_request ? "yes" : "no"}</Descriptions.Item>
              <Descriptions.Item label="Roles"><Space wrap>{view.principal.roles.map((role) => <Tag key={role}>{role}</Tag>)}</Space></Descriptions.Item>
              <Descriptions.Item label="Operation">{view.request.operation}</Descriptions.Item>
              <Descriptions.Item label="Resource state">{view.request.resource_state}</Descriptions.Item>
              <Descriptions.Item label="Requested at">{view.request.requested_at}</Descriptions.Item>
              <Descriptions.Item label="Resource identity">not exposed; SHA-256 digests only</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="sw-card" size="small" title="Evaluation trace">
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="Deny by default">yes</Descriptions.Item>
              <Descriptions.Item label="Principal active">{view.evaluation.principal_active ? "yes" : "no"}</Descriptions.Item>
              <Descriptions.Item label="Resource scope match">{view.evaluation.resource_scope_match ? "yes" : "no"}</Descriptions.Item>
              <Descriptions.Item label="Matching grants">{view.evaluation.matching_grant_count}</Descriptions.Item>
              <Descriptions.Item label="Policy replay">verified</Descriptions.Item>
              <Descriptions.Item label="Recorded decision">{view.evaluation.recorded_decision_present ? "present and replay-verified" : "not supplied"}</Descriptions.Item>
              <Descriptions.Item label="Result">{view.decision.allowed ? <Tag color="success">ALLOW</Tag> : <Tag color="error">DENY</Tag>}</Descriptions.Item>
              <Descriptions.Item label="Matched role">{view.decision.matched_role ?? "none"}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      <Card className="sw-card" size="small" title={`Least-privilege grants (${view.policy.grant_count})`}>
        <Table<Grant>
          rowKey={(item) => `${item.role}:${item.operation}:${item.allowed_states.join(",")}`}
          columns={grantColumns}
          dataSource={view.policy.grants}
          pagination={false}
          size="small"
          scroll={{ x: 720 }}
        />
      </Card>

      <Card className="sw-card" size="small" title={`Principal resource scopes (${view.principal.resource_scope_resource_count} resources)`}>
        <Table<Scope>
          rowKey="resource_domain_digest"
          columns={scopeColumns}
          dataSource={view.principal.resource_scopes}
          pagination={false}
          size="small"
          scroll={{ x: 760 }}
          expandable={{
            expandedRowRender: (scope) => (
              <Space direction="vertical" size={4}>
                {scope.resource_id_digests.map((digest) => <Typography.Text key={digest} className="sw-machine">{digest}</Typography.Text>)}
              </Space>
            ),
          }}
        />
      </Card>

      <Card className="sw-card" size="small" title="Authorization boundary">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Identity provider">external host</Descriptions.Item>
          <Descriptions.Item label="Principal authentication evaluated">no</Descriptions.Item>
          <Descriptions.Item label="Session validity evaluated">no</Descriptions.Item>
          <Descriptions.Item label="MFA evaluated">no</Descriptions.Item>
          <Descriptions.Item label="TLS evaluated">no</Descriptions.Item>
          <Descriptions.Item label="Tenant isolation evaluated">no</Descriptions.Item>
          <Descriptions.Item label="StateWake acting as IAM provider">no</Descriptions.Item>
          <Descriptions.Item label="Broader business authorization inferred">no</Descriptions.Item>
        </Descriptions>
      </Card>

      {view.limitations.map((item) => <Alert key={item} type="info" showIcon message={item} />)}
    </Space>
  );
}
