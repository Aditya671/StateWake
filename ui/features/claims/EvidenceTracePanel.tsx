"use client";

import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getEvidenceTrace } from "@/lib/api/client";
import type {
  EvidenceTrace,
  EvidenceTraceEdge,
  EvidenceTraceNode,
} from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

function short(value: string): string {
  return value.length > 18 ? `${value.slice(0, 10)}…${value.slice(-6)}` : value;
}

function RelationshipMap({ trace }: { trace: EvidenceTrace }) {
  const nodes = trace.nodes.slice(0, 24);
  const positions = new Map(
    nodes.map((node, index) => {
      const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
      const radius = nodes.length <= 6 ? 126 : 158;
      return [
        node.node_id,
        { x: 360 + Math.cos(angle) * radius, y: 210 + Math.sin(angle) * radius },
      ] as const;
    }),
  );
  const edges = trace.edges.filter(
    (edge) => positions.has(edge.source) && positions.has(edge.target),
  );

  if (nodes.length === 0) {
    return <Empty description="No recorded evidence nodes" />;
  }
  return (
    <div className="sw-evidence-map-wrap">
      <svg
        className="sw-evidence-map"
        viewBox="0 0 720 420"
        role="img"
        aria-label={`Relationship overview with ${nodes.length} nodes and ${edges.length} visible edges. Full relationships are listed in the accessible table below.`}
      >
        {edges.map((edge) => {
          const source = positions.get(edge.source);
          const target = positions.get(edge.target);
          if (!source || !target) return null;
          return (
            <line
              key={edge.edge_id}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              className="sw-evidence-edge"
            />
          );
        })}
        {nodes.map((node) => {
          const position = positions.get(node.node_id);
          if (!position) return null;
          return (
            <g key={node.node_id} transform={`translate(${position.x} ${position.y})`}>
              <circle r="34" className={`sw-evidence-node sw-evidence-node-${node.kind}`} />
              <text textAnchor="middle" y="4" className="sw-evidence-node-label">
                {node.kind === "verification-report" ? "report" : node.kind.split("-")[0]}
              </text>
            </g>
          );
        })}
      </svg>
      {trace.nodes.length > nodes.length && (
        <Typography.Text type="secondary">
          Visual overview is capped at 24 nodes; the relationship table contains the complete bounded response.
        </Typography.Text>
      )}
    </div>
  );
}

