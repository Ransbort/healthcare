# Copyright (c) 2026, Ransbort and contributors
# For license information, please see license.txt

"""
Backend for the Rehab Portal page (page/rehab_portal/rehab_portal.js).
Mirrors lab_portal.py's structure, mapped to therapy prescriptions instead
of lab test prescriptions.

Two request sources feed each tab:
  1. Encounter-sourced: Patient Encounter -> Therapy Plan Detail (child
     table `therapies`) -> sits in Requested Therapies until a therapist
     accepts it into a Therapy Plan + Sales Invoice via
     accept_therapy_request().
  2. Direct-sourced: a standalone Therapy Plan with no originating Patient
     Encounter, created via create_therapy_request() by a therapist who
     doesn't need a doctor's encounter first. Since creating it IS the
     therapist's acceptance, it's invoiced immediately on creation and goes
     straight to Pending Therapies, skipping Requested Therapies entirely -
     same pattern as Lab Portal's direct Lab Test requests.

Unlike Lab Test, Therapy Plan has no native field that distinguishes an
encounter-sourced record from a direct one (Lab Test has `prescription`,
set only when created off a Lab Prescription row). Therapy Plan does have a
generic `source_doc`/`order_group` Link/Dynamic-Link pair, but its native
purpose is tied to the Service Request order flow (see
`healthcare_service_order_doctypes` in hooks.py) and is not something this
portal should repurpose without risking a collision with native code that
also reads/writes it. `custom_source_encounter` (Link -> Patient Encounter,
added via setup.py) is a new dedicated field instead, following the same
custom-field pattern already used for `custom_invoice` on this doctype and
`custom_priority`/`custom_therapy_plan` on Therapy Plan Detail: set to the
originating encounter for encounter-sourced plans, left blank for direct
ones.

Both sources are queried separately (different columns) then normalized to
a common row shape with a `source` field ("encounter" | "direct") so the
frontend knows which accept endpoint to call.

Schema notes:
- `Patient Encounter.diagnosis` is a Table MultiSelect (child doctype
  `Patient Encounter Diagnosis`), not a plain column - pulled via a
  correlated GROUP_CONCAT subquery (_DIAGNOSIS_SUBQUERY).
- `Therapy Plan Detail` (the `therapies` child table on Patient Encounter)
  has no native `invoiced` field (unlike Lab Prescription, which does) -
  "has this row been accepted into a Therapy Plan yet" is tracked purely by
  whether `custom_therapy_plan` is NULL (not yet accepted / Requested) or
  set (accepted / Pending or Completed, depending on the linked Therapy
  Plan's status). It also has no comment/note field, so unlike Lab
  Portal's lab_test_comment, there's nowhere to store an optional note on
  a direct therapy request - create_therapy_request() has no comment
  parameter for this reason.
- `Therapy Plan.practitioner` is mandatory (reqd=1, confirmed via the
  doctype JSON) - unlike Lab Test, which has no such requirement. Every
  Therapy Plan created here (both accept_therapy_request() and
  create_therapy_request()) must be given a practitioner; the "New Therapy
  Request" dialog collects one explicitly since a direct request has no
  encounter to pull it from.
- `Therapy Plan` has no built-in Sales Invoice link - `custom_invoice` is a
  custom field, same pattern as Lab Test's custom_invoice.
- `interval` is a reserved word in MySQL/MariaDB - table-qualified
  references (`tpd.interval`) are fine, but it must be backtick-quoted
  when used as an alias (`AS \`interval\``).
- Payment status is read off the linked Sales Invoice's `status` field.
"""

import frappe
from frappe import _
from frappe.utils import cint, today


def _notify(event, payload):
	"""Broadcast a realtime event to everyone listening in this site."""
	frappe.publish_realtime(event=event, message=payload)


