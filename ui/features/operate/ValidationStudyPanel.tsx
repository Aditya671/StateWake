"use client";

import { Alert, Card, Descriptions, List, Skeleton, Space, Table, Typography } from "antd";
import { useEffect, useState } from "react";
import { StateIdentityCard, StateMetricCard } from "@/components/cards/StateWakeCards";
import { getValidationStudy } from "@/lib/api/client";
import type { ValidationStudyView } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function ValidationStudyPanel() {
  const [data, setData] = useState<ValidationStudyView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getValidationStudy(controller.signal)
      .then((value) => {
        setData(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(caught instanceof StateWakeApiError ? caught.message : "Validation study could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />;
  if (error) return <Alert type="warning" showIcon message="Validation study not configured" description={`${error} No benchmark result is inferred.`} />;
  if (!data) return null;

  const injected = data.metrics.reduce((sum, metric) => sum + metric.injected_fault_count, 0);
  const detected = data.metrics.reduce((sum, metric) => sum + metric.detected_fault_count, 0);
  const falsePositives = data.metrics.reduce((sum, metric) => sum + metric.false_positive_count, 0);

  return (
    <Space direction="vertical" size={18} style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        message="Recorded deterministic fixture study"
        description="This page displays a frozen comparative study. It does not execute a live benchmark and does not generalize these results beyond the recorded fixtures, workloads, baselines, and injected faults."
      />

      <div className="sw-overview-grid">
        <StateMetricCard label="Study cases" value={data.case_count} helper="Frozen recorded cases" tone="info" />
        <StateMetricCard label="Baselines" value={data.baselines.length} helper="Compared configurations" />
        <StateMetricCard label="Injected faults" value={injected} helper={`${detected} detected by recorded checks`} tone="warning" />
        <StateMetricCard label="False positives" value={falsePositives} helper="Across valid-case denominators" tone={falsePositives ? "danger" : "success"} />
      </div>

      <div className="sw-grid">
        <StateIdentityCard label="Study ID" value={data.study_id} tag={data.study_kind} />
        <StateIdentityCard label="Study digest" value={data.study_digest} />
      </div>

      <Card className="sw-panel-card" bordered={false} title="Comparative metrics">
        <Table
          rowKey={(row) => row.baseline}
          pagination={false}
          dataSource={data.metrics}
          scroll={{ x: 1050 }}
          columns={[
            { title: "Baseline", dataIndex: "baseline" },
            { title: "Cases", dataIndex: "case_count" },
            {
              title: "Verification coverage",
              render: (_, row) => <span>{percent(row.verification_coverage)} <Typography.Text type="secondary">({row.checkable_property_count}/{row.verification_coverage_denominator})</Typography.Text></span>,
            },
            {
              title: "Fault detection",
              render: (_, row) => <span>{percent(row.fault_detection_rate)} <Typography.Text type="secondary">({row.detected_fault_count}/{row.fault_detection_denominator})</Typography.Text></span>,
            },
            {
              title: "False positive rate",
              render: (_, row) => <span>{percent(row.false_positive_rate)} <Typography.Text type="secondary">({row.false_positive_count}/{row.false_positive_denominator})</Typography.Text></span>,
            },
          ]}
        />
      </Card>

      <div className="sw-grid">
        <Card className="sw-panel-card" bordered={false} title="Study scope">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Workloads">{data.workloads.length}</Descriptions.Item>
            <Descriptions.Item label="Fault definitions">{data.faults.length}</Descriptions.Item>
            <Descriptions.Item label="Recorded cases">{data.case_count}</Descriptions.Item>
            <Descriptions.Item label="Study type">{data.study_kind}</Descriptions.Item>
          </Descriptions>
        </Card>
        <Card className="sw-panel-card" bordered={false} title="Limitations">
          <List size="small" dataSource={data.limitations} renderItem={(item) => <List.Item>{item}</List.Item>} />
        </Card>
      </div>
    </Space>
  );
}
