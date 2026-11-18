import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ClaimView } from "./ClaimView";
import { Queue } from "./Queue";
import { claim, customer, handlers, policy, queue } from "./fixtures";
import { mockFetch } from "./mockFetch";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const decision = {
  decision: "approve" as const,
  payout: 1250,
  explanation: "Covered.",
  policy_section: "Section 5",
  decided_at: "2026-06-30",
};
const step = { id: 1, tool: "get_claim", input: "{}", result: "ok", at: "now" };
const base = {
  "GET /api/policies/POL-2001": policy,
  "GET /api/customers/CUS-3001": customer,
  "GET /api/handlers": handlers,
};

it("runs the agent, shows its steps and stops polling when done", async () => {
  let state: "waiting" | "in_progress" | "decided" = "waiting";
  const fetchMock = mockFetch({
    ...base,
    "GET /api/claims/CLM-1001": () => ({
      ...claim,
      status: state,
      events: state === "waiting" ? [] : [step],
      decision: state === "decided" ? { ...decision, payout: 420 } : null,
    }),
    "POST /api/claims/CLM-1001/run": () => {
      state = "in_progress";
      return { status: state };
    },
  });
  render(<ClaimView claimId="CLM-1001" />);
  fireEvent.click(await screen.findByText("Run agent"));
  expect(
    await screen.findByText("The agent is working on this claim."),
  ).toBeDefined();
  expect(screen.getByText("get_claim")).toBeDefined();

  state = "decided";
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(await screen.findByText("Covered.")).toBeDefined();
  expect(screen.getAllByText("Decided").length).toBeGreaterThan(0);

  const calls = fetchMock.mock.calls.length;
  await act(() => vi.advanceTimersByTimeAsync(6000));
  expect(fetchMock.mock.calls).toHaveLength(calls);
});

it("stops polling when the page unmounts", async () => {
  const fetchMock = mockFetch({
    ...base,
    "GET /api/claims/CLM-1001": { ...claim, status: "in_progress", events: [] },
  });
  const view = render(<ClaimView claimId="CLM-1001" />);
  await screen.findByText("The agent is working on this claim.");
  view.unmount();
  const calls = fetchMock.mock.calls.length;
  await act(() => vi.advanceTimersByTimeAsync(6000));
  expect(fetchMock.mock.calls).toHaveLength(calls);
});

it("signs off a large payout and shows it paid", async () => {
  let paid = false;
  const fetchMock = mockFetch({
    ...base,
    "GET /api/claims/CLM-1001": () => ({
      ...claim,
      status: paid ? "decided" : "waiting_for_signoff",
      decision,
      signoff: paid ? { handler_id: "HND-02", signed_at: "now" } : null,
      payment: paid ? { amount: 1250, paid_at: "now" } : null,
      events: [step],
    }),
    "POST /api/claims/CLM-1001/sign-off": () => {
      paid = true;
      return { status: "decided" };
    },
  });
  render(<ClaimView claimId="CLM-1001" />);
  expect(await screen.findByText("Sign-off needed")).toBeDefined();
  fireEvent.change(await screen.findByLabelText("Handler"), {
    target: { value: "HND-02" },
  });
  fireEvent.click(screen.getByText("Sign off and pay"));
  expect(await screen.findByText(/Paid/)).toBeDefined();
  expect(screen.queryByText("Sign-off needed")).toBeNull();
  const post = fetchMock.mock.calls.find(([path]) => path.endsWith("sign-off"));
  expect(post?.[1]?.body).toBe(JSON.stringify({ handler_id: "HND-02" }));
});

it("shows an error from the agent run", async () => {
  mockFetch({
    ...base,
    "GET /api/claims/CLM-1001": {
      ...claim,
      events: [{ ...step, tool: "error", result: "The agent failed: offline" }],
    },
  });
  render(<ClaimView claimId="CLM-1001" />);
  expect(await screen.findByText("The agent failed: offline")).toBeDefined();
});

it("runs every waiting claim from the queue in order", async () => {
  const runs: string[] = [];
  const waiting = [
    { ...queue[0], claim_id: "CLM-1001" },
    { ...queue[0], claim_id: "CLM-1003" },
  ];
  mockFetch({
    "GET /api/claims": () =>
      waiting.map((c) => ({
        ...c,
        status: runs.includes(c.claim_id) ? "decided" : "waiting",
      })),
    "GET /api/claims/CLM-1001": { ...claim, status: "decided" },
    "GET /api/claims/CLM-1003": { ...claim, status: "decided" },
    "POST /api/claims/CLM-1001/run": () => {
      runs.push("CLM-1001");
      return { status: "in_progress" };
    },
    "POST /api/claims/CLM-1003/run": () => {
      runs.push("CLM-1003");
      return { status: "in_progress" };
    },
  });
  render(<Queue />);
  fireEvent.click(await screen.findByText("Run all waiting"));
  await vi.waitFor(() => {
    expect(runs).toEqual(["CLM-1001", "CLM-1003"]);
  });
  await vi.waitFor(() => {
    expect(screen.getByText("Run all waiting").hasAttribute("disabled")).toBe(
      true,
    );
  });
});

it("polls the queue while a claim is in progress", async () => {
  const fetchMock = mockFetch({
    "GET /api/claims": [{ ...queue[0], status: "in_progress" }],
  });
  render(<Queue />);
  await screen.findByText("CLM-1001");
  const calls = fetchMock.mock.calls.length;
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(fetchMock.mock.calls.length).toBeGreaterThan(calls);
});
