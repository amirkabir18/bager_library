export const config = {
  runtime: "edge",
};

export default async function handler(request) {
  const secret = process.env.RELAY_SECRET;
  if (secret && request.headers.get("X-Relay-Secret") !== secret) {
    return new Response("Unauthorized", { status: 401 });
  }

  const url = new URL(request.url);
  const targetUrl = new URL(url.pathname + url.search, "https://api.telegram.org");

  return fetch(targetUrl, {
    method: request.method,
    headers: request.headers,
    body: request.body,
  });
}
