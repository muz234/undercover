import { useEffect, useState } from "react";
import {
  getClaim,
  getCustomer,
  getPolicy,
  type Claim,
  type Customer,
  type Policy,
} from "./api";
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
  const [background, setBackground] = useState<{
    policy: Policy;
    customer: Customer;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getClaim(claimId)
      .then(async (c) => {
        setClaim(c);
        const [policy, customer] = await Promise.all([
          getPolicy(c.policy_id),
          getCustomer(c.customer_id),
        ]);
        setBackground({ policy, customer });
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Could not load the claim");
      });
  }, [claimId]);

  if (error) return <p className="error">{error}</p>;
  if (!claim) return <p>Loading the claim</p>;

  return (
    <>
      <div className="panel-head">
        <h1 className="mono">{claim.claim_id}</h1>
        <StatusChip status={claim.status} />
      </div>
      <DecisionPanel claim={claim} />
      <Story claim={claim} />
      {background && <Background {...background} />}
    </>
  );
}