def notify_new_therapy_requests(doc, method=None):
	"""Hooked on Patient Encounter on_update (alongside lab_portal.py's
	notify_new_lab_requests). Fires on every save (not just submit, since
	docstatus can stay 0 in walk-in workflows) and diffs against the
	pre-save state to avoid re-notifying on unrelated saves.
	"""
	before_save = doc.get_doc_before_save()
	old_names = set()
	if before_save:
		old_names = {row.name for row in before_save.get("therapies", [])}

	new_pending = [
		row for row in doc.get("therapies", [])
		if not row.custom_therapy_plan and row.name not in old_names
	]

	if not new_pending:
		return

	_notify("queue_update", {
		"department": "rehabilitation",
		"message": f"New therapy request(s) for {doc.patient_name} ({len(new_pending)})",
		"encounter": doc.name,
	})


# Aggregates every diagnosis linked to an encounter into one
# comma-separated string. Requires `pe` aliased in the outer query.
_DIAGNOSIS_SUBQUERY = """
	(
		SELECT GROUP_CONCAT(ped.diagnosis SEPARATOR ', ')
		FROM `tabPatient Encounter Diagnosis` ped
		WHERE ped.parent = pe.name
	) AS diagnosis
"""


def _rehab_search_conditions(search_patient, search_encounter, search_date, date_field="pe.encounter_date"):
	conditions = []
	values = {}

	if search_patient:
		conditions.append("(pe.patient LIKE %(search_patient)s OR pe.patient_name LIKE %(search_patient)s)")
		values["search_patient"] = f"%{search_patient}%"

	if search_encounter:
		conditions.append("pe.name = %(search_encounter)s")
		values["search_encounter"] = search_encounter

	if search_date:
		conditions.append(f"{date_field} = %(search_date)s")
		values["search_date"] = search_date

	return conditions, values


def _direct_search_conditions(search_patient, search_encounter, search_date, date_field="tp.creation"):
	"""Same shape as _rehab_search_conditions but against Therapy Plan
	directly. search_encounter is ignored - direct requests have no
	encounter.
	"""
	conditions = []
	values = {}
	if search_patient:
		conditions.append("(tp.patient LIKE %(search_patient)s OR tp.patient_name LIKE %(search_patient)s)")
		values["search_patient"] = f"%{search_patient}%"
	if search_date:
		conditions.append(f"DATE({date_field}) = %(search_date)s")
		values["search_date"] = search_date
	return conditions, values


def _normalize_direct_row(row):
	"""Reshape a direct Therapy Plan row into the same keys as
	encounter-sourced rows so rehab_portal.js can render both with one code
	path.

	Uses .get() instead of [] since drifting SQL SELECTs between the three
	callers is an easy way to raise a KeyError here (same defensive pattern
	as lab_portal.py's _normalize_direct_row).
	"""
	return {
		"therapy_id": None,
		"therapy_plan_name": row.get("therapy_plan_name"),  # the Therapy Plan's own name - used to accept/view it
		"therapy_type": row.get("therapy_type"),
		"no_of_sessions": row.get("no_of_sessions"),
		"interval": None,
		"priority": None,
		"custom_therapy_plan": row.get("custom_therapy_plan"),
		"encounter_id": None,
		"patient": row.get("patient"),
		"patient_name": row.get("patient_name"),
		"encounter_date": row.get("encounter_date"),
		"practitioner": row.get("practitioner"),
		"diagnosis": None,
		"source": "direct",
	}


@frappe.whitelist()
def get_therapy_types():
	"""Active Therapy Types for the 'New Therapy Request' picker."""
	types = frappe.get_all(
		"Therapy Type",
		filters={"disabled": 0},
		fields=["name", "item"],
		order_by="name asc",
	)
	for t in types:
		t["rate"] = frappe.db.get_value("Item Price", {"item_code": t.item}, "price_list_rate") or 0
	return types


