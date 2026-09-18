export class LinkifyClient {
  constructor({ apiKey, baseUrl = "http://localhost:8000", timeout = 30000 }) {
    if (!apiKey) throw new Error("apiKey is required");
    this.apiKey = apiKey;
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.timeout = timeout;
  }

  async request(path, { method = "GET", params, body } = {}) {
    const url = new URL(`${this.baseUrl}/api/v1/${path.replace(/^\//, "")}`);
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
    });
    const response = await fetch(url, {
      method,
      headers: { "X-API-Key": this.apiKey, "Accept": "application/json", "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(this.timeout),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Linkify request failed (${response.status})`);
    return data;
  }

  search(query, options = {}) {
    return this.request("search/", { params: { q: query, type: "movie", country: "us", ...options } });
  }
  searchResults(query, options = {}) {
    return this.request("search/results/", { params: { q: query, type: "movie", page: 1, ...options } });
  }
  details(type, id, country = "US") {
    return this.request(`media/${type}/${id}/`, { params: { country } });
  }
  trending(type = "all") { return this.request("trending/", { params: { type } }); }
  searchPeople(query) { return this.request("people/search/", { params: { q: query } }); }
  batch(items) { return this.request("batch/", { method: "POST", body: { items } }); }
  usage() { return this.request("usage/"); }
}
