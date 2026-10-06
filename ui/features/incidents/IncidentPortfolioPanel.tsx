"use client";

import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Grid,
  Input,
  List,
  Pagination,
  Row,
  Select,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  getIncidentPortfolio,
  type IncidentPortfolioRequest,
} from "@/lib/api/client";
import type { IncidentPortfolio, IncidentPortfolioItem } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

interface IncidentFilters {
  text?: string;
  status?: string;
  category?: string;
}

const DEFAULT_PAGE_SIZE = 25;
const STATUS_OPTIONS = [
  "detected",
  "preserved",
  "contained",
  "assessed",
  "recovered",
  "reverified",
].map((value) => ({ value, label: value }));

function statusTag(status: string) {
  const color = status === "reverified" ? "success" : status === "recovered" ? "processing" : "warning";
  return <Tag color={color}>{status}</Tag>;
}

function IncidentCard({ item, onOpen }: { item: IncidentPortfolioItem; onOpen: () => void }) {
  return (
    <Card size="small" className="sw-card">
      <Space direction="vertical" size={10} style={{ width: "100%" }}>
        <Space wrap>
          {statusTag(item.status)}
          {item.recovery.recorded && <Tag>recovery {item.recovery.status}</Tag>}
          {item.forensic_continuity_verified && <Tag color="success">forensic continuity verified</Tag>}
        </Space>
        <Typography.Text strong>{item.category}</Typography.Text>
        <Typography.Text className="sw-machine" type="secondary">
          {item.incident_id}
        </Typography.Text>
        <Typography.Text type="secondary">
          {item.observation_count} observations · {item.evidence_ref_count} evidence refs · {item.affected_state_count} affected states
        </Typography.Text>
        <Typography.Text type="secondary">
          Latest observation {item.latest_recorded_at}
        </Typography.Text>
        <Button type="link" style={{ paddingInline: 0 }} onClick={onOpen}>
          Investigate incident
        </Button>
      </Space>
    </Card>
  );
}