@frappe.whitelist()
def create_therapy_request(patient, therapy_type, no_of_sessions=1, practitioner=None):
	"""Create a Therapy Plan requested directly by a therapist, with no
	Patient Encounter involved. Unlike encounter-sourced requests (which
	sit in Requested Therapies until a therapist accepts them), a direct
	request IS the therapist's own acceptance - so it's invoiced
	immediately here and goes straight to Pending Therapies (awaiting
	payment) rather than through Requested Therapies.

	practitioner is required here (unlike Lab Portal's equivalent) because
	Therapy Plan.practitioner is mandatory and there's no encounter to pull
	it from.
	"""
	if not patient:
		frappe.throw(_("Please select a patient"))
	if not therapy_type:
		frappe.throw(_("Please select a therapy type"))
	if not practitioner:
		frappe.throw(_("Please select a practitioner"))

	patient_doc = frappe.get_doc("Patient", patient)

	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not company:
		frappe.throw(_("No default Company is configured - cannot create Therapy Plan without one"))

	no_of_sessions = cint(no_of_sessions) or 1

	therapy_plan = frappe.get_doc(
		{
			"doctype": "Therapy Plan",
			"patient": patient,
			"patient_name": patient_doc.patient_name,
			"status": "Draft",
			"start_date": today(),
			"practitioner": practitioner,
			"company": company,
			# custom_source_encounter deliberately left unset - this is how
			# get_requested/pending/completed_therapies tell a direct plan
			# apart from an encounter-sourced one.
			"therapy_plan_details": [
				{
					"therapy_type": therapy_type,
					"no_of_sessions": no_of_sessions,
				}
			],
		}
	)
	therapy_plan.insert(ignore_permissions=True)

	invoice = _create_therapy_invoice(
		patient_doc, therapy_type, no_of_sessions, reference_dt="Therapy Plan", reference_dn=therapy_plan.name
	)
	therapy_plan.db_set("custom_invoice", invoice.name)

	_notify("queue_update", {
		"department": "rehabilitation",
		"message": f"New direct therapy request for {patient_doc.patient_name}",
		"therapy_plan": therapy_plan.name,
	})

	return {"status": "Success", "therapy_plan_name": therapy_plan.name, "invoice_name": invoice.name}


@frappe.whitelist()
def get_requested_therapies(search_patient=None, search_encounter=None, search_date=None):
	"""Therapies prescribed on an encounter but not yet accepted/invoiced -
	merges encounter-sourced (Therapy Plan Detail) and direct-sourced
	(standalone Therapy Plan, fallback only - see create_therapy_request's
	docstring) requests."""

	conditions, values = _rehab_search_conditions(search_patient, search_encounter, search_date)
	conditions.insert(0, "tpd.custom_therapy_plan IS NULL")
	where_clause = " AND ".join(conditions)

	encounter_rows = frappe.db.sql(
		f"""
		SELECT
			tpd.name AS therapy_id,
			tpd.therapy_type AS therapy_type,
			tpd.no_of_sessions AS no_of_sessions,
			tpd.interval AS `interval`,
			tpd.custom_priority AS priority,
			pe.name AS encounter_id,
			pe.patient AS patient,
			pe.patient_name AS patient_name,
			pe.encounter_date AS encounter_date,
			pe.practitioner AS practitioner,
			{_DIAGNOSIS_SUBQUERY},
			'encounter' AS source
		FROM `tabTherapy Plan Detail` tpd
		INNER JOIN `tabPatient Encounter` pe ON pe.name = tpd.parent
		WHERE {where_clause}
		ORDER BY pe.encounter_date DESC
		""",
		values,
		as_dict=True,
	)

	if search_encounter:
		# Direct requests have no encounter to match.
		return encounter_rows

	d_conditions, d_values = _direct_search_conditions(search_patient, search_encounter, search_date)
	d_conditions[0:0] = ["tp.custom_source_encounter IS NULL", "tp.custom_invoice IS NULL", "tp.status = 'Draft'"]
	d_where = " AND ".join(d_conditions)
	direct_rows = frappe.db.sql(
		f"""
		SELECT
			tp.name AS therapy_plan_name,
			tpd.therapy_type AS therapy_type,
			tpd.no_of_sessions AS no_of_sessions,
			NULL AS custom_therapy_plan,
			tp.patient AS patient,
			tp.patient_name AS patient_name,
			tp.creation AS encounter_date,
			tp.practitioner AS practitioner
		FROM `tabTherapy Plan` tp
		INNER JOIN `tabTherapy Plan Detail` tpd ON tpd.parent = tp.name
		WHERE {d_where}
		ORDER BY tp.creation DESC
		""",
		d_values,
		as_dict=True,
	)

	return encounter_rows + [_normalize_direct_row(r) for r in direct_rows]


