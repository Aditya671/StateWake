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
import { getCaptureHealth, type CaptureHealthRequest } from "@/lib/api/client";
import type { CaptureFailureRecordView, CaptureHealthView } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

interface CaptureFilters {
  stage?: string;
  errorType?: string;
}

const DEFAULT_PAGE_SIZE = 25;

function recordKey(item: CaptureFailureRecordView) {
  return `${item.sequence}:${item.stage}:${item.error_type}`;
}

export function CaptureHealthPanel() {
  const screens = Grid.useBreakpoint();
  const [form] = Form.useForm<CaptureFilters>();
  const [filters, setFilters] = useState<CaptureFilters>({});
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [view, setView] = useState<CaptureHealthView | null>(null);
  const [selected, setSelected] = useState<CaptureFailureRecordView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const request: CaptureHealthRequest = { limit: pageSize, offset };
    if (filters.stage) request.stage = filters.stage;
    if (filters.errorType) request.errorType = filters.errorType;
    setLoading(true);
    setError(null);
    getCaptureHealth(request, controller.signal)
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
                "Unable to load capture failure evidence",
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

  const columns = useMemo<ColumnsType<CaptureFailureRecordView>>(
    () => [
      { title: "Sequence", dataIndex: "sequence", key: "sequence", width: 110 },
      {
        title: "Stage",
        dataIndex: "stage",
        key: "stage",
        render: (value: string) => <Typography.Text className="sw-machine">{value}</Typography.Text>,
      },
      {
        title: "Error type",
        dataIndex: "error_type",
        key: "error_type",
        render: (value: string) => <Tag>{value}</Tag>,
      },
      {
        title: "Inspect",
        key: "inspect",
        width: 100,
        render: (_value, item) => (
          <Button type="link" style={{ paddingInline: 0 }} onClick={() => setSelected(item)}>
            Details
          </Button>
        ),
      },
    ],
    [],
  );

  if (loading && view === null) return <Skeleton active paragraph={{ rows: 10 }} />;
  if (error) {
    return (
      <Alert
        type={error.code === "CAPTURE_FAILURE_SOURCE_NOT_CONFIGURED" ? "warning" : "error"}
        showIcon
        message={
          error.code === "CAPTURE_FAILURE_SOURCE_NOT_CONFIGURED"
            ? "Capture failure journal is not configured"
            : "Capture health evidence is unavailable"
        }
        description={error.message}
      />
    );
  }
  if (view === null) return <Empty description="No capture failure-journal view is available." />;

  const stageOptions = view.aggregates.by_stage.map((item) => ({ value: item.stage, label: `${item.stage} (${item.count})` }));
  const errorOptions = view.aggregates.by_error_type.map((item) => ({ value: item.error_type, label: `${item.error_type} (${item.count})` }));
  const noRecordedFailures = view.observations.recorded_failure_count === 0;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Alert
        type={noRecordedFailures ? "info" : "warning"}
        showIcon
        message={
          noRecordedFailures
            ? "No failures are recorded in this configured journal"
            : `${view.observations.recorded_failure_count} capture failures are recorded`
        }
        description="This is not a capture-success signal. The journal records only stage and exception type, with no timestamps, raw exception messages, or SDK payloads."
      />

      <Row gutter={[12, 12]}>
        <Col xs={24} md={8}>
          <Card className="sw-card" size="small"><Statistic title="Recorded failures" value={view.observations.recorded_failure_count} /></Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="sw-card" size="small"><Statistic title="Distinct stages" value={view.observations.distinct_stage_count} /></Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="sw-card" size="small"><Statistic title="Journal bytes" value={view.source.journal_bytes} /></Card>
        </Col>
      </Row>

      <Card className="sw-card" size="small" title="Journal boundary">
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Journal file observed">{view.source.journal_exists ? "yes" : "not created"}</Descriptions.Item>
          <Descriptions.Item label="Read limit bytes">{view.source.read_limit_bytes}</Descriptions.Item>
          <Descriptions.Item label="Declared runtime capacity">
            {view.source.declared_capacity_bytes ?? "not declared to the read API"}
          </Descriptions.Item>
          <Descriptions.Item label="Declared capacity state">{view.source.declared_capacity_state}</Descriptions.Item>
          <Descriptions.Item label="Timestamps available">no</Descriptions.Item>
          <Descriptions.Item label="Workspace durability inferred">no</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="sw-card" size="small" title="Failure investigation">
        <Form<CaptureFilters>
          form={form}
          layout={screens.md ? "inline" : "vertical"}
          onFinish={(values) => {
            setFilters(values);
            setOffset(0);
            setSelected(null);
          }}
        >
          <Form.Item name="stage" label="Stage">
            <Select allowClear showSearch options={stageOptions} style={{ minWidth: screens.md ? 260 : undefined }} placeholder="All recorded stages" />
          </Form.Item>
          <Form.Item name="errorType" label="Error type">
            <Select allowClear showSearch options={errorOptions} style={{ minWidth: screens.md ? 220 : undefined }} placeholder="All error types" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">Apply</Button>
              <Button onClick={() => { form.resetFields(); setFilters({}); setOffset(0); setSelected(null); }}>Clear</Button>
            </Space>
          </Form.Item>
        </Form>

        <div style={{ marginTop: 16 }}>
          {view.items.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={view.page.matched === 0 ? "No recorded failures match these exact filters." : "No failures are present on this page."} />
          ) : screens.md ? (
            <Table<CaptureFailureRecordView>
              rowKey={recordKey}
              columns={columns}
              dataSource={view.items}
              pagination={false}
              size="small"
              scroll={{ x: 760 }}
            />
          ) : (
            <Space direction="vertical" size={10} style={{ width: "100%" }}>
              {view.items.map((item) => (
                <Card key={recordKey(item)} size="small">
                  <Space direction="vertical" size={6}>
                    <Tag>{item.error_type}</Tag>
                    <Typography.Text strong className="sw-machine">{item.stage}</Typography.Text>
                    <Typography.Text type="secondary">Recorded sequence {item.sequence}</Typography.Text>
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
          <Card className="sw-card" size="small" title="Failures by stage">
            {view.aggregates.by_stage.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> : (
              <Table rowKey="stage" size="small" pagination={false} dataSource={view.aggregates.by_stage} columns={[{ title: "Stage", dataIndex: "stage", key: "stage" }, { title: "Count", dataIndex: "count", key: "count", width: 90 }]} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="sw-card" size="small" title="Failures by error type">
            {view.aggregates.by_error_type.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> : (
              <Table rowKey="error_type" size="small" pagination={false} dataSource={view.aggregates.by_error_type} columns={[{ title: "Error type", dataIndex: "error_type", key: "error_type" }, { title: "Count", dataIndex: "count", key: "count", width: 90 }]} />
            )}
          </Card>
        </Col>
      </Row>

      <Card className="sw-card" size="small" title="Selected recorded failure">
        {selected === null ? (
          <Typography.Text type="secondary">Select a recorded failure to inspect the exact privacy-safe journal fields.</Typography.Text>
        ) : (
          <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Sequence">{selected.sequence}</Descriptions.Item>
            <Descriptions.Item label="Error type">{selected.error_type}</Descriptions.Item>
            <Descriptions.Item label="Stage" span={2}><span className="sw-machine">{selected.stage}</span></Descriptions.Item>
            <Descriptions.Item label="Timestamp">not recorded by canonical journal</Descriptions.Item>
            <Descriptions.Item label="Raw error message">intentionally not persisted</Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      {view.limitations.map((item) => <Alert key={item} type="info" showIcon message={item} />)}
    </Space>
  );
}
