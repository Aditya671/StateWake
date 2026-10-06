export type StateTone = "success" | "error" | "warning" | "processing" | "default";

const KNOWN_STATES: Readonly<Record<string, { label: string; tone: StateTone }>> = {
  accept: { label: "Accept", tone: "success" },
  accepted: { label: "Accepted", tone: "success" },
  accepted_with_limitations: { label: "Accepted with limitations", tone: "warning" },
  review: { label: "Review", tone: "warning" },
  requires_reverification: { label: "Requires reverification", tone: "warning" },
  reject: { label: "Reject", tone: "error" },
  rejected: { label: "Rejected", tone: "error" },
  undecided: { label: "Undecided", tone: "default" },
  "not-approval": { label: "Not an approval", tone: "default" },
  "requires-human-approval": { label: "Requires human approval", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  pending: { label: "Pending", tone: "warning" },
  "not-requested": { label: "Not requested", tone: "default" },
  verified: { label: "Verified", tone: "success" },
  "not-verified": { label: "Not verified", tone: "error" },
};

export function stateFacetPresentation(value: string): { label: string; tone: StateTone } {
  return KNOWN_STATES[value] ?? {
    label: `Unrecognized state: ${value}`,
    tone: "default",
  };
}
