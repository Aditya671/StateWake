"use client";

import {
  Alert,
  Card,
  Descriptions,
  Empty,
  List,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { getReliabilityProofInvestigation } from "@/lib/api/client";
import type { ReliabilityProofInvestigationView } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

function formatStatus(value: string) {
  const color = value === "verified" ? "success" : value === "not-required-by-format" ? "default" : "warning";
  return <Tag color={color}>{value}</Tag>;
}

export function ReliabilityProofPanel() {
  const [data, setData] = useState<ReliabilityProofInvestigationView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getReliabilityProofInvestigation(controller.signal)
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
                "Unable to load the reliability proof bundle",
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

  if (loading) return <Skeleton active paragraph={{ rows: 12 }} />;
  if (error) {
    const unconfigured = error.code === "RELIABILITY_PROOF_SOURCE_NOT_CONFIGURED";
    const oversized = error.code === "RELIABILITY_PROOF_SOURCE_TOO_LARGE";
    return (
      <Alert
        type={unconfigured || oversized ? "warning" : "error"}
        showIcon
        message={
          unconfigured
            ? "Reliability proof bundle is not configured"
            : oversized
              ? "Reliability proof bundle exceeds the configured read limit"
              : "Reliability proof bundle could not be verified"
        }
        description={error.message}
      />
    );
  }
  if (!data) return <Empty description="No reliability proof investigation is available." />;

  const artifactColumns: ColumnsType<ReliabilityProofInvestigationView["artifacts"][number]> = [
    { title: "Artifact", dataIndex: "artifact_id", key: "artifact_id", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
    { title: "Kind", dataIndex: "kind", key: "kind" },
    { title: "Sensitivity", dataIndex: "sensitivity", key: "sensitivity", width: 120, render: (value: string) => <Tag>{value}</Tag> },
    { title: "Bytes", dataIndex: "size_bytes", key: "size_bytes", width: 100, render: (value: number) => value.toLocaleString() },
    { title: "SHA-256", dataIndex: "sha256", key: "sha256", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
  ];

  const sourceColumns: ColumnsType<ReliabilityProofInvestigationView["sources"][number]> = [
    { title: "Reference", dataIndex: "reference_key", key: "reference_key", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
    { title: "Source label", dataIndex: "source_label", key: "source_label" },
    { title: "Packaged artifact", dataIndex: "artifact_id", key: "artifact_id", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
    { title: "Bound digest", dataIndex: "bound_digest", key: "bound_digest", render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text> },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Alert
        type="success"
        showIcon
        message="Portable reliability proof verified offline"
        description="StateWake reproduced the packaged outcome verification from the bundle itself. This verifies the bounded proof relationships, not external factual correctness or human authorization."
      />

      <div className="sw-overview-grid">
        <Card className="sw-card" size="small"><Descriptions column={1} size="small"><Descriptions.Item label="Proof format">v{data.proof.format_version}</Descriptions.Item><Descriptions.Item label="Decision">{data.proof.decision}</Descriptions.Item></Descriptions></Card>
        <Card className="sw-card" size="small"><Descriptions column={1} size="small"><Descriptions.Item label="Outcome verification"><Tag color="success">verified</Tag></Descriptions.Item><Descriptions.Item label="Checks">{data.verification.checks.length}</Descriptions.Item></Descriptions></Card>
        <Card className="sw-card" size="small"><Descriptions column={1} size="small"><Descriptions.Item label="Lineage">{formatStatus(data.lineage.status)}</Descriptions.Item><Descriptions.Item label="Required">{data.lineage.required_by_format ? "yes" : "no"}</Descriptions.Item></Descriptions></Card>
        <Card className="sw-card" size="small"><Descriptions column={1} size="small"><Descriptions.Item label="Completeness">{formatStatus(data.completeness.status)}</Descriptions.Item><Descriptions.Item label="Required">{data.completeness.required_by_format ? "yes" : "no"}</Descriptions.Item></Descriptions></Card>
      </div>

      <Card className="sw-panel-card" bordered={false} title="Proof identity and outcome">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Bundle ID"><span className="sw-machine">{data.bundle.bundle_id}</span></Descriptions.Item>
          <Descriptions.Item label="Manifest ID"><span className="sw-machine">{data.bundle.manifest_id}</span></Descriptions.Item>
          <Descriptions.Item label="Subject">{data.proof.subject_id}</Descriptions.Item>
          <Descriptions.Item label="Reliability state">{data.proof.reliability_state}</Descriptions.Item>
          <Descriptions.Item label="Attestation ID"><span className="sw-machine">{data.proof.attestation_id}</span></Descriptions.Item>
          <Descriptions.Item label="Evidence chain ID"><span className="sw-machine">{data.proof.evidence_chain_id}</span></Descriptions.Item>
          <Descriptions.Item label="Transition ID"><span className="sw-machine">{data.proof.transition_id}</span></Descriptions.Item>
          <Descriptions.Item label="Descriptor SHA-256"><span className="sw-machine">{data.proof.descriptor_digest}</span></Descriptions.Item>
          <Descriptions.Item label="Artifact count">{data.bundle.artifact_count}</Descriptions.Item>
          <Descriptions.Item label="Built by StateWake">{data.bundle.engine_version}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Portable verification boundary">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Offline reverification">verified</Descriptions.Item>
          <Descriptions.Item label="Source set complete">yes</Descriptions.Item>
          <Descriptions.Item label="Lineage closure">{data.lineage.status}</Descriptions.Item>
          <Descriptions.Item label="Completeness witness">{data.completeness.status}</Descriptions.Item>
          <Descriptions.Item label="Trust context">{data.trust_context.present ? "present" : "not present"}</Descriptions.Item>
          <Descriptions.Item label="Portable crypto consistency">{data.trust_context.portable_cryptographic_consistency_verified ? "verified" : "not applicable"}</Descriptions.Item>
          <Descriptions.Item label="External authority trust">not established by packaged authority material</Descriptions.Item>
          <Descriptions.Item label="Publication/release authorization">not evaluated / not authorized</Descriptions.Item>
        </Descriptions>
        <Alert style={{ marginTop: 12 }} type="info" showIcon message={data.portable_dataset_boundary.note} />
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Packaged proof sources">
        {data.sources.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No material source references are recorded." /> : (
          <Table rowKey="reference_key" size="small" pagination={false} dataSource={data.sources} columns={sourceColumns} scroll={{ x: 920 }} />
        )}
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Proof artifacts">
        <Table rowKey="artifact_id" size="small" pagination={false} dataSource={data.artifacts} columns={artifactColumns} scroll={{ x: 980 }} />
      </Card>

      {data.trust_context.present ? (
        <Card className="sw-panel-card" bordered={false} title="Packaged attestation trust context">
          <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Signing key ID"><span className="sw-machine">{data.trust_context.signing_key_id}</span></Descriptions.Item>
            <Descriptions.Item label="Signing-key digest"><span className="sw-machine">{data.trust_context.signing_key_digest}</span></Descriptions.Item>
            <Descriptions.Item label="Trust-state version">{data.trust_context.trust_state_version}</Descriptions.Item>
            <Descriptions.Item label="Trust-state digest"><span className="sw-machine">{data.trust_context.trust_state_digest}</span></Descriptions.Item>
            <Descriptions.Item label="Authority key ID"><span className="sw-machine">{data.trust_context.authority_key_id}</span></Descriptions.Item>
            <Descriptions.Item label="Authority-key digest"><span className="sw-machine">{data.trust_context.authority_key_digest}</span></Descriptions.Item>
          </Descriptions>
        </Card>
      ) : null}

      <Card className="sw-panel-card" bordered={false} title="Verification checks">
        <List size="small" dataSource={data.verification.checks} renderItem={(item) => <List.Item><Tag color="success">verified</Tag>{item}</List.Item>} />
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Limitations">
        <List size="small" dataSource={data.limitations} renderItem={(item) => <List.Item>{item}</List.Item>} />
      </Card>
    </Space>
  );
}
