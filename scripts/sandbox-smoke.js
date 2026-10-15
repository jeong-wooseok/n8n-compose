// Run inside n8n with `docker compose exec -T n8n node < scripts/sandbox-smoke.js`.
// Credentials stay in the container environment and are never logged.
const { randomUUID } = require('node:crypto');

async function main() {
  const base = process.env.N8N_SANDBOX_SERVICE_URL;
  const key = process.env.N8N_SANDBOX_SERVICE_API_KEY;
  if (!base || !key) throw new Error('Sandbox URL/API key is missing');
  const id = randomUUID();
  let created = false;
  async function request(path, options = {}) {
    return fetch(base + path, {
      ...options,
      headers: { 'X-Api-Key': key, 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(180000),
    });
  }
  try {
    const response = await request('/sandboxes', {
      method: 'POST', body: JSON.stringify({ id }),
    });
    if (!response.ok) throw new Error(`Sandbox creation returned HTTP ${response.status}`);
    created = true;
    if ((await response.json()).id !== id) throw new Error('Sandbox ID mismatch');
    const execution = await request(`/sandboxes/${id}/executions`, {
      method: 'POST',
      body: JSON.stringify({ command: "printf 'sandbox-smoke-ok\\n'", workdir: '/home/user',
        timeout_ms: 10000, exec_id: randomUUID() }),
    });
    if (!execution.ok) throw new Error(`Sandbox execution returned HTTP ${execution.status}`);
    const events = (await execution.text()).trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
    const output = events.filter(e => e.type === 'stdout').map(e => e.data || '').join('');
    const exit = events.find(e => e.type === 'exit');
    if (events.some(e => e.type === 'error') || !exit || exit.exit_code !== 0 ||
        exit.success !== true || !output.includes('sandbox-smoke-ok')) {
      throw new Error('Sandbox did not produce the expected successful command output');
    }
  } finally {
    // DELETE also handles uncertain creation outcomes; a 404 means nothing remains.
    const deletion = await request(`/sandboxes/${id}`, { method: 'DELETE' });
    if (deletion.status !== 204 && deletion.status !== 404) {
      throw new Error(`Sandbox cleanup failed for ${id}: HTTP ${deletion.status}`);
    }
    if (created && (await request(`/sandboxes/${id}`)).status !== 404) {
      throw new Error(`Sandbox still exists after cleanup: ${id}`);
    }
  }
  console.log('PASS sandbox authenticated create/execute/delete');
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
