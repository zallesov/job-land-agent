/// <reference path="../pb_data/types.d.ts" />

// Historical record of the 2026-06-23 cleanup: drop two dead collections that
// were never wired into any code.
//
//   - `users`        PocketBase default auth scaffold, 0 records, 0 code refs.
//                    Admin auth goes through `_superusers` instead.
//   - `applications` scaffolded for application tracking, never used, 0 records,
//                    0 code refs.
//
// IMPORTANT: this instance never had migrations before tonight. When the
// migrations dir is first mounted, PocketBase will treat this file as
// "never applied" and run it against the ALREADY-current schema (where these
// collections are already gone). Each delete is therefore guarded so a replay
// against the current state no-ops cleanly instead of erroring.

migrate(
  (app) => {
    // up: drop the collections if they still exist.
    for (const name of ["users", "applications"]) {
      let collection = null;
      try {
        collection = app.findCollectionByNameOrId(name);
      } catch (_) {
        // already absent — nothing to do.
      }
      if (collection) {
        app.delete(collection);
      }
    }
  },
  (app) => {
    // down: recreate minimal versions. These were empty (0 records) and unused,
    // so the down path only needs to restore enough structure to satisfy a
    // rollback, not the original field set.
    let hasUsers = true;
    try {
      app.findCollectionByNameOrId("users");
    } catch (_) {
      hasUsers = false;
    }
    if (!hasUsers) {
      const users = new Collection({
        type: "auth",
        name: "users",
        fields: [],
      });
      app.save(users);
    }

    let hasApplications = true;
    try {
      app.findCollectionByNameOrId("applications");
    } catch (_) {
      hasApplications = false;
    }
    if (!hasApplications) {
      const applications = new Collection({
        type: "base",
        name: "applications",
        fields: [],
      });
      app.save(applications);
    }
  }
);
