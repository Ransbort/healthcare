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

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, today


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
		"sessions_completed": row.get("sessions_completed"),
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
def get_therapy_plan_templates():
	"""Therapy Plan Templates for the optional picker in 'New Therapy
	Request' - each bundles one or more Therapy Types with a preset number
	of sessions, so a therapist doesn't have to add them one at a time for
	a routine protocol (e.g. "Post-Op Knee Protocol")."""
	return frappe.get_all("Therapy Plan Template", fields=["name"], order_by="name asc")


@frappe.whitelist()
def get_therapy_plan_template_detail(therapy_plan_template):
	"""Therapy type/session breakdown of a template, shown as a preview
	before the therapist commits to it in the New Therapy Request dialog."""
	template = frappe.get_doc("Therapy Plan Template", therapy_plan_template)
	rows = []
	for row in template.therapy_types:
		item = frappe.db.get_value("Therapy Type", row.therapy_type, "item")
		rate = frappe.db.get_value("Item Price", {"item_code": item}, "price_list_rate") or 0 if item else 0
		rows.append(
			{
				"therapy_type": row.therapy_type,
				"no_of_sessions": row.no_of_sessions,
				"interval": row.interval,
				"rate": rate,
			}
		)
	return rows


@frappe.whitelist()
def create_therapy_request(
	patient, therapy_type=None, no_of_sessions=1, practitioner=None, therapy_plan_template=None
):
	"""Create a Therapy Plan requested directly by a therapist, with no
	Patient Encounter involved. Unlike encounter-sourced requests (which
	sit in Requested Therapies until a therapist accepts them), a direct
	request IS the therapist's own acceptance - so it's invoiced
	immediately here and goes straight to Pending Therapies (awaiting
	payment) rather than through Requested Therapies.

	practitioner is required here (unlike Lab Portal's equivalent) because
	Therapy Plan.practitioner is mandatory and there's no encounter to pull
	it from.

	Either therapy_plan_template (builds one therapy_plan_details row per
	template line, mirroring Therapy Plan's own
	set_therapy_details_from_template()) or a manual therapy_type +
	no_of_sessions pair must be supplied - the frontend dialog only ever
	sends one or the other.
	"""
	if not patient:
		frappe.throw(_("Please select a patient"))
	if not practitioner:
		frappe.throw(_("Please select a practitioner"))
	if not therapy_plan_template and not therapy_type:
		frappe.throw(_("Please select a therapy type or a therapy plan template"))

	patient_doc = frappe.get_doc("Patient", patient)

	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not company:
		frappe.throw(_("No default Company is configured - cannot create Therapy Plan without one"))

	if therapy_plan_template:
		template = frappe.get_doc("Therapy Plan Template", therapy_plan_template)
		if not template.therapy_types:
			frappe.throw(_("Therapy Plan Template {0} has no therapy types configured").format(therapy_plan_template))
		plan_details = [
			{
				"therapy_type": row.therapy_type,
				"no_of_sessions": row.no_of_sessions,
				"interval": row.interval,
			}
			for row in template.therapy_types
		]
	else:
		no_of_sessions = cint(no_of_sessions) or 1
		plan_details = [{"therapy_type": therapy_type, "no_of_sessions": no_of_sessions}]

	therapy_plan = frappe.get_doc(
		{
			"doctype": "Therapy Plan",
			"patient": patient,
			"patient_name": patient_doc.patient_name,
			"status": "Draft",
			"start_date": today(),
			"practitioner": practitioner,
			"company": company,
			"therapy_plan_template": therapy_plan_template or None,
			# custom_source_encounter deliberately left unset - this is how
			# get_requested/pending/completed_therapies tell a direct plan
			# apart from an encounter-sourced one.
			"therapy_plan_details": plan_details,
		}
	)
	therapy_plan.insert(ignore_permissions=True)

	invoice = _create_therapy_invoice(
		patient_doc,
		[{"therapy_type": d["therapy_type"], "no_of_sessions": d["no_of_sessions"]} for d in plan_details],
		reference_dt="Therapy Plan",
		reference_dn=therapy_plan.name,
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
			tpd.sessions_completed AS sessions_completed,
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
			tpd.sessions_completed AS sessions_completed,
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
		patient,
		[{"therapy_type": therapy_type, "no_of_sessions": no_of_sessions}],
		reference_dt="Patient Encounter",
		reference_dn=encounter_id,
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

	# notify_new_therapy_requests() above only announces the *request*
	# landing in rehab's queue, before any invoice exists - this is the
	# actual invoice-raising moment (accepting the request is what
	# creates it), and nothing told the Cashier Portal about it until now.
	_notify("queue_update", {
		"department": "cashier",
		"message": f"New invoice pending: {invoice.name}",
		"encounter": None,
	})

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
	items = [
		{"therapy_type": d.therapy_type, "no_of_sessions": d.no_of_sessions or 1}
		for d in therapy_plan.therapy_plan_details
	]

	invoice = _create_therapy_invoice(
		patient,
		items,
		reference_dt="Therapy Plan",
		reference_dn=therapy_plan.name,
	)

	therapy_plan.db_set("custom_invoice", invoice.name)

	# See accept_therapy_request()'s matching note above - this is a
	# separate fallback accept path (a direct request that somehow ended
	# up uninvoiced) and needs the same Cashier Portal notification.
	_notify("queue_update", {
		"department": "cashier",
		"message": f"New invoice pending: {invoice.name}",
		"encounter": None,
	})

	return {
		"status": "Success",
		"invoice_name": invoice.name,
		"therapy_plan_name": therapy_plan.name,
	}


def _create_therapy_invoice(patient, items, reference_dt, reference_dn):
	"""Shared by accept_therapy_request/create_therapy_request/
	accept_direct_therapy_request - builds and submits the Sales Invoice
	covering one or more therapy plan line items.

	items: list of {"therapy_type": <Therapy Type name>, "no_of_sessions": <int>}.
	One Sales Invoice Item is created per entry, all pointing back at the
	same reference_dt/reference_dn (the Therapy Plan or Patient Encounter
	being invoiced) - this is what lets a template-based plan with several
	therapy types be invoiced in a single Sales Invoice instead of one per
	type. Existing single-type callers just pass a one-item list.
	"""
	customer = patient.customer
	if not customer:
		frappe.throw(_("Patient {0} has no linked Customer").format(patient.name))

	if not items:
		frappe.throw(_("No therapy types to invoice"))

	invoice_items = []
	for entry in items:
		therapy_type = entry.get("therapy_type")
		no_of_sessions = cint(entry.get("no_of_sessions")) or 1

		item_code = frappe.db.get_value("Therapy Type", therapy_type, "item")
		if not item_code:
			frappe.throw(_("Therapy Type {0} has no linked Item").format(therapy_type))
		rate = frappe.db.get_value("Item Price", {"item_code": item_code}, "price_list_rate") or 0

		invoice_items.append(
			{
				"item_code": item_code,
				"qty": no_of_sessions,
				"rate": rate,
				"reference_dt": reference_dt,
				"reference_dn": reference_dn,
			}
		)

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
			"items": invoice_items,
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


# =============================================
# THERAPY SESSIONS - scheduling & delivery
#
# A Therapy Session is created as a draft (docstatus 0) when scheduled -
# this is the "Scheduled" state shown on the portal's Schedule tab/
# calendar, mirroring how a not-yet-submitted document naturally
# represents "hasn't happened yet". Submitting it (docstatus 1) is
# "session delivered": Therapy Session's own on_submit() (see
# therapy_session.py) increments the matching Therapy Plan Detail row's
# sessions_completed and re-saves the Therapy Plan, whose own
# validate()/set_status() recomputes total_sessions_completed and flips
# status Not Started -> In Progress -> Completed automatically - none of
# that bookkeeping is duplicated here, it's the same path the standard
# desk form already uses.
# =============================================


@frappe.whitelist()
def get_active_therapy_plans(search_patient=None):
	"""Paid Therapy Plans that still have therapy left to deliver - the
	pool a therapist schedules/logs sessions against. Excludes Completed
	plans and unpaid ones (custom_invoice not set) - therapy can't proceed
	before payment, same gate the "Awaiting Payment" state on Pending
	cards already encodes."""
	filters = {
		"status": ["in", ["Not Started", "In Progress"]],
		"custom_invoice": ["is", "set"],
	}
	or_filters = None
	if search_patient:
		or_filters = {
			"patient": ["like", f"%{search_patient}%"],
			"patient_name": ["like", f"%{search_patient}%"],
		}

	plans = frappe.get_all(
		"Therapy Plan",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "patient", "patient_name", "practitioner", "total_sessions", "total_sessions_completed"],
		order_by="modified desc",
	)
	for plan in plans:
		plan["therapy_types"] = frappe.get_all(
			"Therapy Plan Detail",
			filters={"parent": plan.name, "parenttype": "Therapy Plan"},
			fields=["therapy_type", "no_of_sessions", "sessions_completed"],
		)
	return plans


