"use client";

import { Alert, Card, Descriptions, Empty, List, Skeleton, Space, Table, Typography } from "antd";
import { useEffect, useState } from "react";
import { StateMetricCard, StateStatusCard, StateIdentityCard } from "@/components/cards/StateWakeCards";
import { getReleaseTrust } from "@/lib/api/client";
import type { ReleaseTrustView } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

function yesNoUnknown(value: boolean | null): string {
  if (value === null) return "not-verified";
  return value ? "verified" : "not-verified";
}

export function ReleaseTrustPanel() {
  const [data, setData] = useState<ReleaseTrustView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getReleaseTrust(controller.signal)
      .then((value) => {
        setData(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(caught instanceof StateWakeApiError ? caught.message : "Release trust data could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />;
  if (error) {
    return <Alert type="warning" showIcon message="Release trust not configured" description={`${error} No trust result is inferred.`} />;
  }
  if (!data) return null;

  const contentState = data.content_verification.complete === true ? "verified" : data.content_verification.complete === false ? "not-verified" : "undecided";
  const structuralState = data.structural_profile.satisfied ? "verified" : "not-verified";
  const signatureState = yesNoUnknown(data.signature_authenticity.authenticated);
  const decisionState = data.human_decision.decision || "undecided";
  const publicationState = data.release_published ? "verified" : "undecided";

  return (
    <Space direction="vertical" size={18} style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        message="Trust signals remain independent"
        description="Structural completeness, local byte verification, signer authenticity, human release decision, and publication authorization are displayed separately. StateWake does not collapse them into a single trust score."
      />

      <div className="sw-overview-grid">
        <StateStatusCard title="Structural profile" value={structuralState} eyebrow="Release evidence">
          <Typography.Text type="secondary">{data.structural_profile.profile_id} · v{data.structural_profile.profile_version}</Typography.Text>
        </StateStatusCard>
        <StateStatusCard title="Release bytes" value={contentState} eyebrow="Independent content check">
          <Typography.Text type="secondary">{data.content_verification.status}</Typography.Text>
        </StateStatusCard>
        <StateStatusCard title="Signer authenticity" value={signatureState} eyebrow="Identity verification">
          <Typography.Text type="secondary">{data.signature_authenticity.status}</Typography.Text>
        </StateStatusCard>
        <StateStatusCard title="Human decision" value={decisionState} eyebrow="Publication decision">
          <Typography.Text type="secondary">Publication authorized: {data.publication_authorized ? "yes" : "no"}</Typography.Text>
        </StateStatusCard>
        <StateStatusCard title="Registry publication" value={publicationState} eyebrow="Post-publication read-back">
          <Typography.Text type="secondary">Public bytes reconciled: {data.registry_publication.public_bytes_verified ? "yes" : "no"}</Typography.Text>
        </StateStatusCard>
      </div>

      <div className="sw-grid">
        <StateIdentityCard label="Release bundle digest" value={data.bundle_digest} tag={`${data.source.distribution} ${data.source.version}`} />
        <StateIdentityCard label="Source tree SHA-256" value={data.source.source_tree_sha256} tag={data.source.source_revision} />
      </div>

      <div className="sw-summary-grid">
        <StateMetricCard label="Artifacts" value={data.artifacts.length} helper="Declared release artifacts" tone="info" />
        <StateMetricCard label="Matched bytes" value={data.content_verification.matched.length} helper="Local digest matches" tone="success" />
        <StateMetricCard label="Missing bytes" value={data.content_verification.missing.length} helper="Configured release root only" tone={data.content_verification.missing.length ? "warning" : "neutral"} />
        <StateMetricCard label="Mismatches" value={data.content_verification.mismatched.length} helper="Digest mismatches" tone={data.content_verification.mismatched.length ? "danger" : "neutral"} />
      </div>

      <Card className="sw-panel-card" bordered={false} title="Release artifacts">
        <Table
          rowKey={(row) => `${row.name}:${row.sha256}`}
          pagination={false}
          dataSource={data.artifacts}
          columns={[
            { title: "Artifact", dataIndex: "name" },
            { title: "Media type", dataIndex: "media_type" },
            { title: "Bytes", dataIndex: "size_bytes", render: (value: number) => value.toLocaleString() },
            { title: "SHA-256", dataIndex: "sha256", render: (value: string) => <Typography.Text className="mono sw-machine">{value}</Typography.Text> },
          ]}
          scroll={{ x: 880 }}
        />
      </Card>

      <div className="sw-grid">
        <Card className="sw-panel-card" bordered={false} title="Structural profile details">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Satisfied">{data.structural_profile.satisfied ? "yes" : "no"}</Descriptions.Item>
            <Descriptions.Item label="Failed requirements">{data.structural_profile.failed_requirements.length || "none"}</Descriptions.Item>
            <Descriptions.Item label="Missing evidence">{data.structural_profile.missing_evidence.length || "none"}</Descriptions.Item>
          </Descriptions>
          {data.structural_profile.caveats.length ? <List size="small" dataSource={data.structural_profile.caveats} renderItem={(item) => <List.Item>{item}</List.Item>} /> : null}
        </Card>
        <Card className="sw-panel-card" bordered={false} title="Human release decision">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Actor">{data.human_decision.actor_ref || "not recorded"}</Descriptions.Item>
            <Descriptions.Item label="Role">{data.human_decision.role || "not recorded"}</Descriptions.Item>
            <Descriptions.Item label="Decision">{data.human_decision.decision || "not recorded"}</Descriptions.Item>
            <Descriptions.Item label="Scope">{data.human_decision.scope || "not recorded"}</Descriptions.Item>
            <Descriptions.Item label="Decided at">{data.human_decision.decided_at ?? "not recorded"}</Descriptions.Item>
          </Descriptions>
        </Card>
      </div>

      <Card className="sw-panel-card" bordered={false} title="Publication authorization boundary">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="Configured">{data.publication_authorization.configured ? "yes" : "no"}</Descriptions.Item>
          <Descriptions.Item label="Target repository">{data.publication_authorization.target_repository ?? "not configured"}</Descriptions.Item>
          <Descriptions.Item label="Authorized">{data.publication_authorized ? "yes" : "no"}</Descriptions.Item>
          <Descriptions.Item label="Active approvals">{data.publication_authorization.active_approval_receipt_ids.length}</Descriptions.Item>
          <Descriptions.Item label="Execution">external protected workflow only</Descriptions.Item>
        </Descriptions>
        {data.publication_authorization.items.length ? (
          <Table
            rowKey={(row) => row.approval_receipt_id}
            pagination={false}
            dataSource={data.publication_authorization.items}
            columns={[
              { title: "Status", dataIndex: "status" },
              { title: "Actor", dataIndex: "actor_identity_ref" },
              { title: "Role", dataIndex: "role" },
              { title: "Captured", dataIndex: "captured_at" },
              { title: "Approval receipt", dataIndex: "approval_receipt_id", render: (value: string) => <Typography.Text className="mono sw-machine">{value}</Typography.Text> },
            ]}
            scroll={{ x: 980 }}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No canonical publication approval lifecycle configured" />
        )}
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          This surface is read-only. Authorization permits a separate protected publication workflow; it does not publish a package and does not prove registry acceptance.
        </Typography.Paragraph>
      </Card>


      <Card className="sw-panel-card" bordered={false} title="Registry publication reconciliation">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="Configured">{data.registry_publication.configured ? "yes" : "no"}</Descriptions.Item>
          <Descriptions.Item label="Published">{data.release_published ? "yes" : "no"}</Descriptions.Item>
          <Descriptions.Item label="Registry reconciled">{data.registry_publication.registry_reconciled ? "yes" : "no"}</Descriptions.Item>
          <Descriptions.Item label="Public bytes verified">{data.registry_publication.public_bytes_verified ? "yes" : "no"}</Descriptions.Item>
          <Descriptions.Item label="Target repository">{data.registry_publication.target_repository ?? "not configured"}</Descriptions.Item>
          <Descriptions.Item label="Observed at">{data.registry_publication.observed_at ?? "not observed"}</Descriptions.Item>
          <Descriptions.Item label="Receipt digest">
            {data.registry_publication.receipt_digest ? <Typography.Text className="mono sw-machine">{data.registry_publication.receipt_digest}</Typography.Text> : "not recorded"}
          </Descriptions.Item>
        </Descriptions>
        {data.registry_publication.artifacts.length ? (
          <Table
            rowKey={(row) => `${row.name}:${row.sha256}`}
            pagination={false}
            dataSource={data.registry_publication.artifacts}
            columns={[
              { title: "Artifact", dataIndex: "name" },
              { title: "Type", dataIndex: "package_type" },
              { title: "Bytes", dataIndex: "size_bytes", render: (value: number) => value.toLocaleString() },
              { title: "Yanked", dataIndex: "yanked", render: (value: boolean) => (value ? "yes" : "no") },
              { title: "SHA-256", dataIndex: "sha256", render: (value: string) => <Typography.Text className="mono sw-machine">{value}</Typography.Text> },
            ]}
            scroll={{ x: 980 }}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No canonical post-publication registry receipt configured" />
        )}
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 12 }}>
          Registry publication is shown only after StateWake independently reads the registry metadata and public distribution bytes back and matches them to the exact execution permit. The immutable publication receipt is not rewritten by later registry changes.
        </Typography.Paragraph>
        <Descriptions column={1} size="small" title="Registry lifecycle">
          <Descriptions.Item label="Lifecycle configured">{data.registry_publication.lifecycle.configured ? "yes" : "no"}</Descriptions.Item>
          <Descriptions.Item label="Current status">{data.registry_publication.lifecycle.current_status ?? "not observed"}</Descriptions.Item>
          <Descriptions.Item label="Current observed at">{data.registry_publication.lifecycle.current_observed_at ?? "not observed"}</Descriptions.Item>
          <Descriptions.Item label="Default install eligible">
            {data.registry_publication.lifecycle.default_install_eligible === null ? "unknown" : data.registry_publication.lifecycle.default_install_eligible ? "yes" : "no"}
          </Descriptions.Item>
          <Descriptions.Item label="Complete public bytes verified">
            {data.registry_publication.lifecycle.public_bytes_verified === null ? "unknown" : data.registry_publication.lifecycle.public_bytes_verified ? "yes" : "no"}
          </Descriptions.Item>
          <Descriptions.Item label="Missing artifacts">
            {data.registry_publication.lifecycle.missing_artifacts.length ? data.registry_publication.lifecycle.missing_artifacts.join(", ") : "none"}
          </Descriptions.Item>
        </Descriptions>
        {data.registry_publication.lifecycle.observations.length ? (
          <Table
            rowKey="observation_digest"
            pagination={false}
            dataSource={data.registry_publication.lifecycle.observations}
            columns={[
              { title: "Observed", dataIndex: "observed_at" },
              { title: "Status", dataIndex: "status" },
              { title: "Missing", dataIndex: "missing_artifacts", render: (value: string[]) => (value.length ? value.join(", ") : "none") },
              { title: "Registry entry", dataIndex: "registry_entry_present", render: (value: boolean) => (value ? "present" : "absent") },
              { title: "Install eligible", dataIndex: "default_install_eligible", render: (value: boolean) => (value ? "yes" : "no") },
              { title: "Observation digest", dataIndex: "observation_digest", render: (value: string) => <Typography.Text className="mono sw-machine">{value}</Typography.Text> },
            ]}
            scroll={{ x: 1100 }}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No registry lifecycle observations recorded" />
        )}
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          Yank, unyank, partial file removal, and release disappearance are recorded as append-only observations. StateWake reports observed registry state and does not infer who changed it or why.
        </Typography.Paragraph>
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Signer authenticity">
        <Typography.Paragraph>{data.signature_authenticity.reason}</Typography.Paragraph>
        {data.external_evidence.signature === null ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No signature evidence recorded" /> : <pre className="sw-raw">{JSON.stringify(data.external_evidence.signature, null, 2)}</pre>}
      </Card>

      <Card className="sw-panel-card" bordered={false} title="Limitations">
        <List size="small" dataSource={[...data.content_verification.limitations, ...data.limitations]} renderItem={(item) => <List.Item>{item}</List.Item>} />
      </Card>
    </Space>
  );
}
