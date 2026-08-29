import frappe


def execute():
	"""
	Runs post_model_sync, after Spa Type Duration's table exists. Reads
	back whatever stash_spa_type_rates (pre_model_sync) saved from Spa
	Type's old flat `item`/`rate` fields and turns each into a single
	"Fixed" (duration_minutes=0) row in the new `durations` child table,
	so no existing pricing data is silently lost by the schema change.
	"""
	if not frappe.db.table_exists("__spa_type_rate_migration"):
		return

	rows = frappe.db.sql(
		"select spa_type, item, rate from `__spa_type_rate_migration`", as_dict=True
	)

	for row in rows:
		if not frappe.db.exists("Spa Type", row.spa_type):
			continue
		# Don't duplicate rows if this patch is re-run after already migrating.
		if frappe.db.exists(
			"Spa Type Duration", {"parent": row.spa_type, "parenttype": "Spa Type"}
		):
			continue

		doc = frappe.get_doc("Spa Type", row.spa_type)
		doc.append(
			"durations",
			{
				"duration_minutes": 0,
				"rate": row.rate or 0,
				"item": row.item or row.spa_type,
			},
		)
		doc.save(ignore_permissions=True)

	frappe.db.sql("drop table if exists `__spa_type_rate_migration`")
	frappe.db.commit()
