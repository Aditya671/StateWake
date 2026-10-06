import { ClaimComparisonWorkbench } from "@/features/claims/ClaimComparisonWorkbench";

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ left?: string; right?: string }>;
}) {
  const params = await searchParams;
  return (
    <ClaimComparisonWorkbench
      initialLeft={params.left ?? ""}
      initialRight={params.right ?? ""}
    />
  );
}
