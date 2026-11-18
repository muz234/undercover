import type { Claim, Customer, Handler, Policy, QueueClaim } from "./api";

export const queue: QueueClaim[] = [
  {
    claim_id: "CLM-1001",
    customer_name: "Maya Patel",
    claim_type: "trip_delay",
    summary: "Flight home canceled",
    submitted_on: "2026-06-24",
    amount_claimed: 420,
    status: "waiting",
  },
  {
    claim_id: "CLM-1002",
    customer_name: "Tom Becker",
    claim_type: "baggage",
    summary: "Laptop stolen",
    submitted_on: "2026-06-25",
    amount_claimed: 1500,
    status: "decided",
  },
];

export const claim: Claim = {
  claim_id: "CLM-1001",
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  claim_type: "trip_delay",
  submitted_on: "2026-06-24",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  summary: "Flight home canceled",
  story: "My flight was canceled.",
  items: [
    { description: "Airport hotel", category: "accommodation", amount: 245 },
    { description: "Dinner", category: "meals", amount: 175 },
  ],
  amount_claimed: 420,
  documents: [
    { name: "Hotel receipt", type: "receipt", content: "Paid $245." },
  ],
  status: "waiting",
  decision: null,
  signoff: null,
  payment: null,
  events: [],
};

export const policy: Policy = {
  policy_id: "POL-2001",
  plan: "premium",
  add_ons: [],
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
};

export const customer: Customer = {
  customer_id: "CUS-3001",
  name: "Maya Patel",
  email: "maya.patel@example.com",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      incident_date: "2024-08-09",
      summary: "Bag arrived late",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

export const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
  },
  { handler_id: "HND-02", name: "Marcus Oyelaran", role: "Claims Handler" },
];