@frappe.whitelist()
def get_pending_therapies(search_patient=None, search_encounter=None, search_date=None):
	"""Accepted (invoiced) therapies whose Therapy Plan isn't Completed yet -
	merges encounter-sourced and direct-sourced requests."""

	conditions, values = _rehab_search_conditions(search_patient, search_encounter, search_date)
	conditions[0:0] = [
		"tpd.custom_therapy_plan IS NOT NULL",
		"tp.status != 'Completed'",
	]
	where_clause = " AND ".join(conditions)

	encounter_rows = frappe.db.sql(
		f"""
		SELECT
			tpd.name AS therapy_id,
			tpd.therapy_type AS therapy_type,
			tpd.no_of_sessions AS no_of_sessions,
			tpd.interval AS `interval`,
			tpd.custom_priority AS priority,
			tpd.custom_therapy_plan AS custom_therapy_plan,
			pe.name AS encounter_id,
			pe.patient AS patient,
			pe.patient_name AS patient_name,
			pe.encounter_date AS encounter_date,
			pe.practitioner AS practitioner,
			{_DIAGNOSIS_SUBQUERY},
			si.status AS invoice_status,
			'encounter' AS source
		FROM `tabTherapy Plan Detail` tpd
		INNER JOIN `tabPatient Encounter` pe ON pe.name = tpd.parent
		INNER JOIN `tabTherapy Plan` tp ON tp.name = tpd.custom_therapy_plan
		LEFT JOIN `tabSales Invoice` si ON si.name = tp.custom_invoice
		WHERE {where_clause}
		ORDER BY pe.encounter_date DESC
		""",
		values,
		as_dict=True,
	)
	for row in encounter_rows:
		row["payment_status"] = "Paid" if row.pop("invoice_status", None) == "Paid" else "Unpaid"

	if search_encounter:
		return encounter_rows

	d_conditions, d_values = _direct_search_conditions(search_patient, search_encounter, search_date)
	d_conditions[0:0] = [
		"tp.custom_source_encounter IS NULL",
		"tp.custom_invoice IS NOT NULL",
		"tp.status != 'Completed'",
	]
	d_where = " AND ".join(d_conditions)
	direct_rows = frappe.db.sql(
		f"""
		SELECT
			tp.name AS therapy_plan_name,
			tp.name AS custom_therapy_plan,
			tpd.therapy_type AS therapy_type,
			tpd.no_of_sessions AS no_of_sessions,
			tp.patient AS patient,
			tp.patient_name AS patient_name,
			tp.creation AS encounter_date,
			tp.practitioner AS practitioner,
			si.status AS invoice_status
		FROM `tabTherapy Plan` tp
		INNER JOIN `tabTherapy Plan Detail` tpd ON tpd.parent = tp.name
		LEFT JOIN `tabSales Invoice` si ON si.name = tp.custom_invoice
		WHERE {d_where}
		ORDER BY tp.creation DESC
		""",
		d_values,
		as_dict=True,
	)
	normalized_direct = []
	for r in direct_rows:
		row = _normalize_direct_row(r)
		row["payment_status"] = "Paid" if r.get("invoice_status") == "Paid" else "Unpaid"
		normalized_direct.append(row)

	return encounter_rows + normalized_direct


