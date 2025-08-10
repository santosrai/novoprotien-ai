/* Simple test client for the multi-agent route */
import http from 'node:http';

function postJson(url, data) {
  return new Promise((resolve, reject) => {
    const { hostname, port, pathname } = new URL(url);
    const payload = Buffer.from(JSON.stringify(data));
    const req = http.request(
      {
        hostname,
        port: Number(port) || 80,
        path: pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': String(payload.length),
        },
      },
      (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => {
          try {
            const json = JSON.parse(body || '{}');
            resolve({ status: res.statusCode || 0, json });
          } catch (e) {
            resolve({ status: res.statusCode || 0, text: body });
          }
        });
      }
    );
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

const run = async () => {
  const result = await postJson('http://localhost:8787/api/agents/route', {
    input: 'hi',
  });
  console.log(JSON.stringify(result, null, 2));
};

run().catch((e) => {
  console.error(e);
  process.exit(1);
});


