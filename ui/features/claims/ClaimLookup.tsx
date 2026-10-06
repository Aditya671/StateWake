"use client";

import { Button, Card, Form, Input, Space, Typography } from "antd";
import { useRouter } from "next/navigation";

const RECORD_ID = /^[0-9a-f]{64}$/;

export function ClaimLookup() {
  const router = useRouter();
  return (
    <Card className="sw-card">
      <Typography.Title level={2} style={{ marginTop: 0 }}>Open a verification report</Typography.Title>
      <Typography.Paragraph type="secondary">
        Enter a durable 64-character receipt identity to open an exact StateWake verification report, or browse the bounded canonical claim catalog when you do not already know the record ID.
      </Typography.Paragraph>
      <Form<{ recordId: string }>
        layout="vertical"
        onFinish={({ recordId }) => router.push(`/claims/${recordId.trim()}`)}
      >
        <Form.Item
          label="Report receipt ID"
          name="recordId"
          rules={[
            { required: true, message: "Enter a report receipt ID" },
            { validator: (_, value: string | undefined) => value && RECORD_ID.test(value.trim()) ? Promise.resolve() : Promise.reject(new Error("Use the lowercase 64-character SHA-256 receipt identity")) },
          ]}
        >
          <Input className="mono" autoComplete="off" spellCheck={false} placeholder="64-character lowercase receipt identity" />
        </Form.Item>
        <Space wrap>
          <Button type="primary" htmlType="submit">Open workbench</Button>
          <Button onClick={() => router.push("/claims")}>Browse claim catalog</Button>
        </Space>
      </Form>
    </Card>
  );
}
