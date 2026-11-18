import { useEffect, useState } from "react";
import { getInstructions } from "./api";

export function Instructions() {
  const [text, setText] = useState<string | null>(null);

  useEffect(() => {
    void getInstructions().then((r) => {
      setText(r.text);
    });
  }, []);

  return (
    <section className="panel">
      <h1>Agent instructions</h1>
      <p className="muted">
        These are the instructions the UnderCover Agent works from. They are
        read only.
      </p>
      <pre className="instructions">{text ?? "Loading"}</pre>
    </section>
  );
}