@frappe.whitelist()
def schedule_therapy_session(therapy_plan, therapy_type, start_date, start_time, practitioner=None, location=None):
	"""Book a future Therapy Session against an already-paid Therapy Plan.
	Left as a draft - it only becomes a delivered session, and only then
	rolls into the Plan's counts, once complete_therapy_session() submits
	it. Therapy Session's own validate_duplicate() already rejects a slot
	overlapping another session for the same patient or practitioner, so
	no separate conflict check is needed here."""
	if not (therapy_plan and therapy_type and start_date and start_time):
		frappe.throw(_("Please fill in all required fields"))

	plan = frappe.get_doc("Therapy Plan", therapy_plan)
	if not plan.custom_invoice:
		frappe.throw(_("Therapy Plan {0} has not been paid for yet").format(therapy_plan))

	therapy_type_doc = frappe.get_cached_doc("Therapy Type", therapy_type)

	session = frappe.get_doc(
		{
			"doctype": "Therapy Session",
			"patient": plan.patient,
			"therapy_plan": therapy_plan,
			"therapy_type": therapy_type,
			"practitioner": practitioner or plan.practitioner,
			"company": plan.company,
			"start_date": start_date,
			"start_time": start_time,
			"duration": therapy_type_doc.default_duration or 30,
			"rate": therapy_type_doc.rate or 0,
			"location": location or None,
		}
	)
	session.insert(ignore_permissions=True)

	return {"status": "Success", "name": session.name}


