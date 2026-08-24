# Copyright (c) 2026, Ransbort and contributors
# For license information, please see license.txt
"""
Backend for the Lab Portal page (page/lab_portal/lab_portal.js).

Two request sources feed each tab:
  1. Encounter-sourced: Patient Encounter -> Lab Prescription -> sits in
     Requested Labs until a lab scientist accepts it into a Lab Test +
     Sales Invoice via accept_lab_request().
  2. Direct-sourced: a standalone Lab Test with no Patient Encounter,
     created via create_lab_request() by a lab scientist or a front-desk
     receptionist (Laboratory User / Healthcare Receptionist - see this
     page's roles in lab_portal.json) for a walk-in who wants a lab test
     without seeing a doctor first and isn't going through Front Desk's
     own check-in/appointment flow at all. Since creating it IS the
     acceptance, it's invoiced immediately on creation and goes straight
     to Pending Labs, skipping Requested Labs entirely. Identified by
     Lab Test.prescription IS NULL. Healthcare Receptionist's access to
     this action specifically (not Laboratory User's, which is always
     on) can be switched off via Healthcare Settings.
     front_desk_lab_requests_enabled - see _is_front_desk_only()/
     _front_desk_lab_requests_enabled()/get_front_desk_lab_request_access()
     below.

Both are queried separately (different columns) then normalized to a common
row shape with a `source` field ("encounter" | "direct") so the frontend
knows which accept endpoint to call.

Schema notes:
- `Patient Encounter.diagnosis` is a Table MultiSelect (child doctype
  `Patient Encounter Diagnosis`), not a plain column - pulled via a
  correlated GROUP_CONCAT subquery (_DIAGNOSIS_SUBQUERY).
- `Lab Prescription` has custom fields `custom_priority` and
  `custom_lab_test` (set once accepted).
- `Lab Test` has no built-in Sales Invoice link - `custom_invoice` is a
  custom field added for this portal.
- `Lab Test.patient_sex`/`patient_name` are mandatory but fetch_from doesn't
  reliably fire on server-side inserts, so both accept functions set them
  explicitly from the Patient record.
- Payment status is read off the linked Sales Invoice's `status` field.
"""
import frappe
from frappe import _
from frappe.utils import today


def _notify(event, payload):
	"""Broadcast a realtime event to everyone listening in this site."""
	frappe.publish_realtime(event=event, message=payload)


