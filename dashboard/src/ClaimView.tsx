import { useCallback, useEffect, useState } from "react";
import {
  getClaim,
  getCustomer,
  getPolicy,
  type Claim,
  type Customer,
  type Policy,
  POLL_MS,
  REFRESH_MS,
} from "./api";
import { RunPanel, SignOffPanel, Steps } from "./ClaimActions";
import { label, money } from "./format";
import { StatusChip } from "./StatusChip";

function Story({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <section className="panel">
      <h2>The claim</h2>
      <p className="muted">
        {label(claim.claim_type)}, incident on {claim.incident_date} in{" "}
        {claim.incident_location}
      </p>
      <p>{claim.story}</p>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Category</th>
            <th className="num">Amount</th>
          </tr>
        </thead>
        <tbody>
          {claim.items.map((item) => (
            <tr key={item.description}>
              <td>{item.description}</td>
              <td>{label(item.category)}</td>
              <td className="num mono">{money(item.amount)}</td>
            </tr>
          ))}
          <tr>
            <th colSpan={2}>Total claimed</th>
            <th className="num mono">{money(claim.amount_claimed)}</th>
          </tr>
        </tbody>
      </table>
      <h3>Documents</h3>
      {claim.documents.map((doc) => (
        <div key={doc.name} className="document">
          <strong>{doc.name}</strong>{" "}
          <span className="muted">{label(doc.type)}</span>
          <p>{doc.content}</p>
        </div>
      ))}
    </section>
  );
}

function Background({
  policy,
  customer,
}: Readonly<{
  policy: Policy;
  customer: Customer;
}>) {
  return (
    <section className="panel">
      <h2>Policy and customer</h2>
      <p>
        <strong>{customer.name}</strong>, {customer.email}
      </p>
      <p>
        <span className="mono">{policy.policy_id}</span>, {label(policy.plan)}{" "}
        plan
        {policy.add_ons.length > 0 &&
          `, with ${policy.add_ons.map(label).join(", ")}`}
        . Trip to {policy.trip.destination}, {policy.trip.departs_on} to{" "}
        {policy.trip.returns_on}, costing {money(policy.trip.trip_cost)}.
      </p>
      <h3>Earlier claims</h3>
      {customer.previous_claims.length === 0 ? (
        <p className="muted">None</p>
      ) : (
        <ul>
          {customer.previous_claims.map((p) => (
            <li key={p.claim_id}>
              <span className="mono">{p.claim_id}</span>, {p.incident_date}:{" "}
              {p.summary}. {label(p.outcome)}, {money(p.amount_paid)} paid.
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DecisionPanel({ claim }: Readonly<{ claim: Claim }>) {
  const { decision, payment, signoff } = claim;
  if (!decision) return null;
  return (
    <section className="panel">
      <h2>Decision</h2>
      <p>
        <strong>{label(decision.decision)}</strong>
        {decision.decision === "approve" && (
          <>
            {" "}
            with a payout of{" "}
            <span className="mono">{money(decision.payout)}</span>
          </>
        )}
      </p>
      <p>{decision.explanation}</p>
      <p className="muted">{decision.policy_section}</p>
      {signoff && (
        <p className="muted">
          Signed off by <span className="mono">{signoff.handler_id}</span>
        </p>
      )}
      {payment && (
        <p className="muted">
          Paid <span className="mono">{money(payment.amount)}</span> on{" "}
          {payment.paid_at}
        </p>
      )}
    </section>
  );
}

export function ClaimView({ claimId }: Readonly<{ claimId: string }>) {
  const [claim, setClaim] = useState<Claim | null>(null);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fail = (e: unknown) => {
    setError(e instanceof Error ? e.message : "Could not load the claim");
  };
  const reload = useCallback(
    () => getClaim(claimId).then(setClaim).catch(fail),
    [claimId],
  );
  const running = claim?.status === "in_progress";
  const policyId = claim?.policy_id;
  const customerId = claim?.customer_id;

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    const timer = setInterval(
      () => void reload(),
      running ? POLL_MS : REFRESH_MS,
    );
    return () => {
      clearInterval(timer);
    };
  }, [running, reload]);

  useEffect(() => {
    if (!policyId || !customerId) return;
    getPolicy(policyId).then(setPolicy).catch(fail);
    getCustomer(customerId).then(setCustomer).catch(fail);
  }, [policyId, customerId]);

  if (!claim)
    return (
      <p className={error ? "error" : ""}>{error ?? "Loading the claim"}</p>
    );

  return (
    <>
      <div className="panel-head">
        <h1 className="mono">{claim.claim_id}</h1>
        <StatusChip status={claim.status} />
      </div>
      {error && <p className="error">{error}</p>}
      <RunPanel claim={claim} onChange={() => void reload()} />
      <Steps claim={claim} />
      <DecisionPanel claim={claim} />
      <SignOffPanel claim={claim} onChange={() => void reload()} />
      <Story claim={claim} />
      {policy && customer && <Background policy={policy} customer={customer} />}
    </>
  );
}
