export type Status =
  "waiting" | "in_progress" | "waiting_for_signoff" | "decided";

export interface QueueClaim {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  submitted_on: string;
  amount_claimed: number;
  status: Status;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface Document {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decision: "approve" | "decline" | "refer";
  payout: number;
  explanation: string;
  policy_section: string;
  decided_at: string;
}

export interface Step {
  id: number;
  tool: string;
  input: string;
  result: string;
  at: string;
}

export interface Claim extends Omit<QueueClaim, "customer_name"> {
  policy_id: string;
  customer_id: string;
  incident_date: string;
  incident_location: string;
  story: string;
  items: Item[];
  documents: Document[];
  decision: Decision | null;
  signoff: { handler_id: string; signed_at: string } | null;
  payment: { amount: number; paid_at: string } | null;
  events: Step[];
}

export interface Policy {
  policy_id: string;
  plan: string;
  add_ons: string[];
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
}

export interface PreviousClaim {
  claim_id: string;
  incident_date: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Customer {
  customer_id: string;
  name: string;
  email: string;
  previous_claims: PreviousClaim[];
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
}

async function request<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : undefined,
  );
  if (!response.ok) throw new Error(`${path}: ${response.statusText}`);
  return (await response.json()) as T;
}

export const getClaims = () => request<QueueClaim[]>("/api/claims");
export const getClaim = (id: string) => request<Claim>(`/api/claims/${id}`);
export const getPolicy = (id: string) => request<Policy>(`/api/policies/${id}`);
export const getCustomer = (id: string) =>
  request<Customer>(`/api/customers/${id}`);
export const getHandlers = () => request<Handler[]>("/api/handlers");
export const getInstructions = () =>
  request<{ text: string }>("/api/instructions");

export const POLL_MS = 2000;

export const runClaim = (id: string) =>
  request<{ status: Status }>(`/api/claims/${id}/run`, {});
export const signOff = (id: string, handlerId: string) =>
  request<{ status: Status }>(`/api/claims/${id}/sign-off`, {
    handler_id: handlerId,
  });

export async function runAndWait(id: string): Promise<void> {
  await runClaim(id);
  while ((await getClaim(id)).status === "in_progress") {
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
}
