const RECEIPT_ID = /^[0-9a-f]{64}$/;

export function isAllowedReviewApiPath(parts: readonly string[]): boolean {
  if (parts.length === 3) {
    return parts[0] === "api" && parts[1] === "v1" && parts[2] === "review-capabilities";
  }
  const isThread =
    parts.length === 5 &&
    parts[0] === "api" &&
    parts[1] === "v1" &&
    parts[2] === "claims" &&
    RECEIPT_ID.test(parts[3] ?? "") &&
    ["reviews", "approvals"].includes(parts[4] ?? "");
  const isApprovalLifecycle =
    parts.length === 7 &&
    parts[0] === "api" &&
    parts[1] === "v1" &&
    parts[2] === "claims" &&
    RECEIPT_ID.test(parts[3] ?? "") &&
    parts[4] === "approvals" &&
    RECEIPT_ID.test(parts[5] ?? "") &&
    ["revoke", "supersede"].includes(parts[6] ?? "");
  return isThread || isApprovalLifecycle;
}

export function encodedReviewApiPath(parts: readonly string[]): string {
  if (!isAllowedReviewApiPath(parts)) {
    throw new Error("unsupported StateWake review API path");
  }
  return `/${parts.map(encodeURIComponent).join("/")}`;
}
