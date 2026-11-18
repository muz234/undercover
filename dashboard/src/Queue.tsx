import { useCallback, useEffect, useState } from "react";
import {
  getClaims,
  POLL_MS,
  REFRESH_MS,
  runAndWait,
  type QueueClaim,
  type Status,
} from "./api";
import { label, money, STATUS_LABELS } from "./format";
import { StatusChip } from "./StatusChip";

export function Queue() {
  const [claims, setClaims] = useState<QueueClaim[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Status | "all">("all");

  const [running, setRunning] = useState(false);

  const reload = useCallback(
    () =>
      getClaims()
        .then(setClaims)
        .catch((e: unknown) => {
          setError(e instanceof Error ? e.message : "Could not load the queue");
        }),
    [],
  );
  const working = claims?.some((c) => c.status === "in_progress") ?? false;

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    const timer = setInterval(
      () => void reload(),
      working ? POLL_MS : REFRESH_MS,
    );
    return () => {
      clearInterval(timer);
    };
  }, [working, reload]);

  const runAll = async () => {
    setRunning(true);
    for (const c of (claims ?? []).filter((x) => x.status === "waiting")) {
      await runAndWait(c.claim_id);
      await reload();
    }
    setRunning(false);
  };

  if (error) return <p className="error">{error}</p>;
  if (!claims) return <p>Loading the queue</p>;

  const shown = claims.filter((c) => filter === "all" || c.status === filter);

  return (
    <section className="panel">
      <div className="panel-head">
        <h1>Claims queue</h1>
        <button
          disabled={running || !claims.some((c) => c.status === "waiting")}
          onClick={() => void runAll()}
        >
          Run all waiting
        </button>
        <label>
          Show{" "}
          <select
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value as Status | "all");
            }}
          >
            <option value="all">All claims</option>
            {Object.entries(STATUS_LABELS).map(([value, text]) => (
              <option key={value} value={value}>
                {text}
              </option>
            ))}
          </select>
        </label>
      </div>
      <table>
        <thead>
          <tr>
            <th>Claim</th>
            <th>Customer</th>
            <th>Type</th>
            <th>Summary</th>
            <th className="num">Claimed</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((c) => (
            <tr key={c.claim_id}>
              <td className="mono">
                <a href={`#/claims/${c.claim_id}`}>{c.claim_id}</a>
              </td>
              <td>{c.customer_name}</td>
              <td>{label(c.claim_type)}</td>
              <td>{c.summary}</td>
              <td className="num mono">{money(c.amount_claimed)}</td>
              <td>
                <StatusChip status={c.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
