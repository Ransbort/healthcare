import frappe


def execute():
	"""
	Runs pre_model_sync, before the DocType sync drops Spa Type's old
	`item`/`rate` columns (replaced by the `durations` child table on
	Spa Type Duration). Stashes any existing values in a scratch table so
	migrate_spa_type_rates_to_durations (post_model_sync) can turn them
	into a "Fixed" (duration_minutes=0) row once the child table exists.
	"""
	if not frappe.db.table_exists("Spa Type"):
		return

	columns = frappe.db.get_table_columns("Spa Type")
	if "rate" not in columns and "item" not in columns:
		# Already migrated (or a fresh install past this point) - nothing to stash.
		return

	rows = frappe.db.sql(
		"""select name, item, rate from `tabSpa Type`
		   where coalesce(item, '') != '' or coalesce(rate, 0) != 0""",
		as_dict=True,
	)
	if not rows:
		return

	frappe.db.sql(
		"""create table if not exists `__spa_type_rate_migration` (
			spa_type varchar(140),
			item varchar(140),
			rate decimal(21,9)
		)"""
	)
	frappe.db.sql("delete from `__spa_type_rate_migration`")
	for row in rows:
		frappe.db.sql(
			"insert into `__spa_type_rate_migration` (spa_type, item, rate) values (%s, %s, %s)",
			(row.name, row.item, row.rate),
		)
	frappe.db.commit()
