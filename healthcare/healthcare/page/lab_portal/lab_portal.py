# Copyright (c) 2026, Ransbort and contributors
# For license information, please see license.txt
"""
Backend for the Lab Portal page (page/lab_portal/lab_portal.js).
Schema notes confirmed against the real site (see console checks in chat):
- `Patient Encounter.diagnosis` is a Table MultiSelect field backed by the
  child doctype `Patient Encounter Diagnosis`, NOT a plain column - it can't
  be selected directly as `pe.diagnosis` in raw SQL. Pulled via a correlated
  GROUP_CONCAT subquery instead (see _diagnosis_subquery below).
- `Patient Encounter Diagnosis.diagnosis` is a Link to the `Diagnosis`
  doctype, and Diagnosis records are named by their diagnosis text itself,
  so the linked value doubles as display text - no extra join needed.
Everything else here was already verified working:
- `Patient Encounter` has a child table `lab_test_prescription`
  (child doctype `Lab Prescription`) with fields: lab_test_code,
  lab_test_comment, invoiced (Check).
- `Lab Prescription` has a CUSTOM field `custom_priority` (Select: High/
  Medium/Low) and a CUSTOM field `custom_lab_test` (Link -> Lab Test) that
  gets set once accept_lab_request() creates the Lab Test doc.
- `Lab Test Template` has an `item` field linking to a stock/service Item
  (standard in ERPNext Healthcare).
- `Lab Test` has fields: patient, template, prescription (Link -> Lab
  Prescription, not Patient Encounter), status, invoiced (Check). It has NO
  built-in Sales Invoice link - `custom_invoice` (Link -> Sales Invoice) is
  a CUSTOM field added specifically for this portal (see setup.py).
- `Lab Test.patient_sex` (and patient_name) are MANDATORY fields on the
  doctype, presumably meant to auto-populate via fetch_from when set through
  the desk UI. That fetch does NOT reliably fire when a doc is constructed
  and inserted directly server-side (frappe.get_doc({...}).insert()) - so
  accept_lab_request() below fetches these from the Patient record itself
  and sets them explicitly, rather than relying on fetch_from.
- Payment status is read off the linked Sales Invoice's `status` field via
  Lab Test.custom_invoice.
"""
import frappe
from frappe import _
from frappe.utils import today

def _notify(event, payload):
	"""Broadcast a realtime event to everyone listening in this site."""
	frappe.publish_realtime(event=event, message=payload)


def notify_new_lab_requests(doc, method=None):
	"""Hooked on Patient Encounter on_update. Encounters aren't always
	submitted (docstatus can stay 0 indefinitely in walk-in workflows),
	so this can't rely on on_submit - it has to fire on every save and
	diff against the pre-save state itself to avoid re-notifying on
	unrelated re-saves of the same encounter.
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

# Correlated subquery: aggregates every diagnosis linked to an encounter
# into one comma-separated string. `pe` must already be joined/aliased in
# the outer query for the `pe.name` reference here to resolve.
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
	
@frappe.whitelist()
def get_requested_labs(search_patient=None, search_encounter=None, search_date=None):
	"""Lab tests prescribed on an encounter but not yet accepted/invoiced."""
	conditions, values = _lab_search_conditions(search_patient, search_encounter, search_date)
	conditions.insert(0, "lp.invoiced = 0")
	where_clause = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			lp.name AS prescription_id,
			lp.lab_test_code AS lab_test_code,
			lp.lab_test_comment AS lab_test_comment,
			COALESCE(ltt.lab_test_name, lp.lab_test_code) AS lab_test_name,
			lp.custom_priority AS priority,
			pe.name AS encounter_id,
			pe.patient AS patient,
			pe.patient_name AS patient_name,
			pe.encounter_date AS encounter_date,
			pe.practitioner AS practitioner,
			{_DIAGNOSIS_SUBQUERY}
		FROM `tabLab Prescription` lp
		INNER JOIN `tabPatient Encounter` pe ON pe.name = lp.parent
		LEFT JOIN `tabLab Test Template` ltt ON ltt.name = lp.lab_test_code
		WHERE {where_clause}
		ORDER BY pe.encounter_date DESC
		""",
		values,
		as_dict=True,
	)
	
