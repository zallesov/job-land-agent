import { createServer } from 'node:http';
import { createHttpApp } from './httpApp.js';
import { JoblandPocketBaseGateway } from './pbGateway.js';

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

const port = Number(process.env.PORT ?? '8787');
const host = process.env.HOST ?? '0.0.0.0';

const pb = new JoblandPocketBaseGateway({
  url: requiredEnv('POCKETBASE_URL'),
  adminEmail: requiredEnv('POCKETBASE_ADMIN_EMAIL'),
  adminPassword: requiredEnv('POCKETBASE_ADMIN_PASSWORD'),
});

const app = createHttpApp(pb, {
  envToken: process.env.MCP_API_TOKEN,
  host,
});

createServer(app).listen(port, host, () => {
  console.error(`JobLandAgent MCP server listening on http://${host}:${port}/mcp`);
});