export function EvidenceTracePanel({ recordId, active }: { recordId: string; active: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const [trace, setTrace] = useState<EvidenceTrace | null>(null);
  const [error, setError] = useState<StateWakeApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<EvidenceTraceNode | null>(null);

  useEffect(() => {
    if (!active || trace !== null) return;
    const controller = new AbortController();
    setLoading(true);
    getEvidenceTrace(recordId, controller.signal)
      .then((value) => {
        setTrace(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load evidence trace",
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
  }, [active, recordId, trace]);

  const nodesById = useMemo(
    () => new Map((trace?.nodes ?? []).map((node) => [node.node_id, node])),
    [trace],
  );
  const columns: TableColumnsType<EvidenceTraceEdge> = [
    {
      title: "Source",
      dataIndex: "source",
      render: (value: string) => {
        const node = nodesById.get(value);
        return node ? (
          <Button type="link" onClick={() => setSelectedNode(node)}>
            {node.label}: {short(node.identity)}
          </Button>
        ) : (
          short(value)
        );
      },
    },
    { title: "Relationship", dataIndex: "relationship_type" },
    {
      title: "Target",
      dataIndex: "target",
      render: (value: string) => {
        const node = nodesById.get(value);
        return node ? (
          <Button type="link" onClick={() => setSelectedNode(node)}>
            {node.label}: {short(node.identity)}
          </Button>
        ) : (
          short(value)
        );
      },
    },
    { title: "Recorded basis", dataIndex: "basis", responsive: ["md"] },
    { title: "Count", dataIndex: "occurrences", width: 82 },
  ];

  if (!active) return null;
  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />;
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="Evidence trace unavailable"
        description={`${error.code}: ${error.message}`}
      />
    );
  }
  if (!trace) return <Empty description="Evidence trace not loaded" />;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Space wrap>
        <Button onClick={() => router.push(`${pathname}?tab=history`)}>Open history</Button>
        <Button onClick={() => router.push(`/compare?left=${encodeURIComponent(recordId)}`)}>
          Compare this report
        </Button>
        <Tag>{trace.nodes.length} nodes</Tag>
        <Tag>{trace.edges.length} relationships</Tag>
        <Tag>{trace.unresolved.length} unresolved</Tag>
      </Space>

      <div className="sw-summary-grid">
        <Card size="small" className="sw-card" title="Receipt integrity">
          <Typography.Title level={3} style={{ margin: 0 }}>
            {trace.assurance_summary.receipt_integrity_verified}/{trace.assurance_summary.receipts_resolved}
          </Typography.Title>
          <Typography.Text type="secondary">
            Canonical receipts whose deterministic identity and digest parsed successfully.
          </Typography.Text>
        </Card>
        <Card size="small" className="sw-card" title="Artifact bytes">
          <Typography.Title level={3} style={{ margin: 0 }}>
            {trace.assurance_summary.artifact_integrity_verified}/{trace.assurance_summary.receipts_resolved}
          </Typography.Title>
          <Typography.Text type="secondary">
            Content-addressed artifacts re-read and verified against their recorded SHA-256.
          </Typography.Text>
        </Card>
        <Card size="small" className="sw-card" title="Admission binding">
          <Typography.Title level={3} style={{ margin: 0 }}>
            {trace.assurance_summary.admission_verified}/{trace.assurance_summary.receipts_resolved}
          </Typography.Title>
          <Typography.Text type="secondary">
            Receipts whose persisted receipt and artifact satisfy the canonical admission contract.
          </Typography.Text>
        </Card>
        <Card size="small" className="sw-card" title="Producer authentication">
          <Tag>not recorded</Tag>
          <Typography.Paragraph type="secondary" style={{ marginTop: 10, marginBottom: 0 }}>
            Producer identity is recorded, but detached signatures and independent producer trust keys are not persisted in this workspace view.
          </Typography.Paragraph>
        </Card>
      </div>

      <Alert
        type="info"
        showIcon
        message="Producer authenticity is outside this workspace projection"
        description={trace.producer_authentication.reason}
      />

      {!trace.workspace_scan.complete && (
        <Alert
          type="warning"
          showIcon
          message="Workspace resolution is partial"
          description={`Inspected ${trace.workspace_scan.records_scanned} receipt records from ${trace.workspace_scan.records_available} available receipts within the configured bound. Unresolved identities are not evidence of absence.`}
        />
      )}
      {trace.unresolved.length > 0 && (
        <Card className="sw-card" size="small" title="Unresolved or explicitly missing evidence">
          <Table
            rowKey={(item) => `${item.kind}:${item.identity}`}
            pagination={false}
            size="small"
            dataSource={trace.unresolved}
            columns={[
              { title: "Kind", dataIndex: "kind" },
              { title: "Identity", dataIndex: "identity", render: (value) => <span className="sw-machine">{value}</span> },
              { title: "Reason", dataIndex: "reason" },
            ]}
            scroll={{ x: 720 }}
          />
        </Card>
      )}

      <Card className="sw-card" title="Recorded relationship overview">
        <RelationshipMap trace={trace} />
      </Card>

      <Card className="sw-card" title="Relationship table">
        <Table
          rowKey="edge_id"
          pagination={{ pageSize: 12, hideOnSinglePage: true }}
          size="small"
          dataSource={trace.edges}
          columns={columns}
          scroll={{ x: 900 }}
        />
      </Card>

      <Alert
        type="info"
        showIcon
        message="Interpretation boundary"
        description={trace.limitations.join(" ")}
      />

      <Drawer
        open={selectedNode !== null}
        onClose={() => setSelectedNode(null)}
        title={selectedNode?.label ?? "Evidence node"}
        width={520}
      >
        {selectedNode && (
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="Kind">{selectedNode.kind}</Descriptions.Item>
            <Descriptions.Item label="Identity">
              <span className="sw-machine">{selectedNode.identity}</span>
            </Descriptions.Item>
            <Descriptions.Item label="Integrity">{selectedNode.integrity_status}</Descriptions.Item>
            <Descriptions.Item label="Availability">{selectedNode.availability}</Descriptions.Item>
            {selectedNode.receipt_integrity_status && (
              <Descriptions.Item label="Receipt integrity">
                <Tag>{selectedNode.receipt_integrity_status}</Tag>
              </Descriptions.Item>
            )}
            {selectedNode.artifact_integrity_status && (
              <Descriptions.Item label="Artifact integrity">
                <Tag>{selectedNode.artifact_integrity_status}</Tag>
              </Descriptions.Item>
            )}
            {selectedNode.admission_status && (
              <Descriptions.Item label="Admission">
                <Tag>{selectedNode.admission_status}</Tag>
              </Descriptions.Item>
            )}
            {selectedNode.producer_authentication_status && (
              <Descriptions.Item label="Producer authentication">
                <Tag>{selectedNode.producer_authentication_status}</Tag>
              </Descriptions.Item>
            )}
            {selectedNode.digest && (
              <Descriptions.Item label={selectedNode.digest_kind ?? "Digest"}>
                <span className="sw-machine">{selectedNode.digest}</span>
              </Descriptions.Item>
            )}
            {selectedNode.receipt_digest && (
              <Descriptions.Item label="Receipt digest">
                <span className="sw-machine">{selectedNode.receipt_digest}</span>
              </Descriptions.Item>
            )}
            {selectedNode.admission_digest && (
              <Descriptions.Item label="Admission digest">
                <span className="sw-machine">{selectedNode.admission_digest}</span>
              </Descriptions.Item>
            )}
            {selectedNode.producer_id && (
              <Descriptions.Item label="Producer">{selectedNode.producer_id}</Descriptions.Item>
            )}
            {selectedNode.producer_type && (
              <Descriptions.Item label="Producer type">{selectedNode.producer_type}</Descriptions.Item>
            )}
            {selectedNode.run_id && (
              <Descriptions.Item label="Run"><span className="sw-machine">{selectedNode.run_id}</span></Descriptions.Item>
            )}
            {selectedNode.source_event_id && (
              <Descriptions.Item label="Source event"><span className="sw-machine">{selectedNode.source_event_id}</span></Descriptions.Item>
            )}
            {selectedNode.captured_at && (
              <Descriptions.Item label="Captured at">{selectedNode.captured_at}</Descriptions.Item>
            )}
            {selectedNode.artifact_size !== null && (
              <Descriptions.Item label="Artifact bytes">{selectedNode.artifact_size}</Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Drawer>
    </Space>
  );
}