@frappe.whitelist()
def get_pending_labs(search_patient=None, search_encounter=None, search_date=None):
	"""Accepted (invoiced) lab tests that haven't been marked Completed yet."""
	conditions, values = _lab_search_conditions(search_patient, search_encounter, search_date)
	conditions[0:0] = [
		"lp.invoiced = 1",
		"lp.custom_lab_test IS NOT NULL",
		"lt.status != 'Completed'",
	]
	where_clause = " AND ".join(conditions)
	rows = frappe.db.sql(
		f"""
		SELECT
			lp.name AS prescription_id,
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
			si.status AS invoice_status
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
	for row in rows:
		row["payment_status"] = "Paid" if row.pop("invoice_status", None) == "Paid" else "Unpaid"
	return rows
	
@frappe.whitelist()
def get_completed_labs(search_patient=None, search_encounter=None, filter_date=None):
	"""Lab tests with results entered (status Completed)."""
	conditions, values = _lab_search_conditions(
		search_patient, search_encounter, filter_date, date_field="DATE(lt.modified)"
	)
	conditions[0:0] = [
		"lp.invoiced = 1",
		"lp.custom_lab_test IS NOT NULL",
		"lt.status = 'Completed'",
	]
	where_clause = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			lp.name AS prescription_id,
			lp.lab_test_code AS lab_test_code,
			COALESCE(ltt.lab_test_name, lp.lab_test_code) AS lab_test_name,
			lp.custom_lab_test AS custom_lab_test,
			pe.name AS encounter_id,
			pe.patient AS patient,
			pe.patient_name AS patient_name,
			pe.encounter_date AS encounter_date,
			pe.practitioner AS practitioner,
			{_DIAGNOSIS_SUBQUERY}
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
	
@frappe.whitelist()
def accept_lab_request(prescription_id, patient_id, encounter_id, lab_test_code):
	"""
	Accept a requested lab test: create + submit a Sales Invoice, create a
	draft Lab Test, then stamp the originating Lab Prescription row so it
	shows up under Pending instead of Requested on the next reload.
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
	customer = patient.customer
	if not customer:
		frappe.throw(_("Patient {0} has no linked Customer").format(patient_id))

	item_code = frappe.db.get_value("Lab Test Template", lab_test_code, "item")
	if not item_code:
		frappe.throw(_("Lab Test Template {0} has no linked Item").format(lab_test_code))
	rate = frappe.db.get_value("Item Price", {"item_code": item_code}, "price_list_rate") or 0
	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": customer,
			"patient": patient_id,
			"posting_date": today(),
			# Without this, cashier_portal.py's _get_department_invoices()
			# has no way to bucket this invoice under Laboratory - it would
			# fall into "Other Invoices" instead (same issue fixed for
			# Pharmacy Sales Orders and Rehabilitation invoices).
			"custom_department": "Laboratory",
			"items": [
				{
					"item_code": item_code,
					"qty": 1,
					"rate": rate,
					"reference_dt": "Patient Encounter",
					"reference_dn": encounter_id,
				}
			],
		}
	)
	invoice.insert(ignore_permissions=True)
	invoice.submit()

	lab_test = frappe.get_doc(
		{
			"doctype": "Lab Test",
			"patient": patient_id,
			# patient_name/patient_sex are mandatory on Lab Test and don't
			# reliably auto-populate via fetch_from when the doc is built
			# and inserted directly here (as opposed to through the desk
			# UI) - fetch them from the Patient doc explicitly instead of
			# relying on Frappe to backfill them.
			"patient_name": patient.patient_name,
			"patient_sex": patient.sex,
			"template": lab_test_code,
			# `prescription` is a Link to Lab Prescription, NOT Patient
			# Encounter - encounter_id was being written here before,
			# silently pointing at the wrong doctype's records.
			"prescription": prescription_row.name,
			# Lab Test has no "invoice" field - only the boolean `invoiced`
			# Check. custom_invoice (added in setup.py) is what actually
			# links back to the Sales Invoice.
			"custom_invoice": invoice.name,
			"status": "Draft",
		}
	)
	lab_test.insert(ignore_permissions=True)
	prescription_row.db_set("custom_lab_test", lab_test.name)
	prescription_row.db_set("invoiced", 1)
	return {
		"status": "Success",
		"invoice_name": invoice.name,
		"lab_test_name": lab_test.name,
	}
	
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
