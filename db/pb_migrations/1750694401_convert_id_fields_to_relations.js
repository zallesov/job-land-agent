/// <reference path="../pb_data/types.d.ts" />

// Historical record of the 2026-06-23 conversion of four text fields that
// stored foreign-key-like ID strings into proper PocketBase `relation` fields.
//
//   jobs.company_id                -> relation to companies, cascadeDelete: false
//   jobs.actual_hiring_company_id  -> relation to companies, cascadeDelete: false
//   job_assessments.job_id         -> relation to jobs,      cascadeDelete: true
//   company_research.company_id    -> relation to companies, cascadeDelete: true
//
// Explicitly NOT converted: interviews.job_id stays plain `text` (it has
// records pointing at deleted jobs and is real personal data — left untouched).
//
// The live conversion was done rename-old -> add-new-relation -> backfill ->
// drop-old via the Admin REST API. As a forward-looking migration the simplest
// correct expression is: ensure each target field is a relation with the right
// options. Because the live schema is ALREADY in the desired state, every step
// here is guarded to no-op on replay. We mutate the field in place by removing
// any existing field of that name and (re)adding it as a relation, which is
// idempotent: re-running leaves an identical relation field.

function collectionId(app, name) {
  return app.findCollectionByNameOrId(name).id;
}

function ensureRelationField(app, collectionName, fieldName, targetCollectionName, cascadeDelete) {
  let collection;
  try {
    collection = app.findCollectionByNameOrId(collectionName);
  } catch (_) {
    // Owning collection doesn't exist (e.g. fresh DB / partial state) — skip.
    return;
  }

  const targetId = collectionId(app, targetCollectionName);

  const existing = collection.fields.getByName(fieldName);
  // If it's already a relation pointing at the right collection with matching
  // cascade behavior, leave it alone.
  if (
    existing &&
    existing.type === "relation" &&
    existing.collectionId === targetId &&
    existing.cascadeDelete === cascadeDelete
  ) {
    return;
  }

  // Drop any stale field of this name (old text field, or mis-configured
  // relation) then add the correct relation field.
  if (existing) {
    collection.fields.removeByName(fieldName);
  }

  collection.fields.add(
    new RelationField({
      name: fieldName,
      collectionId: targetId,
      cascadeDelete: cascadeDelete,
      maxSelect: 1,
      minSelect: 0,
      required: false,
    })
  );

  app.save(collection);
}

function revertToTextField(app, collectionName, fieldName) {
  let collection;
  try {
    collection = app.findCollectionByNameOrId(collectionName);
  } catch (_) {
    return;
  }
  const existing = collection.fields.getByName(fieldName);
  if (existing && existing.type === "text") {
    return; // already text
  }
  if (existing) {
    collection.fields.removeByName(fieldName);
  }
  collection.fields.add(
    new TextField({
      name: fieldName,
      required: false,
    })
  );
  app.save(collection);
}

migrate(
  (app) => {
    ensureRelationField(app, "jobs", "company_id", "companies", false);
    ensureRelationField(app, "jobs", "actual_hiring_company_id", "companies", false);
    ensureRelationField(app, "job_assessments", "job_id", "jobs", true);
    ensureRelationField(app, "company_research", "company_id", "companies", true);
  },
  (app) => {
    // down: convert the relation fields back to plain text. Stored values are
    // record-ID strings, which are valid text, so no data is lost.
    revertToTextField(app, "jobs", "company_id");
    revertToTextField(app, "jobs", "actual_hiring_company_id");
    revertToTextField(app, "job_assessments", "job_id");
    revertToTextField(app, "company_research", "company_id");
  }
);
