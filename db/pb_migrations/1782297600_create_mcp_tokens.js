/// <reference path="../pb_data/types.d.ts" />

function collectionExists(app, name) {
  try {
    app.findCollectionByNameOrId(name);
    return true;
  } catch (_) {
    return false;
  }
}

migrate(
  (app) => {
    if (collectionExists(app, "mcp_tokens")) return;

    const collection = new Collection({
      type: "base",
      name: "mcp_tokens",
      listRule: null,
      viewRule: null,
      createRule: null,
      updateRule: null,
      deleteRule: null,
      fields: [
        {
          name: "name",
          type: "text",
          required: true,
          max: 120,
        },
        {
          name: "token_hash",
          type: "text",
          required: true,
          max: 64,
        },
        {
          name: "scopes",
          type: "json",
          required: false,
        },
        {
          name: "enabled",
          type: "bool",
          required: false,
        },
        {
          name: "last_used_at",
          type: "date",
          required: false,
        },
        {
          name: "expires_at",
          type: "date",
          required: false,
        },
      ],
      indexes: [
        "CREATE UNIQUE INDEX idx_mcp_tokens_token_hash ON mcp_tokens (token_hash)",
      ],
    });

    app.save(collection);
  },
  (app) => {
    try {
      const collection = app.findCollectionByNameOrId("mcp_tokens");
      app.delete(collection);
    } catch (_) {
      // Already absent.
    }
  }
);