@frappe.whitelist()
def get_completed_therapies(search_patient=None, search_encounter=None, filter_date=None):
	"""Therapies whose Therapy Plan has been marked Completed - merges
	encounter-sourced and direct-sourced requests."""

	conditions, values = _rehab_search_conditions(
		search_patient, search_encounter, filter_date, date_field="DATE(tp.modified)"
	)
	conditions[0:0] = [
		"tpd.custom_therapy_plan IS NOT NULL",
		"tp.status = 'Completed'",
	]
	where_clause = " AND ".join(conditions)

	encounter_rows = frappe.db.sql(
		f"""
		SELECT
			tpd.name AS therapy_id,
			tpd.therapy_type AS therapy_type,
			tpd.no_of_sessions AS no_of_sessions,
			tpd.custom_therapy_plan AS custom_therapy_plan,
			pe.name AS encounter_id,
			pe.patient AS patient,
			pe.patient_name AS patient_name,
			pe.encounter_date AS encounter_date,
			pe.practitioner AS practitioner,
			{_DIAGNOSIS_SUBQUERY},
			'encounter' AS source
		FROM `tabTherapy Plan Detail` tpd
		INNER JOIN `tabPatient Encounter` pe ON pe.name = tpd.parent
		INNER JOIN `tabTherapy Plan` tp ON tp.name = tpd.custom_therapy_plan
		WHERE {where_clause}
		ORDER BY tp.modified DESC
		""",
		values,
		as_dict=True,
	)

	if search_encounter:
		return encounter_rows

	d_conditions, d_values = _direct_search_conditions(
		search_patient, search_encounter, filter_date, date_field="tp.modified"
	)
	d_conditions[0:0] = ["tp.custom_source_encounter IS NULL", "tp.status = 'Completed'"]
	d_where = " AND ".join(d_conditions)
	direct_rows = frappe.db.sql(
		f"""
		SELECT
			tp.name AS therapy_plan_name,
			tp.name AS custom_therapy_plan,
			tpd.therapy_type AS therapy_type,
			tpd.no_of_sessions AS no_of_sessions,
			tp.patient AS patient,
			tp.patient_name AS patient_name,
			tp.modified AS encounter_date,
			tp.practitioner AS practitioner
		FROM `tabTherapy Plan` tp
		INNER JOIN `tabTherapy Plan Detail` tpd ON tpd.parent = tp.name
		WHERE {d_where}
		ORDER BY tp.modified DESC
		""",
		d_values,
		as_dict=True,
	)

	return encounter_rows + [_normalize_direct_row(r) for r in direct_rows]


@frappe.whitelist()
def accept_therapy_request(therapy_id, patient_id, encounter_id, therapy_type):
	"""
	Accept an encounter-sourced request: create + submit a Sales Invoice,
	create a draft Therapy Plan (stamped with custom_source_encounter so
	it's identifiable as encounter-sourced), then stamp the originating
	Therapy Plan Detail row so it shows up under Pending instead of
	Requested on the next reload.
	"""

	encounter = frappe.get_doc("Patient Encounter", encounter_id)

	therapy_row = None
	for row in encounter.therapies:
		if row.name == therapy_id:
			therapy_row = row
			break

	if not therapy_row:
		frappe.throw(_("Therapy Plan Detail row {0} not found on encounter {1}").format(therapy_id, encounter_id))

	if therapy_row.custom_therapy_plan:
		frappe.throw(_("Therapy request {0} has already been accepted").format(therapy_id))

	patient = frappe.get_doc("Patient", patient_id)

	no_of_sessions = therapy_row.no_of_sessions or 1

	invoice = _create_therapy_invoice(
		patient, therapy_type, no_of_sessions, reference_dt="Patient Encounter", reference_dn=encounter_id
	)

	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not company:
		frappe.throw(_("No default Company is configured - cannot create Therapy Plan without one"))

	therapy_plan = frappe.get_doc(
		{
			"doctype": "Therapy Plan",
			"patient": patient_id,
			"patient_name": patient.patient_name,
			"custom_invoice": invoice.name,
			"custom_source_encounter": encounter_id,
			"status": "Draft",
			"start_date": today(),
			"practitioner": encounter.practitioner,
			"company": company,
			"therapy_plan_details": [
				{
					"therapy_type": therapy_type,
					"no_of_sessions": no_of_sessions,
				}
			],
		}
	)
	therapy_plan.insert(ignore_permissions=True)

	therapy_row.db_set("custom_therapy_plan", therapy_plan.name)

	return {
		"status": "Success",
		"invoice_name": invoice.name,
		"therapy_plan_name": therapy_plan.name,
	}