@frappe.whitelist()
def schedule_multiple_therapy_sessions(sessions):
	"""Bulk version of schedule_therapy_session() - lets the "New Therapy
	Request" dialog set up every session slot a request needs (one per
	therapy type per no_of_sessions) in a single call, instead of a round
	trip per session.

	sessions: JSON string / list of entries shaped like
	  schedule_therapy_session()'s own arguments:
	  {"therapy_plan", "therapy_type", "start_date", "start_time",
	   "practitioner" (optional), "location" (optional)}.

	Each entry is scheduled via schedule_therapy_session() itself, so the
	same paid-plan check and Therapy Session validate_duplicate() slot-
	conflict guard apply per row. All rows are inserted within this one
	request, so if any entry fails, Frappe rolls back the whole request -
	this never leaves a request with only some of its sessions scheduled.
	"""
	if isinstance(sessions, str):
		sessions = json.loads(sessions)
	if not sessions:
		frappe.throw(_("No sessions to schedule"))

	created = []
	for entry in sessions:
		result = schedule_therapy_session(
			therapy_plan=entry.get("therapy_plan"),
			therapy_type=entry.get("therapy_type"),
			start_date=entry.get("start_date"),
			start_time=entry.get("start_time"),
			practitioner=entry.get("practitioner"),
			location=entry.get("location"),
		)
		created.append(result["name"])

	return {"status": "Success", "names": created}


