const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    throw new Error((data && data.detail) || "Request failed");
  }
  return data;
}

export const calculate = (expression, mode) =>
  request("/calculate", {
    method: "POST",
    body: JSON.stringify({ expression, mode }),
  });

export const getHistory = () => request("/history");

export const deleteHistoryItem = (id) =>
  request(`/history/${id}`, { method: "DELETE" });

export const clearHistory = () => request("/history", { method: "DELETE" });
