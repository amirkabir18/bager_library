export default {
  async fetch(request, env) {
    const secret = env.RELAY_SECRET;
    if (secret && request.headers.get("X-Relay-Secret") !== secret) {
      return new Response("Unauthorized", { status: 401 });
    }

    const url = new URL(request.url);
    url.hostname = "api.telegram.org";
    url.port = "443";
    url.protocol = "https:";

    const proxyRequest = new Request(url.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.body,
      redirect: "follow",
    });

    return fetch(proxyRequest);
  },
};