@frappe.whitelist()
def get_scheduled_sessions(from_date=None, to_date=None, date=None, practitioner=None):
	"""Therapy Sessions in a date range, for the Schedule tab's list and
	calendar views - mirrors spa_portal.py's get_spa_bookings() calling
	shapes (single `date` for the list view, `from_date`/`to_date` for the
	calendar's visible month). Cancelled sessions (docstatus 2) are left
	out - see cancel_therapy_session()."""
	filters = {"docstatus": ["!=", 2]}
	if date:
		filters["start_date"] = date
	elif from_date and to_date:
		filters["start_date"] = ["between", [from_date, to_date]]
	if practitioner:
		filters["practitioner"] = practitioner

	sessions = frappe.get_all(
		"Therapy Session",
		filters=filters,
		fields=[
			"name",
			"patient",
			"patient_name",
			"therapy_type",
			"therapy_plan",
			"practitioner",
			"start_date",
			"start_time",
			"duration",
			"docstatus",
		],
		order_by="start_date asc, start_time asc",
	)
	for s in sessions:
		s["status"] = "Completed" if s.docstatus == 1 else "Scheduled"
	return sessions


@frappe.whitelist()
def get_therapy_session_exercises(therapy_session):
	"""Exercise rows on a still-draft (scheduled) session, pre-populated
	from the Therapy Type's exercise list by Therapy Session's own
	validate() at insert time - fetched here so the 'Complete Session'
	dialog can show the planned exercises with editable Counts Completed /
	Assistance Level fields."""
	session = frappe.get_doc("Therapy Session", therapy_session)
	return {
		"patient_name": session.patient_name,
		"therapy_type": session.therapy_type,
		"start_date": session.start_date,
		"start_time": session.start_time,
		"docstatus": session.docstatus,
		"exercises": [
			{
				"exercise_type": row.exercise_type,
				"difficulty_level": row.difficulty_level,
				"counts_target": row.counts_target,
				"counts_completed": row.counts_completed,
				"assistance_level": row.assistance_level,
			}
			for row in session.exercises
		],
	}


@frappe.whitelist()
def complete_therapy_session(therapy_session, exercises=None, notes=None):
	"""Submit a scheduled (draft) Therapy Session with the actual counts
	completed - this is what rolls the delivered session into the Therapy
	Plan's session counts and status (see this section's module note
	above). exercises, if given, replaces the session's exercise rows with
	the therapist's logged results; if omitted, the exercises already on
	the draft (the Therapy Type's defaults) are submitted as-is."""
	if isinstance(exercises, str):
		exercises = json.loads(exercises)

	session = frappe.get_doc("Therapy Session", therapy_session)
	if session.docstatus != 0:
		frappe.throw(_("Therapy Session {0} has already been submitted or cancelled").format(therapy_session))

	if exercises:
		session.set("exercises", [])
		for ex in exercises:
			session.append(
				"exercises",
				{
					"exercise_type": ex.get("exercise_type"),
					"counts_target": cint(ex.get("counts_target")) or 0,
					"counts_completed": cint(ex.get("counts_completed")) or 0,
					"assistance_level": ex.get("assistance_level") or None,
				},
			)

	session.save(ignore_permissions=True)
	session.submit()

	if notes:
		session.add_comment("Comment", notes)

	plan_status = frappe.db.get_value("Therapy Plan", session.therapy_plan, "status")

	return {
		"status": "Success",
		"name": session.name,
		"therapy_plan": session.therapy_plan,
		"therapy_plan_status": plan_status,
	}


@frappe.whitelist()
def cancel_therapy_session(therapy_session):
	"""Cancel a scheduled or delivered session. A still-draft (scheduled,
	not yet delivered) session is simply deleted - Frappe's submit
	workflow only recognises cancellation (docstatus 2) for submitted
	documents, and a draft never rolled into the Plan's session counts in
	the first place, so there's nothing to unwind. A submitted session is
	cancelled properly instead, letting Therapy Session's own on_cancel()
	decrement the Plan's session count exactly as it would from the
	standard desk form."""
	session = frappe.get_doc("Therapy Session", therapy_session)
	if session.docstatus == 0:
		frappe.delete_doc("Therapy Session", therapy_session, ignore_permissions=True)
	elif session.docstatus == 1:
		session.cancel()
	else:
		frappe.throw(_("Therapy Session {0} is already cancelled").format(therapy_session))
	return {"status": "Success"}