export function IncidentPortfolioPanel() {
  const router = useRouter();
  const screens = Grid.useBreakpoint();
  const [form] = Form.useForm<IncidentFilters>();
  const [filters, setFilters] = useState<IncidentFilters>({});
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [portfolio, setPortfolio] = useState<IncidentPortfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const request: IncidentPortfolioRequest = { limit: pageSize, offset };
    if (filters.status) request.status = filters.status;
    if (filters.category) request.category = filters.category;
    if (filters.text) request.text = filters.text;
    setLoading(true);
    setError(null);
    getIncidentPortfolio(request, controller.signal)
      .then((value) => {
        if (value.items.length === 0 && value.scope.matched_incidents > 0 && value.page.offset > 0) {
          setPortfolio(null);
          setOffset(0);
          return;
        }
        setPortfolio(value);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setPortfolio(null);
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load incident evidence",
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

  const columns = useMemo<ColumnsType<IncidentPortfolioItem>>(
    () => [
      {
        title: "Incident",
        key: "incident",
        render: (_value, item) => (
          <Space direction="vertical" size={2}>
            <Button
              type="link"
              style={{ paddingInline: 0 }}
              onClick={() => router.push(`/incidents/${item.incident_id}`)}
            >
              {item.category}
            </Button>
            <Typography.Text type="secondary" className="sw-machine">
              {item.incident_id}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: "Status",
        dataIndex: "status",
        key: "status",
        width: 125,
        render: (value: string) => statusTag(value),
      },
      {
        title: "Recovery",
        key: "recovery",
        width: 180,
        render: (_value, item) => (
          <Space direction="vertical" size={2}>
            <Typography.Text>{item.recovery.recorded ? item.recovery.status : "not recorded"}</Typography.Text>
            {item.forensic_continuity_verified && (
              <Typography.Text type="success">post-recovery verified</Typography.Text>
            )}
          </Space>
        ),
      },
      {
        title: "Evidence",
        key: "evidence",
        width: 160,
        render: (_value, item) => (
          <Typography.Text type="secondary">
            refs {item.evidence_ref_count} · states {item.affected_state_count}
          </Typography.Text>
        ),
      },
      {
        title: "Latest observation",
        dataIndex: "latest_recorded_at",
        key: "latest_recorded_at",
        width: 215,
      },
    ],
    [router],
  );

  const applyFilters = (values: IncidentFilters) => {
    const next: IncidentFilters = {};
    if (values.text?.trim()) next.text = values.text.trim();
    if (values.status) next.status = values.status;
    if (values.category?.trim()) next.category = values.category.trim();
    setFilters(next);
    setOffset(0);
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card className="sw-card" size="small" title="Investigate recorded incidents">
        <Form<IncidentFilters> form={form} layout="vertical" onFinish={applyFilters}>
          <Row gutter={12}>
            <Col xs={24} lg={10}>
              <Form.Item label="Search" name="text" rules={[{ max: 200 }]}>
                <Input
                  allowClear
                  autoComplete="off"
                  placeholder="Incident ID, event ID, actor, category, or status"
                />
              </Form.Item>
            </Col>
            <Col xs={12} lg={6}>
              <Form.Item label="Status" name="status">
                <Select allowClear options={STATUS_OPTIONS} />
              </Form.Item>
            </Col>
            <Col xs={12} lg={8}>
              <Form.Item label="Category" name="category" rules={[{ max: 256 }]}>
                <Input allowClear autoComplete="off" placeholder="Exact recorded category" />
              </Form.Item>
            </Col>
          </Row>
          <Space wrap>
            <Button type="primary" htmlType="submit">Apply filters</Button>
            <Button
              onClick={() => {
                form.resetFields();
                setFilters({});
                setOffset(0);
              }}
            >
              Clear
            </Button>
          </Space>
        </Form>
      </Card>

      {loading && <Skeleton active paragraph={{ rows: 6 }} />}

      {!loading && error && (
        <Alert
          type={error.code === "INCIDENT_SOURCE_NOT_CONFIGURED" ? "info" : "error"}
          showIcon
          message={
            error.code === "INCIDENT_SOURCE_NOT_CONFIGURED"
              ? "Incident evidence is not configured"
              : "Incident investigation is unavailable"
          }
          description={error.message}
        />
      )}

      {!loading && !error && portfolio && portfolio.scope.total_incidents === 0 && (
        <Empty description="No canonical incident evidence has been recorded." />
      )}

      {!loading && !error && portfolio && portfolio.scope.total_incidents > 0 && portfolio.scope.matched_incidents === 0 && (
        <Empty description="No recorded incidents match the current filters." />
      )}

      {!loading && !error && portfolio && portfolio.items.length > 0 && (
        <>
          <Card className="sw-card" size="small">
            <Space wrap>
              <Typography.Text strong>{portfolio.scope.matched_incidents} matching incidents</Typography.Text>
              <Typography.Text type="secondary">
                {portfolio.scope.store_records} verified store records · {portfolio.scope.total_incidents} incident identities
              </Typography.Text>
            </Space>
          </Card>
          {screens.md ? (
            <Table<IncidentPortfolioItem>
              rowKey="incident_id"
              columns={columns}
              dataSource={portfolio.items}
              pagination={false}
              scroll={{ x: 900 }}
            />
          ) : (
            <List
              dataSource={portfolio.items}
              renderItem={(item) => (
                <List.Item>
                  <IncidentCard
                    item={item}
                    onOpen={() => router.push(`/incidents/${item.incident_id}`)}
                  />
                </List.Item>
              )}
            />
          )}
          <Pagination
            current={Math.floor(portfolio.page.offset / portfolio.page.limit) + 1}
            pageSize={portfolio.page.limit}
            total={portfolio.scope.matched_incidents}
            showSizeChanger
            pageSizeOptions={[10, 25, 50, 100]}
            onChange={(page, size) => {
              setPageSize(size);
              setOffset((page - 1) * size);
            }}
          />
          {portfolio.limitations.map((item) => (
            <Alert key={item} type="info" showIcon message={item} />
          ))}
        </>
      )}
    </Space>
  );
}
