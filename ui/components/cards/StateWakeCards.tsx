"use client";

import { Card, Space, Tag, Typography } from "antd";
import type { ReactNode } from "react";
import { StateFacet } from "@/components/StateFacet";

export type CardTone = "neutral" | "success" | "warning" | "danger" | "info";

export function StateMetricCard({
  label,
  value,
  helper,
  tone = "neutral",
}: {
  label: string;
  value: number | string;
  helper?: string;
  tone?: CardTone;
}) {
  return (
    <Card className={`sw-metric-card sw-tone-${tone}`} bordered={false}>
      <div className="sw-metric-label">{label}</div>
      <div className="sw-metric-value">{value}</div>
      {helper ? <div className="sw-metric-helper">{helper}</div> : null}
    </Card>
  );
}

export function StateStatusCard({
  title,
  value,
  description,
  eyebrow,
  children,
}: {
  title: string;
  value: string;
  description?: string;
  eyebrow?: string;
  children?: ReactNode;
}) {
  return (
    <Card className="sw-status-card" bordered={false}>
      <Space direction="vertical" size={10} style={{ width: "100%" }}>
        {eyebrow ? <div className="sw-card-eyebrow">{eyebrow}</div> : null}
        <div className="sw-status-card-head">
          <Typography.Title level={4} style={{ margin: 0 }}>
            {title}
          </Typography.Title>
          <StateFacet value={value} />
        </div>
        {description ? (
          <Typography.Text type="secondary">{description}</Typography.Text>
        ) : null}
        {children}
      </Space>
    </Card>
  );
}

export function StateChecklistCard({
  title,
  items,
}: {
  title: string;
  items: Array<{ label: string; state: "success" | "warning" | "danger" | "neutral" }>;
}) {
  return (
    <Card className="sw-checklist-card" bordered={false} title={title}>
      <div className="sw-checklist">
        {items.map((item) => (
          <div className="sw-checklist-item" key={`${item.state}:${item.label}`}>
            <span className={`sw-state-dot sw-state-dot-${item.state}`} aria-hidden="true" />
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

export function StateIdentityCard({
  label,
  value,
  tag,
}: {
  label: string;
  value: string;
  tag?: string;
}) {
  return (
    <Card className="sw-identity-card" bordered={false}>
      <div className="sw-card-eyebrow">{label}</div>
      <Typography.Text className="mono sw-machine">{value}</Typography.Text>
      {tag ? <Tag className="sw-inline-tag">{tag}</Tag> : null}
    </Card>
  );
}
