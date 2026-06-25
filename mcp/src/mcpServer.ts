import { McpServer } from '@modelcontextprotocol/server';
import * as z from 'zod/v4';
import { createJoblandToolHandlers, type JoblandRecordGateway } from './toolHandlers.js';
import type { AuthInfo } from './auth.js';

const idSchema = z.object({ id: z.string().min(1) });
const fieldsSchema = z.record(z.string(), z.unknown());
const listSchema = z.object({
  filter: z.string().optional(),
  sort: z.string().optional(),
  page: z.number().int().positive().optional(),
  perPage: z.number().int().positive().max(500).optional(),
});
const searchSchema = z.object({
  query: z.string().min(1),
  page: z.number().int().positive().optional(),
  perPage: z.number().int().positive().max(500).optional(),
});

function asToolResult(value: unknown) {
  return {
    content: [{ type: 'text' as const, text: JSON.stringify(value, null, 2) }],
    structuredContent: { result: value },
  };
}

export function createMcpServer(pb: JoblandRecordGateway, auth: AuthInfo): McpServer {
  const server = new McpServer({ name: 'joblandagent-mcp', version: '0.1.0' });
  const tools = createJoblandToolHandlers(pb, auth);

  server.registerTool('jobs_list', {
    title: 'List jobs',
    description: 'List non-deleted jobs with optional filter, sort, and pagination.',
    inputSchema: listSchema,
  }, async (input) => asToolResult(await tools.jobs_list(input)));

  server.registerTool('jobs_get', {
    title: 'Get job',
    description: 'Get one job record by id.',
    inputSchema: idSchema,
  }, async (input) => asToolResult(await tools.jobs_get(input)));

  server.registerTool('jobs_create', {
    title: 'Create job',
    description: 'Create a job record with supported fields.',
    inputSchema: z.object({ fields: fieldsSchema }),
  }, async (input) => asToolResult(await tools.jobs_create(input)));

  server.registerTool('jobs_update', {
    title: 'Update job',
    description: 'Patch arbitrary editable fields on a job record. System fields are rejected.',
    inputSchema: z.object({ id: z.string().min(1), fields: fieldsSchema }),
  }, async (input) => asToolResult(await tools.jobs_update(input)));

  server.registerTool('jobs_delete', {
    title: 'Soft-delete job',
    description: 'Soft-delete a job by setting deleted_at and updated_at. Does not hard-delete.',
    inputSchema: idSchema,
  }, async (input) => asToolResult(await tools.jobs_delete(input)));

  server.registerTool('jobs_find_by_url', {
    title: 'Find job by URL',
    description: 'Find the first non-deleted job matching an exact URL.',
    inputSchema: z.object({ url: z.string().url() }),
  }, async (input) => asToolResult(await tools.jobs_find_by_url(input)));

  server.registerTool('jobs_search', {
    title: 'Search jobs',
    description: 'Search common job text fields.',
    inputSchema: searchSchema,
  }, async (input) => asToolResult(await tools.jobs_search(input)));

  server.registerTool('interviews_list', {
    title: 'List interviews',
    description: 'List interviews with optional filter, sort, and pagination.',
    inputSchema: listSchema,
  }, async (input) => asToolResult(await tools.interviews_list(input)));

  server.registerTool('interviews_get', {
    title: 'Get interview',
    description: 'Get one interview record by id.',
    inputSchema: idSchema,
  }, async (input) => asToolResult(await tools.interviews_get(input)));

  server.registerTool('interviews_create', {
    title: 'Create interview',
    description: 'Create an interview record with supported fields.',
    inputSchema: z.object({ fields: fieldsSchema }),
  }, async (input) => asToolResult(await tools.interviews_create(input)));

  server.registerTool('interviews_update', {
    title: 'Update interview',
    description: 'Patch arbitrary editable fields on an interview record. System fields are rejected.',
    inputSchema: z.object({ id: z.string().min(1), fields: fieldsSchema }),
  }, async (input) => asToolResult(await tools.interviews_update(input)));

  server.registerTool('interviews_delete', {
    title: 'Delete interview',
    description: 'Hard-delete an interview record.',
    inputSchema: idSchema,
  }, async (input) => asToolResult(await tools.interviews_delete(input)));

  server.registerTool('interviews_search', {
    title: 'Search interviews',
    description: 'Search common interview text fields.',
    inputSchema: searchSchema,
  }, async (input) => asToolResult(await tools.interviews_search(input)));

  return server;
}
