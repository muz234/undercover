import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { claim, customer, policy, queue } from "./fixtures";
import { mockFetch } from "./mockFetch";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

const routes = {
  "GET /api/claims": queue,
  "GET /api/claims/CLM-1001": claim,
  "GET /api/policies/POL-2001": policy,
  "GET /api/customers/CUS-3001": customer,
  "GET /api/instructions": { text: "Decide claims by the wording." },
};

it("lists the queue with statuses and filters it", async () => {
  mockFetch(routes);
  render(<App />);
  expect(await screen.findByText("CLM-1002")).toBeDefined();
  expect(screen.getByText("Waiting", { selector: "span" })).toBeDefined();
  expect(screen.getByText("$1,500.00")).toBeDefined();
  fireEvent.change(screen.getByLabelText("Show"), {
    target: { value: "decided" },
  });
  expect(screen.queryByText("CLM-1001")).toBeNull();
  expect(screen.getByText("CLM-1002")).toBeDefined();
});

it("shows an error when the queue cannot load", async () => {
  mockFetch({});
  render(<App />);
  expect(await screen.findByText(/api\/claims/)).toBeDefined();
});

it("shows a claim in full", async () => {
  mockFetch(routes);
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  expect(await screen.findByText("My flight was canceled.")).toBeDefined();
  expect(screen.getByText("Total claimed")).toBeDefined();
  expect(screen.getAllByText("$420.00").length).toBeGreaterThan(0);
  expect(await screen.findByText(/Bag arrived late/)).toBeDefined();
  expect(screen.getByText(/Premium\s+plan/)).toBeDefined();
});

it("shows the decision, sign-off and payment of a decided claim", async () => {
  mockFetch({
    ...routes,
    "GET /api/claims/CLM-1001": {
      ...claim,
      status: "decided",
      decision: {
        decision: "approve",
        payout: 420,
        explanation: "Covered by the wording.",
        policy_section: "Section 3, Trip Delay",
        decided_at: "2026-06-30",
      },
      signoff: { handler_id: "HND-01", signed_at: "2026-06-30" },
      payment: { amount: 420, paid_at: "2026-06-30" },
    },
  });
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  expect(await screen.findByText("Covered by the wording.")).toBeDefined();
  expect(screen.getByText("Section 3, Trip Delay")).toBeDefined();
  expect(screen.getByText("HND-01")).toBeDefined();
});

it("shows the instructions with no way to edit them", async () => {
  mockFetch(routes);
  window.location.hash = "#/instructions";
  render(<App />);
  expect(
    await screen.findByText("Decide claims by the wording."),
  ).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
});
