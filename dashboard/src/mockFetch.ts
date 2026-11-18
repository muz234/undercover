import { vi } from "vitest";

export function mockFetch(routes: Record<string, unknown>) {
  const fetchMock = vi.fn((path: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${path}`;
    if (!(key in routes)) {
      return Promise.resolve(new Response("missing", { status: 404 }));
    }
    const route = routes[key];
    const body =
      typeof route === "function" ? (route as () => unknown)() : route;
    return Promise.resolve(Response.json(body));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
