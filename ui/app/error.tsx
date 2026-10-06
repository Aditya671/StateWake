"use client";

import { Button, Result } from "antd";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <Result status="error" title="The inspection UI could not render this view" subTitle="No StateWake verification result has been changed." extra={<Button onClick={reset}>Retry view</Button>} />;
}