@frappe.whitelist()
def get_rehab_summary():
	"""Aggregate counts for the Rehab Portal's stat tiles - mirrors Spa
	Portal's Total/Paid/Unpaid summary strip, adapted to rehab's own
	Requested -> Pending -> Completed queue plus today's session load.
	Reuses get_requested_therapies()/get_pending_therapies() rather than
	re-deriving the same encounter-sourced/direct-sourced merge logic in
	raw SQL a second time, trading a little extra query overhead for one
	less place that logic can drift out of sync."""
	requested = get_requested_therapies()
	pending = get_pending_therapies()
	pending_unpaid = sum(1 for row in pending if row.get("payment_status") != "Paid")

	today_str = today()
	sessions_scheduled_today = frappe.db.count("Therapy Session", filters={"start_date": today_str, "docstatus": 0})
	sessions_completed_today = frappe.db.count("Therapy Session", filters={"start_date": today_str, "docstatus": 1})

	return {
		"requested": len(requested),
		"pending": len(pending),
		"pending_unpaid": pending_unpaid,
		"sessions_scheduled_today": sessions_scheduled_today,
		"sessions_completed_today": sessions_completed_today,
	}


# =============================================
# OUTCOME TRACKING - Patient Assessments
#
# Patient Assessment is a standard Frappe Healthcare doctype (pain scale,
# range-of-motion sheets, etc. are just differently-configured Patient
# Assessment Templates) - nothing new is added to the schema here, this
# just exposes create/list endpoints for it from the portal so a
# therapist doesn't have to leave for the desk form to record one.
# =============================================


@frappe.whitelist()
def get_assessment_templates():
	"""Patient Assessment Templates (e.g. a pain scale or a range-of-motion
	sheet) for the 'Record Assessment' dialog, each with its parameter list
	and scale so the frontend can render one score input per parameter."""
	templates = frappe.get_all(
		"Patient Assessment Template",
		fields=["name", "scale_min", "scale_max"],
		order_by="name asc",
	)
	for t in templates:
		t["parameters"] = frappe.get_all(
			"Patient Assessment Detail",
			filters={"parent": t.name, "parenttype": "Patient Assessment Template"},
			fields=["assessment_parameter"],
			pluck="assessment_parameter",
		)
	return templates


@frappe.whitelist()
def create_patient_assessment(patient, assessment_template, scores, therapy_session=None, assessment_datetime=None):
	"""Record an outcome assessment (pain scale, range of motion, etc.)
	against a patient - optionally tied to a specific Therapy Session, or
	standalone against the patient's care in general.

	scores: JSON string / list of
	  {"parameter": <Patient Assessment Parameter name>, "score": <int>}.

	total_score is approximated as scale_max * number of parameters scored
	(Patient Assessment's own controller only computes total_score_obtained
	server-side - total_score is otherwise set by the desk form's client
	script, which this whitelisted call bypasses)."""
	if isinstance(scores, str):
		scores = json.loads(scores)
	if not patient:
		frappe.throw(_("Please select a patient"))
	if not assessment_template:
		frappe.throw(_("Please select an assessment template"))
	if not scores:
		frappe.throw(_("Please score at least one parameter"))

	template = frappe.get_doc("Patient Assessment Template", assessment_template)

	assessment = frappe.get_doc(
		{
			"doctype": "Patient Assessment",
			"patient": patient,
			"therapy_session": therapy_session or None,
			"assessment_template": assessment_template,
			"assessment_datetime": assessment_datetime or now_datetime(),
			"scale_min": template.scale_min,
			"scale_max": template.scale_max,
			"total_score": (template.scale_max or 0) * len(scores),
			"assessment_sheet": [
				{"parameter": s.get("parameter"), "score": cint(s.get("score"))} for s in scores
			],
		}
	)
	assessment.insert(ignore_permissions=True)
	assessment.submit()

	return {"status": "Success", "name": assessment.name, "total_score_obtained": assessment.total_score_obtained}


@frappe.whitelist()
def get_patient_assessments(patient):
	"""Assessment history for a patient - used for the outcome trend view
	opened from a Pending/Completed plan card."""
	return frappe.get_all(
		"Patient Assessment",
		filters={"patient": patient, "docstatus": 1},
		fields=["name", "assessment_template", "assessment_datetime", "total_score_obtained", "total_score"],
		order_by="assessment_datetime desc",
	)
