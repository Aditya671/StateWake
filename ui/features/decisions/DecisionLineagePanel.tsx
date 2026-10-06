"use client";

import {
  Alert,
  Card,
  Descriptions,
  Empty,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
  type TableColumnsType,
} from "antd";
import { useEffect, useState } from "react";
import { getDecisionLineage } from "@/lib/api/client";
import type {
  DecisionLineageInputView,
  DecisionLineageView,
} from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

function statusTag(value: string) {
  const color = ["verified", "reliable", "recovered", "accept", "resolved"].includes(value)
    ? "success"
    : ["review", "degraded", "medium"].includes(value)
      ? "warning"
      : value === "reject" || value === "unreliable" || value === "high"
        ? "error"
        : "default";
  return <Tag color={color}>{value}</Tag>;
}

export function DecisionLineagePanel() {
  const [data, setData] = useState<DecisionLineageView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getDecisionLineage(controller.signal)
      .then((value) => {
        setData(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setData(null);
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load reliability decision lineage",
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
    const unconfigured = error.code === "DECISION_LINEAGE_SOURCE_NOT_CONFIGURED";
    const oversized = error.code === "DECISION_LINEAGE_SOURCE_TOO_LARGE";
    return (
      <Alert
        type={unconfigured || oversized ? "warning" : "error"}
        showIcon
        message={
          unconfigured
            ? "Reliability decision chain is not configured"
            : oversized
              ? "Reliability decision evidence exceeds the configured read limit"
              : "Reliability decision evidence could not be verified"
        }
        description={error.message}
      />
    );
  }
  if (!data) return <Empty description="No reliability decision investigation is available." />;

  const inputColumns: TableColumnsType<DecisionLineageInputView> = [
    {
      title: "Digest",
      dataIndex: "digest",
      key: "digest",
      render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text>,
    },
    {
      title: "Semantic role",
      dataIndex: "semantic_roles",
      key: "semantic_roles",
      render: (values: string[]) => (
        <Space size={[4, 4]} wrap>{values.map((value) => <Tag key={value}>{value}</Tag>)}</Space>
      ),
    },
    {
      title: "Classification",
      dataIndex: "classification",
      key: "classification",
      width: 170,
      render: (value: string) => (
        <Tag color={value === "lineage-bound" ? "success" : "processing"}>{value}</Tag>
      ),
    },
    {
      title: "Run reachability",
      dataIndex: "reachable_to_run",
      key: "reachable_to_run",
      width: 150,
      render: (value: true | null) => value === true ? <Tag color="success">verified</Tag> : <Tag>not a graph node</Tag>,
    },
  ];

  const lineageColumns: TableColumnsType<DecisionLineageView["lineage"]["bindings"][number]> = [
    { title: "Role", dataIndex: "role", key: "role" },
    { title: "Node", dataIndex: "node_id", key: "node_id", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
    { title: "Identity", dataIndex: "identity", key: "identity", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
    { title: "SHA-256", dataIndex: "digest", key: "digest", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
    { title: "Reachable to run", dataIndex: "reachable_to_run", key: "reachable", width: 140, render: () => <Tag color="success">verified</Tag> },
  ];

  const comparisonColumns: TableColumnsType<{
    side: "before" | "after";
    role: string;
    kind: string;
    identity: string;
    digest: string;
  }> = [
    { title: "Side", dataIndex: "side", key: "side", width: 90, render: (value: string) => <Tag>{value}</Tag> },
    { title: "Role", dataIndex: "role", key: "role" },
    { title: "Kind", dataIndex: "kind", key: "kind" },
    { title: "Identity", dataIndex: "identity", key: "identity", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
    { title: "SHA-256", dataIndex: "digest", key: "digest", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
  ];

  const comparisonRows = data.comparison.present
    ? [
        ...data.comparison.before_inputs.map((item) => ({ ...item, side: "before" as const })),
        ...data.comparison.after_inputs.map((item) => ({ ...item, side: "after" as const })),
      ]
    : [];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Alert
        type="success"
        showIcon
        message="Decision evidence and lineage verified"
        description="StateWake verified the configured evidence chain, its material source digests, and provenance lineage. This establishes recorded bindings, not external factual correctness or business authorization."
      />

      <div className="sw-overview-grid">
        <Card className="sw-card" size="small">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Decision">{statusTag(data.chain.decision)}</Descriptions.Item>
            <Descriptions.Item label="Reliability">{statusTag(data.chain.reliability_state)}</Descriptions.Item>
          </Descriptions>
        </Card>
        <Card className="sw-card" size="small">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Decision basis">{data.decision_basis.present ? <Tag color="success">verified</Tag> : <Tag>not bound</Tag>}</Descriptions.Item>
            <Descriptions.Item label="Inputs">{data.decision_inputs.length}</Descriptions.Item>
          </Descriptions>
        </Card>
        <Card className="sw-card" size="small">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Reconciliation">{statusTag(data.chain.reconciliation_state)}</Descriptions.Item>
            <Descriptions.Item label="Binding">{data.reconciliation.present ? <Tag color="success">verified</Tag> : <Tag>not bound</Tag>}</Descriptions.Item>
          </Descriptions>
        </Card>
        <Card className="sw-card" size="small">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Lineage closure"><Tag color="success">verified</Tag></Descriptions.Item>
            <Descriptions.Item label="Bound nodes">{data.lineage.bindings.length}</Descriptions.Item>
          </Descriptions>
        </Card>
      </div>

      <Card className="sw-panel-card" bordered={false} title="Reliability decision">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Chain ID"><span className="sw-machine">{data.chain.chain_id}</span></Descriptions.Item>
          <Descriptions.Item label="Chain SHA-256"><span className="sw-machine">{data.chain.digest}</span></Descriptions.Item>
          <Descriptions.Item label="Verification status">{statusTag(data.chain.verification_status)}</Descriptions.Item>
          <Descriptions.Item label="Decision">{statusTag(data.chain.decision)}</Descriptions.Item>
          <Descriptions.Item label="Reliability state">{statusTag(data.chain.reliability_state)}</Descriptions.Item>
          <Descriptions.Item label="Reconciliation state">{statusTag(data.chain.reconciliation_state)}</Descriptions.Item>
          <Descriptions.Item label="Evidence references">{data.chain.evidence_count}</Descriptions.Item>
          <Descriptions.Item label="Rationale">{data.chain.rationale_count} recorded · intentionally not exposed here</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Decision basis">
        {!data.decision_basis.present ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No decision basis is bound to this chain." />
        ) : (
          <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Basis type">{data.decision_basis.basis_type}</Descriptions.Item>
            <Descriptions.Item label="Basis ID"><span className="sw-machine">{data.decision_basis.basis_id}</span></Descriptions.Item>
            <Descriptions.Item label="Version">{data.decision_basis.version}</Descriptions.Item>
            <Descriptions.Item label="Basis SHA-256"><span className="sw-machine">{data.decision_basis.digest}</span></Descriptions.Item>
            <Descriptions.Item label="Decision">{statusTag(data.decision_basis.decision)}</Descriptions.Item>
            <Descriptions.Item label="Reliability state">{statusTag(data.decision_basis.reliability_state)}</Descriptions.Item>
            <Descriptions.Item label="Bound inputs">{data.decision_basis.input_count}</Descriptions.Item>
            <Descriptions.Item label="Narrative rationale">{data.decision_basis.rationale_count} recorded · omitted from this projection</Descriptions.Item>
            {data.decision_basis.policy_id ? <Descriptions.Item label="Policy ID">{data.decision_basis.policy_id}</Descriptions.Item> : null}
            {data.decision_basis.policy_version ? <Descriptions.Item label="Policy version">{data.decision_basis.policy_version}</Descriptions.Item> : null}
            {data.decision_basis.policy_digest ? <Descriptions.Item label="Policy SHA-256"><span className="sw-machine">{data.decision_basis.policy_digest}</span></Descriptions.Item> : null}
          </Descriptions>
        )}
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Exact decision inputs">
        {data.decision_inputs.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No decision-basis inputs are recorded." />
        ) : (
          <Table
            rowKey={(item) => `${item.digest}:${item.semantic_roles.join(",")}`}
            size="small"
            pagination={false}
            dataSource={data.decision_inputs}
            columns={inputColumns}
            scroll={{ x: 1000 }}
          />
        )}
        <Alert
          style={{ marginTop: 12 }}
          type="info"
          showIcon
          message="Verification context is not fake graph lineage"
          description="Some verification artifacts can legitimately influence decision verification without being representable as provenance-graph nodes. Only lineage-bound inputs receive run-reachability claims."
        />
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Behavioral comparison">
        {!data.comparison.present ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No behavioral comparison is bound to this chain." />
        ) : (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
              <Descriptions.Item label="Comparison ID"><span className="sw-machine">{data.comparison.comparison_id}</span></Descriptions.Item>
              <Descriptions.Item label="Significance">{statusTag(data.comparison.significance)}</Descriptions.Item>
              <Descriptions.Item label="SHA-256"><span className="sw-machine">{data.comparison.digest}</span></Descriptions.Item>
              <Descriptions.Item label="Discrepancies">
                <Space size={[4, 4]} wrap>{data.comparison.discrepancies.map((value) => <Tag key={value}>{value}</Tag>)}</Space>
              </Descriptions.Item>
            </Descriptions>
            <Table
              rowKey={(item) => `${item.side}:${item.role}:${item.digest}`}
              size="small"
              pagination={false}
              dataSource={comparisonRows}
              columns={comparisonColumns}
              scroll={{ x: 980 }}
            />
          </Space>
        )}
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Reconciliation and recovery">
        {!data.reconciliation.present ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No discrepancy-to-reconciliation binding is recorded." />
        ) : (
          <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Resolution">{statusTag(data.reconciliation.resolution)}</Descriptions.Item>
            <Descriptions.Item label="Reconciliation status">{statusTag(data.reconciliation.reconciliation_status)}</Descriptions.Item>
            <Descriptions.Item label="Comparison ID"><span className="sw-machine">{data.reconciliation.comparison_id}</span></Descriptions.Item>
            <Descriptions.Item label="Reconciliation ID"><span className="sw-machine">{data.reconciliation.reconciliation_id}</span></Descriptions.Item>
            <Descriptions.Item label="Resolved discrepancies" span={2}>
              <Space size={[4, 4]} wrap>{data.reconciliation.resolved_discrepancies.map((value) => <Tag key={value}>{value}</Tag>)}</Space>
            </Descriptions.Item>
          </Descriptions>
        )}
        {data.recovery.present ? (
          <Alert
            style={{ marginTop: 12 }}
            type="success"
            showIcon
            message="Recovered outcome binding verified"
            description={`Recovery ${data.recovery.recovery_id} is bound to reconciliation ${data.recovery.reconciliation_id}. Recovery does not erase the earlier discrepancy.`}
          />
        ) : null}
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Provenance lineage closure">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }} style={{ marginBottom: 12 }}>
          <Descriptions.Item label="Graph SHA-256"><span className="sw-machine">{data.lineage.provenance_graph_digest}</span></Descriptions.Item>
          <Descriptions.Item label="Closure SHA-256"><span className="sw-machine">{data.lineage.closure_digest}</span></Descriptions.Item>
          <Descriptions.Item label="Run role">{data.lineage.run_role}</Descriptions.Item>
          <Descriptions.Item label="Reachable roles">{data.lineage.reachable_roles.length}</Descriptions.Item>
        </Descriptions>
        <Table
          rowKey={(item) => `${item.role}:${item.node_id}`}
          size="small"
          pagination={false}
          dataSource={data.lineage.bindings}
          columns={lineageColumns}
          scroll={{ x: 1040 }}
        />
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Verification and authority boundary">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Evidence chain"><Tag color="success">verified</Tag></Descriptions.Item>
          <Descriptions.Item label="Lineage closure"><Tag color="success">verified</Tag></Descriptions.Item>
          <Descriptions.Item label="Decision basis">{data.verification.decision_basis_verified ? <Tag color="success">verified</Tag> : <Tag>not bound</Tag>}</Descriptions.Item>
          <Descriptions.Item label="Comparison">{data.verification.comparison_verified ? <Tag color="success">verified</Tag> : <Tag>not bound</Tag>}</Descriptions.Item>
          <Descriptions.Item label="Reconciliation binding">{data.verification.reconciliation_binding_verified ? <Tag color="success">verified</Tag> : <Tag>not bound</Tag>}</Descriptions.Item>
          <Descriptions.Item label="Recovery outcome">{data.verification.recovery_outcome_verified ? <Tag color="success">verified</Tag> : <Tag>not applicable</Tag>}</Descriptions.Item>
          <Descriptions.Item label="Business authorization">not evaluated</Descriptions.Item>
          <Descriptions.Item label="Publication authority">not granted</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Boundaries and limitations">
        <Space direction="vertical" size={8}>
          {data.limitations.map((item) => <Typography.Text key={item}>• {item}</Typography.Text>)}
        </Space>
      </Card>
    </Space>
  );
}
