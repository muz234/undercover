import { useEffect, useState } from "react";
import {
  getHandlers,
  runClaim,
  signOff,
  type Claim,
  type Handler,
} from "./api";
import { money } from "./format";

const SHORT = 160;
const short = (text: string) =>
  text.length > SHORT ? `${text.slice(0, SHORT)}...` : text;

export function Steps({ claim }: Readonly<{ claim: Claim }>) {
  if (claim.events.length === 0 && claim.status !== "in_progress") return null;
  return (
    <section className="panel">
      <h2>What the agent did</h2>
      {claim.status === "in_progress" && (
        <p className="muted">The agent is working on this claim.</p>
      )}
      <ol className="steps">
        {claim.events.map((step) => (
          <li key={step.id} className={step.tool === "error" ? "error" : ""}>
            <span className="mono">{step.tool}</span>{" "}
            <span className="muted mono">{short(step.input)}</span>
            <div>{short(step.result)}</div>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function RunPanel({
  claim,
  onChange,
}: Readonly<{ claim: Claim; onChange: () => void }>) {
  const [busy, setBusy] = useState(false);
  if (claim.status !== "waiting") return null;
  return (
    <section className="panel">
      <button
        disabled={busy}
        onClick={() => {
          setBusy(true);
          void runClaim(claim.claim_id)
            .then(onChange)
            .finally(() => {
              setBusy(false);
            });
        }}
      >
        Run agent
      </button>
    </section>
  );
}

export function SignOffPanel({
  claim,
  onChange,
}: Readonly<{ claim: Claim; onChange: () => void }>) {
  const [handlers, setHandlers] = useState<Handler[]>([]);
  const [handlerId, setHandlerId] = useState("");
  const waiting = claim.status === "waiting_for_signoff";

  useEffect(() => {
    if (!waiting) return;
    void getHandlers().then((list) => {
      setHandlers(list);
      setHandlerId(list[0]?.handler_id ?? "");
    });
  }, [waiting]);

  if (!waiting || !claim.decision) return null;
  return (
    <section className="panel">
      <h2>Sign-off needed</h2>
      <p>
        The payout of{" "}
        <span className="mono">{money(claim.decision.payout)}</span> is over the
        approval limit. It is paid when a handler signs off.
      </p>
      <label>
        Handler{" "}
        <select
          value={handlerId}
          onChange={(e) => {
            setHandlerId(e.target.value);
          }}
        >
          {handlers.map((h) => (
            <option key={h.handler_id} value={h.handler_id}>
              {h.name}
            </option>
          ))}
        </select>
      </label>{" "}
      <button
        disabled={!handlerId}
        onClick={() => {
          void signOff(claim.claim_id, handlerId).then(onChange);
        }}
      >
        Sign off and pay
      </button>
    </section>
  );
}
