/**
 * Cloudflare Email Worker — receives status page notification emails
 * and forwards them as webhook POSTs to the status-monitor server.
 *
 * This turns email notifications into webhook events, enabling
 * event-driven monitoring for status pages that don't support webhooks.
 */

export interface Env {
  WEBHOOK_URL: string;
}

export default {
  async email(message: ForwardableEmailMessage, env: Env): Promise<void> {
    const from = message.from;
    const to = message.to;
    const subject = message.headers.get("subject") || "(no subject)";

    // Read the raw email body
    const reader = message.raw.getReader();
    const chunks: Uint8Array[] = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value) chunks.push(value);
    }
    const rawEmail = new TextDecoder().decode(
      concatenate(chunks)
    );

    // Extract plain text body from the raw email
    const body = extractTextBody(rawEmail);

    // Build a normalized webhook payload
    const payload = {
      source: "email",
      from,
      to,
      subject,
      body: body.slice(0, 2000), // cap body size
      received_at: new Date().toISOString(),
    };

    console.log(`Email received: from=${from} subject="${subject}"`);

    // POST to webhook
    try {
      const resp = await fetch(env.WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      console.log(`Webhook response: ${resp.status}`);
    } catch (err) {
      console.error(`Webhook POST failed: ${err}`);
    }
  },
};

function concatenate(arrays: Uint8Array[]): Uint8Array {
  const totalLength = arrays.reduce((sum, arr) => sum + arr.length, 0);
  const result = new Uint8Array(totalLength);
  let offset = 0;
  for (const arr of arrays) {
    result.set(arr, offset);
    offset += arr.length;
  }
  return result;
}

function extractTextBody(raw: string): string {
  // Try to find a text/plain section in the MIME message
  const plainBoundaryMatch = raw.match(
    /Content-Type:\s*text\/plain[^\r\n]*\r?\n(?:[\w-]+:[^\r\n]*\r?\n)*\r?\n([\s\S]*?)(?:\r?\n--|\r?\n\r?\n--)/i
  );
  if (plainBoundaryMatch) {
    return cleanBody(plainBoundaryMatch[1]);
  }

  // Fallback: strip HTML tags from an HTML section
  const htmlMatch = raw.match(
    /Content-Type:\s*text\/html[^\r\n]*\r?\n(?:[\w-]+:[^\r\n]*\r?\n)*\r?\n([\s\S]*?)(?:\r?\n--)/i
  );
  if (htmlMatch) {
    return cleanBody(
      htmlMatch[1]
        .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
        .replace(/<[^>]+>/g, " ")
        .replace(/&nbsp;/g, " ")
        .replace(/&amp;/g, "&")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
    );
  }

  // Last resort: return everything after the headers
  const headerEnd = raw.indexOf("\r\n\r\n");
  if (headerEnd > 0) {
    return cleanBody(raw.slice(headerEnd + 4));
  }

  return raw.slice(0, 500);
}

function cleanBody(text: string): string {
  return text
    .replace(/=\r?\n/g, "")  // quoted-printable soft line breaks
    .replace(/=([0-9A-Fa-f]{2})/g, (_, hex) =>
      String.fromCharCode(parseInt(hex, 16))
    )
    .replace(/\s+/g, " ")
    .trim();
}
