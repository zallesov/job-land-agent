import { createMcpExpressApp } from '@modelcontextprotocol/express';
import { NodeStreamableHTTPServerTransport } from '@modelcontextprotocol/node';
import type { Express, Request, Response } from 'express';
import { authorizeBearerToken } from './auth.js';
import { createMcpServer } from './mcpServer.js';
import type { JoblandPocketBaseGateway } from './pbGateway.js';

export type HttpAppConfig = {
  envToken?: string;
  host?: string;
};

export function createHttpApp(pb: JoblandPocketBaseGateway, config: HttpAppConfig): Express {
  const app = createMcpExpressApp({ host: config.host ?? '0.0.0.0' });

  app.get('/healthz', (_req: Request, res: Response) => {
    res.json({ ok: true });
  });

  app.post('/mcp', async (req: Request, res: Response) => {
    const authResult = await authorizeBearerToken({
      authorization: req.header('authorization'),
      envToken: config.envToken,
      findDbTokenByHash: (hash) => pb.findMcpTokenByHash(hash),
      markTokenUsed: (id, usedAt) => pb.markMcpTokenUsed(id, usedAt),
    });

    if (!authResult.ok) {
      res.status(authResult.status).json({ error: authResult.error });
      return;
    }

    const server = createMcpServer(pb, authResult.auth);
    const transport = new NodeStreamableHTTPServerTransport({ sessionIdGenerator: undefined });
    await server.connect(transport);
    res.on('close', () => {
      void transport.close();
      void server.close();
    });
    await transport.handleRequest(req, res, req.body);
  });

  return app;
}

