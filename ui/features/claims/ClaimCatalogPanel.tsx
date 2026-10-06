"use client";

import {
  Alert,
  Button,
  Card,
  Checkbox,
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
import { getClaimCatalog, type ClaimCatalogRequest } from "@/lib/api/client";
import type { ClaimCatalog, ClaimCatalogItem } from "@/lib/api/dto";
import { StateWakeApiError } from "@/lib/api/errors";

interface CatalogFilters {
  text?: string;
  decision?: string;
  verified?: "true" | "false";
  approvalStatus?: string;
  profileId?: string;
  candidateId?: string;
}

const DEFAULT_PAGE_SIZE = 25;

function normalizeFilters(values: CatalogFilters): CatalogFilters {
  const cleaned: CatalogFilters = {};
  if (values.text?.trim()) cleaned.text = values.text.trim();
  if (values.decision?.trim()) cleaned.decision = values.decision.trim();
  if (values.verified) cleaned.verified = values.verified;
  if (values.approvalStatus?.trim()) {
    cleaned.approvalStatus = values.approvalStatus.trim();
  }
  if (values.profileId?.trim()) cleaned.profileId = values.profileId.trim();
  if (values.candidateId?.trim()) cleaned.candidateId = values.candidateId.trim();
  return cleaned;
}

function decisionTag(decision: string) {
  const color = decision === "accept" ? "success" : decision === "reject" ? "error" : "warning";
  return <Tag color={color}>{decision}</Tag>;
}

function reportStatus(item: ClaimCatalogItem) {
  if (!item.verified) return <Tag color="warning">unverified</Tag>;
  return <Tag color="success">verified</Tag>;
}

function CatalogCard({
  item,
  checked,
  onChecked,
  onOpen,
  disabled,
}: {
  item: ClaimCatalogItem;
  checked: boolean;
  onChecked: (checked: boolean) => void;
  onOpen: () => void;
  disabled: boolean;
}) {
  return (
    <Card size="small" className="sw-card sw-catalog-card">
      <Space direction="vertical" size={10} style={{ width: "100%" }}>
        <Space wrap>
          <Checkbox
            checked={checked}
            disabled={disabled}
            onChange={(event) => onChecked(event.target.checked)}
          >
            Compare
          </Checkbox>
          {decisionTag(item.decision)}
          {reportStatus(item)}
          {item.human_decision_required && <Tag>human decision</Tag>}
        </Space>
        <Typography.Text strong>{item.claim}</Typography.Text>
        <Typography.Text type="secondary" className="sw-machine">
          {item.profile.id} · {item.candidate.id}
        </Typography.Text>
        <Typography.Text type="secondary">
          Captured {item.captured_at} · missing evidence {item.evidence.missing} · failed checks {item.checks.failed}
        </Typography.Text>
        <Button type="link" style={{ paddingInline: 0 }} onClick={onOpen}>
          Open workbench
        </Button>
      </Space>
    </Card>
  );
}

export function ClaimCatalogPanel() {
  const router = useRouter();
  const screens = Grid.useBreakpoint();
  const [form] = Form.useForm<CatalogFilters>();
  const [filters, setFilters] = useState<CatalogFilters>({});
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [catalog, setCatalog] = useState<ClaimCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<StateWakeApiError | null>(null);
  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    const request: ClaimCatalogRequest = { limit: pageSize, offset };
    if (filters.text) request.text = filters.text;
    if (filters.decision) request.decision = filters.decision;
    if (filters.verified !== undefined) {
      request.verified = filters.verified === "true";
    }
    if (filters.approvalStatus) request.approvalStatus = filters.approvalStatus;
    if (filters.profileId) request.profileId = filters.profileId;
    if (filters.candidateId) request.candidateId = filters.candidateId;
    setLoading(true);
    setError(null);
    getClaimCatalog(request, controller.signal)
      .then((value) => {
        if (value.items.length === 0 && value.scope.matched_reports > 0 && value.page.offset > 0) {
          setCatalog(null);
          setOffset(0);
          return;
        }
        setCatalog(value);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setCatalog(null);
        setError(
          caught instanceof StateWakeApiError
            ? caught
            : new StateWakeApiError(
                "Unable to load claim catalog",
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

  const columns = useMemo<ColumnsType<ClaimCatalogItem>>(
    () => [
      {
        title: "Claim",
        dataIndex: "claim",
        key: "claim",
        render: (_value, item) => (
          <Space direction="vertical" size={2}>
            <Button type="link" style={{ paddingInline: 0 }} onClick={() => router.push(`/claims/${item.record_id}`)}>
              {item.claim}
            </Button>
            <Typography.Text type="secondary" className="sw-machine">
              {item.profile.id} · {item.candidate.id}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: "Decision",
        dataIndex: "decision",
        key: "decision",
        width: 120,
        render: (value: string) => decisionTag(value),
      },
      {
        title: "Verification",
        key: "verification",
        width: 135,
        render: (_value, item) => reportStatus(item),
      },
      {
        title: "Evidence / checks",
        key: "evidence",
        width: 155,
        render: (_value, item) => (
          <Typography.Text type="secondary">
            missing {item.evidence.missing} · failed {item.checks.failed}
          </Typography.Text>
        ),
      },
      {
        title: "Captured",
        dataIndex: "captured_at",
        key: "captured_at",
        width: 210,
      },
    ],
    [router],
  );

  const toggleSelected = (recordId: string, checked: boolean) => {
    setSelected((current) => {
      if (!checked) return current.filter((value) => value !== recordId);
      if (current.includes(recordId)) return current;
      return [...current, recordId].slice(-2);
    });
  };

  const reset = () => {
    form.resetFields();
    setFilters({});
    setOffset(0);
    setSelected([]);
  };

  const compare = () => {
    const [left, right] = selected;
    if (left === undefined || right === undefined) return;
    router.push(
      `/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`,
    );
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card className="sw-card" size="small" title="Discover verification reports">
        <Form<CatalogFilters>
          form={form}
          layout="vertical"
          onFinish={(values) => {
            setFilters(normalizeFilters(values));
            setOffset(0);
            setSelected([]);
          }}
        >
          <Row gutter={12}>
            <Col xs={24} lg={10}>
              <Form.Item
                label="Search"
                name="text"
                rules={[{ max: 200, message: "Search text must be 200 characters or fewer" }]}
              >
                <Input
                  allowClear
                  placeholder="Claim, profile, candidate, decision, approval status"
                  autoComplete="off"
                />
              </Form.Item>
            </Col>
            <Col xs={12} md={8} lg={4}>
              <Form.Item label="Decision" name="decision" rules={[{ max: 256 }]}>
                <Input allowClear placeholder="review" autoComplete="off" />
              </Form.Item>
            </Col>
            <Col xs={12} md={8} lg={4}>
              <Form.Item label="Verified" name="verified">
                <Select
                  allowClear
                  options={[
                    { value: "true", label: "Verified" },
                    { value: "false", label: "Not verified" },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8} lg={6}>
              <Form.Item label="Approval status" name="approvalStatus">
                <Select
                  allowClear
                  options={[
                    { value: "not-approval", label: "Not an approval" },
                    { value: "requires-human-approval", label: "Requires human approval" },
                    { value: "approved", label: "Approved" },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} lg={12}>
              <Form.Item label="Profile ID" name="profileId" rules={[{ max: 256 }]}>
                <Input allowClear autoComplete="off" placeholder="rag_answer_verified.v1" />
              </Form.Item>
            </Col>
            <Col xs={24} lg={12}>
              <Form.Item label="Candidate ID" name="candidateId" rules={[{ max: 256 }]}>
                <Input allowClear autoComplete="off" placeholder="Exact recorded candidate identity" />
              </Form.Item>
            </Col>
          </Row>
          <Space wrap>
            <Button type="primary" htmlType="submit">Apply filters</Button>
            <Button onClick={reset}>Clear</Button>
            <Button disabled={selected.length !== 2} onClick={compare}>
              Compare selected ({selected.length}/2)
            </Button>
          </Space>
        </Form>
      </Card>

      {loading && <Skeleton active paragraph={{ rows: 9 }} />}
      {error && (
        <Alert
          type="error"
          showIcon
          message="Claim catalog unavailable"
          description={`${error.code}: ${error.message}`}
        />
      )}
      {!loading && !error && catalog && catalog.scope.total_reports === 0 && (
        <Empty description="No canonical verification reports are present in this workspace." />
      )}
      {!loading && !error && catalog && catalog.scope.total_reports > 0 && catalog.items.length === 0 && (
        <Empty
          description="No verification reports match the current filters."
        >
          <Button onClick={reset}>Clear filters</Button>
        </Empty>
      )}
      {!loading && !error && catalog && catalog.items.length > 0 && (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Alert
            type="info"
            showIcon
            message={`${catalog.scope.matched_reports} matching report${catalog.scope.matched_reports === 1 ? "" : "s"}`}
            description={`Discovery scanned ${catalog.scope.scanned_receipts} workspace receipts and found ${catalog.scope.total_reports} canonical verification reports. Results are recorded evidence, not a reliability ranking.`}
          />
          {screens.md ? (
            <Table<ClaimCatalogItem>
              className="sw-catalog-table"
              rowKey="record_id"
              columns={columns}
              dataSource={catalog.items}
              pagination={false}
              scroll={{ x: 960 }}
              rowSelection={{
                selectedRowKeys: selected,
                preserveSelectedRowKeys: true,
                onSelect: (item, checked) => toggleSelected(item.record_id, checked),
                hideSelectAll: true,
                getCheckboxProps: (item) => ({
                  disabled: !selected.includes(item.record_id) && selected.length >= 2,
                }),
              }}
            />
          ) : (
            <List
              dataSource={catalog.items}
              renderItem={(item) => (
                <List.Item style={{ paddingInline: 0 }}>
                  <CatalogCard
                    item={item}
                    checked={selected.includes(item.record_id)}
                    onChecked={(checked) => toggleSelected(item.record_id, checked)}
                    onOpen={() => router.push(`/claims/${item.record_id}`)}
                    disabled={!selected.includes(item.record_id) && selected.length >= 2}
                  />
                </List.Item>
              )}
            />
          )}
          <Pagination
            current={Math.floor(catalog.page.offset / catalog.page.limit) + 1}
            pageSize={catalog.page.limit}
            total={catalog.scope.matched_reports}
            showSizeChanger
            pageSizeOptions={[25, 50, 100, 200]}
            showTotal={(total) => `${total} matching reports`}
            onChange={(page, nextPageSize) => {
              if (nextPageSize !== pageSize) {
                setPageSize(nextPageSize);
                setOffset(0);
              } else {
                setOffset((page - 1) * nextPageSize);
              }
            }}
          />
          <Typography.Paragraph type="secondary" className="sw-overview-footnote">
            {catalog.limitations.join(" ")}
          </Typography.Paragraph>
        </Space>
      )}
    </Space>
  );
}
