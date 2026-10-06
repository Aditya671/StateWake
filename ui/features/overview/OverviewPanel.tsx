"use client";

import { Alert, Card, Empty, List, Skeleton, Space, Typography } from "antd";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { StateFacet } from "@/components/StateFacet";
import { StateMetricCard } from "@/components/cards/StateWakeCards";
import { getOverview } from "@/lib/api/client";
import type { OverviewProjection } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

export function OverviewPanel() {
  const router = useRouter();
  const [overview, setOverview] = useState<OverviewProjection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getOverview(controller.signal)
      .then((value) => {
        setOverview(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof StateWakeApiError
            ? caught.message
            : "The StateWake overview could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  if (loading) {
    return <Skeleton active paragraph={{ rows: 5 }} />;
  }
  if (error) {
    return (
      <Alert
        type="warning"
        showIcon
        message="Workspace overview unavailable"
        description={`${error} Claim lookup remains available and no dashboard values are fabricated.`}
      />
    );
  }
  if (!overview) return null;

  const metric = overview.metrics;
  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <div className="sw-overview-grid">
        <StateMetricCard
          label="Reports evaluated"
          value={metric.reports_evaluated}
          helper={`Denominator: ${overview.scope.denominator} report records`}
          tone="info"
        />
        <StateMetricCard
          label="Human decisions pending"
          value={metric.human_decisions_pending}
          helper="Recorded approval/human-decision fields only"
          tone="warning"
        />
        <StateMetricCard
          label="Missing evidence"
          value={metric.reports_missing_evidence}
          helper="Reports with one or more missing evidence entries"
          tone="danger"
        />
        <StateMetricCard
          label="Verified reports"
          value={metric.verified_reports}
          helper="Recorded verified=true; not publication authorization"
          tone="success"
        />
      </div>

      <Card className="sw-panel-card" bordered={false} title="Recent verification reports">
        {overview.recent_reports.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No canonical verification reports are present in this workspace"
          />
        ) : (
          <List
            dataSource={overview.recent_reports}
            renderItem={(item) => (
              <List.Item
                className="sw-recent-report"
                onClick={() => router.push(`/claims/${item.record_id}`)}
              >
                <div className="sw-recent-main">
                  <Typography.Text strong>{item.claim}</Typography.Text>
                  <Typography.Text type="secondary" className="mono sw-machine">
                    {item.candidate.id}
                  </Typography.Text>
                </div>
                <Space wrap>
                  <StateFacet value={item.decision} />
                  <StateFacet value={item.verified ? "verified" : "unverified"} />
                  <StateFacet value={item.approval_status} />
                </Space>
              </List.Item>
            )}
          />
        )}
      </Card>

      <Typography.Text type="secondary" className="sw-overview-footnote">
        Scope: {overview.scope.resource} · deduplicated by {overview.scope.deduplication_key}
        {overview.as_of ? ` · as of ${overview.as_of}` : ""}. These are report counts, not a reliability score.
      </Typography.Text>
    </Space>
  );
}
