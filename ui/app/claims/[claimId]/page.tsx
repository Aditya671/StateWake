import { ClaimWorkbench } from "@/features/claims/ClaimWorkbench";

export default async function ClaimPage({ params }: { params: Promise<{ claimId: string }> }) {
  const { claimId } = await params;
  return <ClaimWorkbench recordId={claimId} />;
}