def notify_new_lab_requests(doc, method=None):
	"""Hooked on Patient Encounter on_update. Fires on every save (not just
	submit, since docstatus can stay 0 in walk-in workflows) and diffs
	against the pre-save state to avoid re-notifying on unrelated saves.
	"""
	before_save = doc.get_doc_before_save()
	old_names = set()
	if before_save:
		old_names = {row.name for row in before_save.get("lab_test_prescription", [])}

	new_pending = [
		row for row in doc.get("lab_test_prescription", [])
		if not row.invoiced and row.name not in old_names
	]

	if not new_pending:
		return

	_notify("queue_update", {
		"department": "laboratory",
		"message": f"New lab request(s) for {doc.patient_name} ({len(new_pending)})",
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


def _lab_search_conditions(search_patient, search_encounter, search_date, date_field="pe.encounter_date"):
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


def _direct_search_conditions(search_patient, search_encounter, search_date, date_field="lt.creation"):
	"""Same shape as _lab_search_conditions but against Lab Test directly.
	search_encounter is ignored - direct requests have no encounter.
	"""
	conditions = []
	values = {}
	if search_patient:
		conditions.append("(lt.patient LIKE %(search_patient)s OR lt.patient_name LIKE %(search_patient)s)")
		values["search_patient"] = f"%{search_patient}%"
	if search_date:
		conditions.append(f"DATE({date_field}) = %(search_date)s")
		values["search_date"] = search_date
	return conditions, values


def _normalize_direct_row(row):
	"""Reshape a direct Lab Test row into the same keys as encounter-sourced
	rows so lab_portal.js can render both with one code path.

	Uses .get() instead of [] since the three callers' SQL SELECTs have
	drifted out of sync before (a missing column raised KeyError here).
	"""
	return {
		"prescription_id": None,
		"lab_test_name_id": row.get("lab_test_name_id"),  # the Lab Test's own name - used to accept/view it
		"lab_test_code": row.get("lab_test_code"),
		"lab_test_comment": row.get("lab_test_comment"),
		"lab_test_name": row.get("lab_test_name"),
		"priority": None,
		"custom_lab_test": row.get("custom_lab_test"),
		"encounter_id": None,
		"patient": row.get("patient"),
		"patient_name": row.get("patient_name"),
		"encounter_date": row.get("encounter_date"),
		"practitioner": None,
		"diagnosis": None,
		"source": "direct",
	}


@frappe.whitelist()
def get_lab_test_templates():
	"""Active Lab Test Templates for the 'New Lab Request' picker."""
	templates = frappe.get_all(
		"Lab Test Template",
		filters={"disabled": 0},
		fields=["name", "lab_test_name", "department", "item"],
		order_by="lab_test_name asc",
	)
	for t in templates:
		t["rate"] = frappe.db.get_value("Item Price", {"item_code": t.item}, "price_list_rate") or 0
	return templates


def _is_front_desk_only(user=None):
	"""True when the user's only reason to be in Lab Portal at all is
	Healthcare Receptionist - i.e. they aren't also Laboratory User or
	System Manager, who can always create direct lab requests regardless
	of front_desk_lab_requests_enabled.
	"""
	roles = set(frappe.get_roles(user))
	if "Laboratory User" in roles or "System Manager" in roles:
		return False
	return "Healthcare Receptionist" in roles


def _front_desk_lab_requests_enabled():
	"""Healthcare Settings > Lab Portal - Front Desk Access >
	Front Desk Can Create Direct Lab Requests (see setup.py). Only
	consulted for front-desk-only users - see _is_front_desk_only().
	"""
	return bool(frappe.db.get_single_value("Healthcare Settings", "front_desk_lab_requests_enabled"))


@frappe.whitelist()
def get_front_desk_lab_request_access():
	"""Whitelisted so lab_portal.js can decide up front whether to show
	the current user the 'New Request' action at all, instead of letting
	them fill out the dialog and only then hitting create_lab_request()'s
	PermissionError.
	"""
	if not _is_front_desk_only():
		return True
	return _front_desk_lab_requests_enabled()


@frappe.whitelist()
def create_lab_request(patient, lab_test_code, lab_test_comment=None):
	"""Create a Lab Test requested directly by a lab scientist or a
	front-desk receptionist (page-level access: Laboratory User,
	Healthcare Receptionist, System Manager - see lab_portal.json), with
	no Patient Encounter involved. Unlike encounter-sourced requests
	(which sit in Requested Labs until a lab scientist accepts them), a
	direct request IS its own acceptance - so it's invoiced immediately
	here and goes straight to Pending Labs (awaiting payment) rather than
	through Requested Labs.

	Healthcare Receptionist's access to this specific action is gated by
	Healthcare Settings.front_desk_lab_requests_enabled (default on) -
	see _is_front_desk_only()/_front_desk_lab_requests_enabled() above.
	Laboratory User and System Manager are never affected by that
	setting.
	"""
	if not patient:
		frappe.throw(_("Please select a patient"))
	if not lab_test_code:
		frappe.throw(_("Please select a lab test"))
	if _is_front_desk_only() and not _front_desk_lab_requests_enabled():
		frappe.throw(
			_(
				"Front Desk is not currently permitted to create direct lab "
				"requests. Ask a Laboratory User, or enable this under "
				"Healthcare Settings > Lab Portal - Front Desk Access."
			),
			frappe.PermissionError,
		)

	patient_doc = frappe.get_doc("Patient", patient)

	lab_test = frappe.get_doc(
		{
			"doctype": "Lab Test",
			"patient": patient,
			"patient_name": patient_doc.patient_name,
			"patient_sex": patient_doc.sex,
			"template": lab_test_code,
			"lab_test_comment": lab_test_comment,
			"status": "Draft",
		}
	)
	lab_test.insert(ignore_permissions=True)

	invoice = _create_lab_invoice(
		patient_doc, lab_test_code, reference_dt="Lab Test", reference_dn=lab_test.name
	)
	lab_test.db_set("custom_invoice", invoice.name)

	_notify("queue_update", {
		"department": "laboratory",
		"message": f"New direct lab request for {patient_doc.patient_name}",
		"lab_test": lab_test.name,
	})

	return {"status": "Success", "lab_test_name": lab_test.name, "invoice_name": invoice.name}


@frappe.whitelist()
def get_requested_labs(search_patient=None, search_encounter=None, search_date=None):
	"""Lab tests requested but not yet accepted/invoiced - merges
	encounter-sourced (Lab Prescription) and direct-sourced (standalone
	Lab Test) requests."""
	conditions, values = _lab_search_conditions(search_patient, search_encounter, search_date)
	conditions.insert(0, "lp.invoiced = 0")
	where_clause = " AND ".join(conditions)
	encounter_rows = frappe.db.sql(
		f"""
		SELECT
			lp.name AS prescription_id,
			NULL AS lab_test_name_id,
			lp.lab_test_code AS lab_test_code,
			lp.lab_test_comment AS lab_test_comment,
			COALESCE(ltt.lab_test_name, lp.lab_test_code) AS lab_test_name,
			lp.custom_priority AS priority,
			pe.name AS encounter_id,
			pe.patient AS patient,
			pe.patient_name AS patient_name,
			pe.encounter_date AS encounter_date,
			pe.practitioner AS practitioner,
			{_DIAGNOSIS_SUBQUERY},
			'encounter' AS source
		FROM `tabLab Prescription` lp
		INNER JOIN `tabPatient Encounter` pe ON pe.name = lp.parent
		LEFT JOIN `tabLab Test Template` ltt ON ltt.name = lp.lab_test_code
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
	d_conditions[0:0] = ["lt.prescription IS NULL", "lt.custom_invoice IS NULL", "lt.status = 'Draft'"]
	d_where = " AND ".join(d_conditions)
	direct_rows = frappe.db.sql(
		f"""
		SELECT
			lt.name AS lab_test_name_id,
			lt.template AS lab_test_code,
			lt.lab_test_comment AS lab_test_comment,
			COALESCE(ltt.lab_test_name, lt.template) AS lab_test_name,
			NULL AS custom_lab_test,
			lt.patient AS patient,
			lt.patient_name AS patient_name,
			lt.creation AS encounter_date
		FROM `tabLab Test` lt
		LEFT JOIN `tabLab Test Template` ltt ON ltt.name = lt.template
		WHERE {d_where}
		ORDER BY lt.creation DESC
		""",
		d_values,
		as_dict=True,
	)

	return encounter_rows + [_normalize_direct_row(r) for r in direct_rows]


@frappe.whitelist()
def get_pending_labs(search_patient=None, search_encounter=None, search_date=None):
	"""Accepted (invoiced) lab tests that haven't been marked Completed yet -
	merges encounter-sourced and direct-sourced requests."""
	conditions, values = _lab_search_conditions(search_patient, search_encounter, search_date)
	conditions[0:0] = [
		"lp.invoiced = 1",
		"lp.custom_lab_test IS NOT NULL",
		"lt.status != 'Completed'",
	]
	where_clause = " AND ".join(conditions)
	encounter_rows = frappe.db.sql(
		f"""
		SELECT
			lp.name AS prescription_id,
			NULL AS lab_test_name_id,
			lp.lab_test_code AS lab_test_code,
			lp.lab_test_comment AS lab_test_comment,
			COALESCE(ltt.lab_test_name, lp.lab_test_code) AS lab_test_name,
			lp.custom_priority AS priority,
			lp.custom_lab_test AS custom_lab_test,
			pe.name AS encounter_id,
			pe.patient AS patient,
			pe.patient_name AS patient_name,
			pe.encounter_date AS encounter_date,
			pe.practitioner AS practitioner,
			{_DIAGNOSIS_SUBQUERY},
			si.status AS invoice_status,
			'encounter' AS source
		FROM `tabLab Prescription` lp
		INNER JOIN `tabPatient Encounter` pe ON pe.name = lp.parent
		INNER JOIN `tabLab Test` lt ON lt.name = lp.custom_lab_test
		LEFT JOIN `tabLab Test Template` ltt ON ltt.name = lp.lab_test_code
		LEFT JOIN `tabSales Invoice` si ON si.name = lt.custom_invoice
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
	d_conditions[0:0] = ["lt.prescription IS NULL", "lt.custom_invoice IS NOT NULL", "lt.status != 'Completed'"]
	d_where = " AND ".join(d_conditions)
	direct_rows = frappe.db.sql(
		f"""
		SELECT
			lt.name AS lab_test_name_id,
			lt.template AS lab_test_code,
			lt.lab_test_comment AS lab_test_comment,
			COALESCE(ltt.lab_test_name, lt.template) AS lab_test_name,
			lt.name AS custom_lab_test,
			lt.patient AS patient,
			lt.patient_name AS patient_name,
			lt.creation AS encounter_date,
			si.status AS invoice_status
		FROM `tabLab Test` lt
		LEFT JOIN `tabLab Test Template` ltt ON ltt.name = lt.template
		LEFT JOIN `tabSales Invoice` si ON si.name = lt.custom_invoice
		WHERE {d_where}
		ORDER BY lt.creation DESC
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
def get_completed_labs(search_patient=None, search_encounter=None, filter_date=None):
	"""Lab tests with results entered (status Completed) - merges
	encounter-sourced and direct-sourced requests."""
	conditions, values = _lab_search_conditions(
		search_patient, search_encounter, filter_date, date_field="DATE(lt.modified)"
	)
	conditions[0:0] = [
		"lp.invoiced = 1",
		"lp.custom_lab_test IS NOT NULL",
		"lt.status = 'Completed'",
	]
	where_clause = " AND ".join(conditions)
	encounter_rows = frappe.db.sql(
		f"""
		SELECT
			lp.name AS prescription_id,
			NULL AS lab_test_name_id,
			lp.lab_test_code AS lab_test_code,
			COALESCE(ltt.lab_test_name, lp.lab_test_code) AS lab_test_name,
			lp.custom_lab_test AS custom_lab_test,
			pe.name AS encounter_id,
			pe.patient AS patient,
			pe.patient_name AS patient_name,
			pe.encounter_date AS encounter_date,
			pe.practitioner AS practitioner,
			{_DIAGNOSIS_SUBQUERY},
			'encounter' AS source
		FROM `tabLab Prescription` lp
		INNER JOIN `tabPatient Encounter` pe ON pe.name = lp.parent
		INNER JOIN `tabLab Test` lt ON lt.name = lp.custom_lab_test
		LEFT JOIN `tabLab Test Template` ltt ON ltt.name = lp.lab_test_code
		WHERE {where_clause}
		ORDER BY lt.modified DESC
		""",
		values,
		as_dict=True,
	)

	if search_encounter:
		return encounter_rows

	d_conditions, d_values = _direct_search_conditions(
		search_patient, search_encounter, filter_date, date_field="lt.modified"
	)
	d_conditions[0:0] = ["lt.prescription IS NULL", "lt.status = 'Completed'"]
	d_where = " AND ".join(d_conditions)
	direct_rows = frappe.db.sql(
		f"""
		SELECT
			lt.name AS lab_test_name_id,
			lt.template AS lab_test_code,
			lt.lab_test_comment AS lab_test_comment,
			COALESCE(ltt.lab_test_name, lt.template) AS lab_test_name,
			lt.name AS custom_lab_test,
			lt.patient AS patient,
			lt.patient_name AS patient_name,
			lt.modified AS encounter_date
		FROM `tabLab Test` lt
		LEFT JOIN `tabLab Test Template` ltt ON ltt.name = lt.template
		WHERE {d_where}
		ORDER BY lt.modified DESC
		""",
		d_values,
		as_dict=True,
	)

	return encounter_rows + [_normalize_direct_row(r) for r in direct_rows]


@frappe.whitelist()
def accept_lab_request(prescription_id, patient_id, encounter_id, lab_test_code):
	"""Accept an encounter-sourced request: create + submit a Sales Invoice,
	create a draft Lab Test, and stamp the source Lab Prescription row so
	it moves from Requested to Pending on the next reload.
	"""
	encounter = frappe.get_doc("Patient Encounter", encounter_id)
	prescription_row = None
	for row in encounter.lab_test_prescription:
		if row.name == prescription_id:
			prescription_row = row
			break
	if not prescription_row:
		frappe.throw(_("Lab Prescription row {0} not found on encounter {1}").format(prescription_id, encounter_id))

	patient = frappe.get_doc("Patient", patient_id)
	invoice = _create_lab_invoice(patient, lab_test_code, reference_dt="Patient Encounter", reference_dn=encounter_id)

	lab_test = frappe.get_doc(
		{
			"doctype": "Lab Test",
			"patient": patient_id,
			"patient_name": patient.patient_name,
			"patient_sex": patient.sex,
			"template": lab_test_code,
			"prescription": prescription_row.name,
			"custom_invoice": invoice.name,
			"status": "Draft",
		}
	)
	lab_test.insert(ignore_permissions=True)
	prescription_row.db_set("custom_lab_test", lab_test.name)
	prescription_row.db_set("invoiced", 1)

	# notify_new_lab_requests() above only announces the *request* landing
	# in the lab's queue, before any invoice exists - this is the actual
	# invoice-raising moment (accepting the request is what creates it),
	# and nothing told the Cashier Portal about it until now.
	_notify("queue_update", {
		"department": "cashier",
		"message": f"New invoice pending: {invoice.name}",
		"encounter": None,
	})

	return {
		"status": "Success",
		"invoice_name": invoice.name,
		"lab_test_name": lab_test.name,
	}


@frappe.whitelist()
def accept_direct_lab_request(lab_test_name):
	"""Accept a direct-sourced request: invoice the existing draft Lab Test
	and link it via custom_invoice, moving it from Requested to Pending.
	"""
	lab_test = frappe.get_doc("Lab Test", lab_test_name)
	if lab_test.prescription:
		frappe.throw(_("Lab Test {0} is encounter-sourced, use accept_lab_request instead").format(lab_test_name))
	if lab_test.custom_invoice:
		frappe.throw(_("Lab Test {0} is already invoiced").format(lab_test_name))

	patient = frappe.get_doc("Patient", lab_test.patient)
	invoice = _create_lab_invoice(patient, lab_test.template, reference_dt="Lab Test", reference_dn=lab_test.name)

	lab_test.db_set("custom_invoice", invoice.name)

	# See accept_lab_request()'s matching note above - this is a separate
	# fallback accept path (a direct request that somehow ended up
	# uninvoiced) and needs the same Cashier Portal notification.
	_notify("queue_update", {
		"department": "cashier",
		"message": f"New invoice pending: {invoice.name}",
		"encounter": None,
	})

	return {
		"status": "Success",
		"invoice_name": invoice.name,
		"lab_test_name": lab_test.name,
	}


def _create_lab_invoice(patient, lab_test_code, reference_dt, reference_dn):
	"""Shared by both accept functions - builds and submits the Sales
	Invoice for one lab test line."""
	customer = patient.customer
	if not customer:
		frappe.throw(_("Patient {0} has no linked Customer").format(patient.name))

	item_code = frappe.db.get_value("Lab Test Template", lab_test_code, "item")
	if not item_code:
		frappe.throw(_("Lab Test Template {0} has no linked Item").format(lab_test_code))
	rate = frappe.db.get_value("Item Price", {"item_code": item_code}, "price_list_rate") or 0

	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": customer,
			"patient": patient.name,
			"posting_date": today(),
			# Needed so cashier_portal.py buckets this under Laboratory
			# instead of "Other Invoices".
			"custom_department": "Laboratory",
			"items": [
				{
					"item_code": item_code,
					"qty": 1,
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