@frappe.whitelist()
def accept_direct_therapy_request(therapy_plan_name):
	"""Accept a direct-sourced request: invoice the existing draft Therapy
	Plan and link it via custom_invoice, moving it from Requested to
	Pending. Direct requests are normally invoiced immediately on creation
	(see create_therapy_request()) so this is a fallback for the rare case
	one ends up uninvoiced - mirrors Lab Portal's accept_direct_lab_request.
	"""
	therapy_plan = frappe.get_doc("Therapy Plan", therapy_plan_name)
	if therapy_plan.custom_source_encounter:
		frappe.throw(
			_("Therapy Plan {0} is encounter-sourced, use accept_therapy_request instead").format(therapy_plan_name)
		)
	if therapy_plan.custom_invoice:
		frappe.throw(_("Therapy Plan {0} is already invoiced").format(therapy_plan_name))
	if not therapy_plan.therapy_plan_details:
		frappe.throw(_("Therapy Plan {0} has no therapy plan details").format(therapy_plan_name))

	patient = frappe.get_doc("Patient", therapy_plan.patient)
	detail_row = therapy_plan.therapy_plan_details[0]

	invoice = _create_therapy_invoice(
		patient,
		detail_row.therapy_type,
		detail_row.no_of_sessions or 1,
		reference_dt="Therapy Plan",
		reference_dn=therapy_plan.name,
	)

	therapy_plan.db_set("custom_invoice", invoice.name)
	return {
		"status": "Success",
		"invoice_name": invoice.name,
		"therapy_plan_name": therapy_plan.name,
	}


def _create_therapy_invoice(patient, therapy_type, no_of_sessions, reference_dt, reference_dn):
	"""Shared by accept_therapy_request/create_therapy_request/
	accept_direct_therapy_request - builds and submits the Sales Invoice
	for one therapy plan's sessions."""
	customer = patient.customer
	if not customer:
		frappe.throw(_("Patient {0} has no linked Customer").format(patient.name))

	item_code = frappe.db.get_value("Therapy Type", therapy_type, "item")
	if not item_code:
		frappe.throw(_("Therapy Type {0} has no linked Item").format(therapy_type))
	rate = frappe.db.get_value("Item Price", {"item_code": item_code}, "price_list_rate") or 0

	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": customer,
			"patient": patient.name,
			"posting_date": today(),
			# Without this, cashier_portal.py's _get_department_invoices()
			# has no way to bucket this invoice under Rehabilitation - it
			# would fall into "Other Invoices" instead.
			"custom_department": "Rehabilitation",
			"items": [
				{
					"item_code": item_code,
					"qty": no_of_sessions,
					"rate": rate,
					"reference_dt": reference_dt,
					"reference_dn": reference_dn,
				}
			],
		}
	)
	invoice.insert(ignore_permissions=True)
	invoice.submit()
	return invoice


@frappe.whitelist()
def get_print_formats(doctype):
	formats = frappe.get_all(
		"Print Format",
		filters={"doc_type": doctype, "disabled": 0},
		fields=["name"],
		order_by="name asc",
	)
	if not any(f.name == "Standard" for f in formats):
		formats.insert(0, {"name": "Standard"})
	return formats


@frappe.whitelist()
def get_print_content(doctype, docname, print_format=None):
	html = frappe.get_print(doctype, docname, print_format=print_format or None)
	return {"html": html}
