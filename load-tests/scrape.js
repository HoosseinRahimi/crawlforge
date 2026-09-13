import http from 'k6/http';
import { check, sleep } from 'k6';
export const options = { vus: 5, duration: '30s' };
const base = __ENV.BASE_URL || 'http://localhost:8000';
const key = __ENV.CRAWLFORGE_API_KEY || '';
export default function () {
  check(http.get(`${base}/health`), { 'health is 200': (r) => r.status === 200 });
  const params = { headers: { Authorization: `Bearer ${key}` } };
  check(http.post(`${base}/v1/scrape`, JSON.stringify({ url: 'https://example.com', render_js: false, output: ['markdown'] }), params), { 'scrape accepted': (r) => [200, 429].includes(r.status) });
  check(http.post(`${base}/v1/jobs`, JSON.stringify({ url: 'https://example.com', render_js: false, output: ['markdown'] }), params), { 'job accepted': (r) => [202, 429].includes(r.status) });
  sleep(1);
}
