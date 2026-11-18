import { useEffect, useState } from "react";
import { ClaimView } from "./ClaimView";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";

function useHash() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const update = () => {
      setHash(window.location.hash);
    };
    window.addEventListener("hashchange", update);
    return () => {
      window.removeEventListener("hashchange", update);
    };
  }, []);
  return hash;
}

export function App() {
  const hash = useHash();
  const claimId = /^#\/claims\/(.+)$/.exec(hash)?.[1];
  let page = <Queue />;
  if (claimId) page = <ClaimView claimId={claimId} />;
  else if (hash === "#/instructions") page = <Instructions />;

  return (
    <>
      <header>
        <a className="brand" href="#/">
          UnderCover
        </a>
        <nav>
          <a href="#/">Claims queue</a>
          <a href="#/instructions">Agent instructions</a>
        </nav>
      </header>
      <main>{page}</main>
    </>
  );
}
