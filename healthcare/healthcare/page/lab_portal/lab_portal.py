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


def _lab_search_conditions(
	search_patient, search_encounter, search_date, search_to_date=None, date_field="pe.encounter_date"
):
	conditions = []
	values = {}
	if search_patient:
		conditions.append("(pe.patient LIKE %(search_patient)s OR pe.patient_name LIKE %(search_patient)s)")
		values["search_patient"] = f"%{search_patient}%"
	if search_encounter:
		conditions.append("pe.name = %(search_encounter)s")
		values["search_encounter"] = search_encounter
	if search_date and search_to_date:
		conditions.append(f"{date_field} BETWEEN %(search_date)s AND %(search_to_date)s")
		values["search_date"] = search_date
		values["search_to_date"] = search_to_date
	elif search_date:
		conditions.append(f"{date_field} = %(search_date)s")
		values["search_date"] = search_date
	return conditions, values


def _direct_search_conditions(
	search_patient, search_encounter, search_date, search_to_date=None, date_field="lt.creation"
):
	"""Same shape as _lab_search_conditions but against Lab Test directly.
	search_encounter is ignored - direct requests have no encounter.
	"""
	conditions = []
	values = {}
	if search_patient:
		conditions.append("(lt.patient LIKE %(search_patient)s OR lt.patient_name LIKE %(search_patient)s)")
		values["search_patient"] = f"%{search_patient}%"
	if search_date and search_to_date:
		conditions.append(f"DATE({date_field}) BETWEEN %(search_date)s AND %(search_to_date)s")
		values["search_date"] = search_date
		values["search_to_date"] = search_to_date
	elif search_date:
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


def _resolve_practitioner_names(rows):
	"""Encounter-sourced rows only ever carry `practitioner` as the raw
	Healthcare Practitioner Link value (e.g. "HLC-PRAC-2026-00003") - none
	of the SQL above joins across to the practitioner's own display name
	(direct-sourced Lab Test rows have no practitioner at all - see
	_normalize_direct_row). Bulk-resolve it here and stamp a
	`practitioner_name` key onto each row, same shape/relationship
	front_desk.py's _resolve_patient_full_names() has to `patient`/
	`patient_name` (and rehab_portal.py's own copy of this same helper).
	Mutates rows in place; falls back to leaving practitioner_name unset
	(the front-end falls back to the raw ID) if a practitioner was deleted
	or renamed out from under a stale row.
	"""
	practitioner_ids = list({row["practitioner"] for row in rows if row.get("practitioner")})
	if not practitioner_ids:
		return

	practitioners = frappe.get_all(
		"Healthcare Practitioner",
		filters={"name": ["in", practitioner_ids]},
		fields=["name", "practitioner_name"],
	)
	name_map = {p["name"]: p["practitioner_name"] for p in practitioners}

	for row in rows:
		if row.get("practitioner") in name_map:
			row["practitioner_name"] = name_map[row["practitioner"]]


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
		_resolve_practitioner_names(encounter_rows)
		return encounter_rows

	d_conditions, d_values = _direct_search_conditions(search_patient, search_encounter, search_date)
	# ifnull(lt.invoiced, 0) = 0 excludes a free trial panel test
	# (sports_complex's create_trial_lab_panel() marks those invoiced=1
	# directly, with no custom_invoice to link, when the trial's
	# consultation fee was $0/unset - see that function's docstring) -
	# without this it would show here as if still awaiting billing, even
	# though nothing is owed.
	d_conditions[0:0] = [
		"lt.prescription IS NULL",
		"lt.custom_invoice IS NULL",
		"ifnull(lt.invoiced, 0) = 0",
		"lt.status = 'Draft'",
	]
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

	rows = encounter_rows + [_normalize_direct_row(r) for r in direct_rows]
	_resolve_practitioner_names(rows)
	return rows


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
		_resolve_practitioner_names(encounter_rows)
		return encounter_rows

	d_conditions, d_values = _direct_search_conditions(search_patient, search_encounter, search_date)
	# Either a real invoice is linked, or it's a free trial panel test
	# marked invoiced=1 directly with no invoice to link (see
	# sports_complex's create_trial_lab_panel() docstring) - both belong
	# here, nothing left to accept/invoice either way.
	#
	# sc_trial_appointment IS NULL excludes trial panel tests specifically -
	# those have their own dedicated Trial Labs tab now (sports_complex's
	# get_trial_lab_tests()), which covers exactly this same "not yet
	# Completed" state for a trial. Without this they'd show up twice -
	# once here, once there - which is what actually happened before this
	# was added: staff were clicking Pending Labs' "Open Lab Test" (full
	# form navigation) instead of Trial Labs' own, on the very cards this
	# excludes. Deliberately NOT added to get_completed_labs() below -
	# once a trial's appointment leaves "With Lab" (sent to the doctor),
	# get_trial_lab_queue() stops returning it, so a completed trial test
	# needs to stay visible in the general Completed Labs tab or it
	# disappears from Lab Portal entirely.
	d_conditions[0:0] = [
		"lt.prescription IS NULL",
		"(lt.custom_invoice IS NOT NULL OR lt.invoiced = 1)",
		"lt.status != 'Completed'",
		"lt.sc_trial_appointment IS NULL",
	]
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
			lt.custom_invoice AS direct_custom_invoice,
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
		if not r.get("direct_custom_invoice"):
			# Matched the (lt.invoiced = 1) side of the OR above with no
			# custom_invoice to show a real invoice_status for - a free
			# trial panel test, nothing owed rather than owed-and-unpaid.
			row["payment_status"] = "Free"
		else:
			row["payment_status"] = "Paid" if r.get("invoice_status") == "Paid" else "Unpaid"
		normalized_direct.append(row)

	rows = encounter_rows + normalized_direct
	_resolve_practitioner_names(rows)
	return rows


@frappe.whitelist()
def get_completed_labs(search_patient=None, search_encounter=None, filter_date=None, to_date=None):
	"""Lab tests with results entered (status Completed) - merges
	encounter-sourced and direct-sourced requests. `to_date` is optional -
	leaving it blank keeps the single-day filter behavior; filling it in
	switches to a `filter_date`-to-`to_date` range (see _lab_search_
	conditions/_direct_search_conditions)."""
	conditions, values = _lab_search_conditions(
		search_patient, search_encounter, filter_date, to_date, date_field="DATE(lt.modified)"
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
		_resolve_practitioner_names(encounter_rows)
		return encounter_rows

	d_conditions, d_values = _direct_search_conditions(
		search_patient, search_encounter, filter_date, to_date, date_field="lt.modified"
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

	rows = encounter_rows + [_normalize_direct_row(r) for r in direct_rows]
	_resolve_practitioner_names(rows)
	return rows


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

	# Create the Lab Test BEFORE the invoice, and bill against the Lab Test
	# itself (reference_dt="Lab Test") rather than the Lab Prescription row
	# or the encounter as a whole. Two things this avoids:
	#
	# 1. (The original reason "Patient Encounter" was ruled out.) healthcare/
	#    utils.py's set_invoiced()/validate_invoiced_on_submit() stamp the
	#    "invoiced" flag onto whatever (reference_dt, reference_dn) the
	#    invoice item points at. Using "Patient Encounter" flipped the
	#    *encounter's own* invoiced flag (meant for its OP consulting charge,
	#    unrelated to labs) on submit of the FIRST lab test's invoice, which
	#    then made every other lab test requested off the same encounter
	#    fail with "already invoiced" even though only one test had actually
	#    been billed.
	#
	# 2. (Why "Lab Prescription" turned out to be wrong too.) Core Healthcare's
	#    own Sales Invoice on_submit hook (manage_invoice_submit_cancel() ->
	#    create_multiple(), gated on Healthcare Settings' "Create Lab Test on
	#    Sales Invoice Submit") independently scans the invoice's own items
	#    for anything whose Item Code matches a Lab Test Template, and - in
	#    healthcare/healthcare/doctype/lab_test/lab_test.py's
	#    create_lab_test_from_invoice() - only skips creating its OWN Lab
	#    Test when it finds item.reference_dt == "Lab Test" already.
	#    "Lab Prescription" doesn't match that check, so every accepted
	#    request silently got a SECOND, untracked Lab Test made for it (with
	#    invoiced=1 and no custom_invoice, since core doesn't know about this
	#    app's own field) the moment the invoice was submitted - which Lab
	#    Portal then showed as a "Free" duplicate card as soon as the request
	#    moved from Requested into Pending Labs. accept_direct_lab_request()
	#    below already uses "Lab Test" for exactly this reason, and never
	#    produced this duplicate - matching it here closes the gap for
	#    encounter-sourced (doctor-ordered) requests too. (If the "Create Lab
	#    Test on Sales Invoice Submit" setting is off, this branch of core
	#    never runs at all - but this fix holds regardless of that setting.)
	lab_test = frappe.get_doc(
		{
			"doctype": "Lab Test",
			"patient": patient_id,
			"patient_name": patient.patient_name,
			"patient_sex": patient.sex,
			"template": lab_test_code,
			"prescription": prescription_row.name,
			"status": "Draft",
		}
	)
	lab_test.insert(ignore_permissions=True)

	invoice = _create_lab_invoice(
		patient, lab_test_code, reference_dt="Lab Test", reference_dn=lab_test.name
	)
	lab_test.db_set("custom_invoice", invoice.name)

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

	Guards against two different "already handled" states, not just one:
	custom_invoice already set (checked first, as before) and the
	standard core `invoiced` flag already set with no custom_invoice to
	show for it - e.g. a free trial panel test (sports_complex's
	create_trial_lab_panel() marks those invoiced=1 directly, nothing to
	link) or any other case where invoiced ended up set without this
	app's own custom_invoice bookkeeping keeping pace. get_requested_labs()
	now excludes invoiced=1 rows, so this shouldn't normally even be
	reachable for one any more - but if it is (a stale page, a race), it
	self-heals instead of ploughing ahead into _create_lab_invoice(),
	whose invoice.submit() would otherwise crash with a raw, unfriendly
	"already invoiced" ValidationError from healthcare/utils.py's own
	validate_invoiced_on_submit() rather than handling it here.
	"""
	lab_test = frappe.get_doc("Lab Test", lab_test_name)
	if lab_test.prescription:
		frappe.throw(_("Lab Test {0} is encounter-sourced, use accept_lab_request instead").format(lab_test_name))
	if lab_test.custom_invoice:
		frappe.throw(_("Lab Test {0} is already invoiced").format(lab_test_name))

	if lab_test.invoiced:
		# Look for a real Sales Invoice that already covers it and link
		# that instead of attempting (and failing) to raise a second one.
		existing_invoice = frappe.db.get_value(
			"Sales Invoice Item",
			{"reference_dt": "Lab Test", "reference_dn": lab_test.name, "docstatus": 1},
			"parent",
		)
		if existing_invoice:
			lab_test.db_set("custom_invoice", existing_invoice)
			return {
				"status": "Success",
				"invoice_name": existing_invoice,
				"lab_test_name": lab_test.name,
			}

		# No real invoice exists - marked settled with nothing to bill
		# (the free trial panel case). Nothing to invoice, nothing to
		# link - just confirm there's nothing left to do here.
		frappe.msgprint(_("Lab Test {0} needs no invoice - already marked settled.").format(lab_test_name))
		return {
			"status": "Success",
			"invoice_name": None,
			"lab_test_name": lab_test.name,
		}

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


# ---------------------------------------------------------------------
# "Open Lab Test" popup (Trial Labs tab)
# ---------------------------------------------------------------------
# A lightweight in-portal result editor so a lab tech doesn't have to leave
# Lab Portal to enter a trial test's results - the full Lab Test form still
# exists and still works for anything these two functions don't cover.
# Only the two result-table shapes actually in use here are handled -
# Normal/Compound (normal_test_items) and Descriptive (descriptive_test_items).
# A template built around Sensitivity/Organism results (culture panels)
# falls back to result_type "other" - get_lab_test_detail() below doesn't
# try to guess at a layout for those, it just tells the caller to use the
# full form instead.


@frappe.whitelist()
def get_lab_test_detail(lab_test_name):
	"""Loads one Lab Test's own result-entry rows for the "Open Lab Test"
	popup. Each row keeps its own child-table `idx` so save_lab_test_result()
	below can write a saved value back onto the exact same row it came from.

	`docstatus` is included so the dialog can tell a truly-finalized test
	(docstatus 1, submitted by save_lab_test_result() below) apart from
	one just marked Completed on a draft the old way - see lab_portal.js,
	which opens this read-only once a test is actually submitted, rather
	than letting the tech hit Save and get a raw "cannot edit a submitted
	document" error back from the submit attempt.
	"""
	lab_test = frappe.get_doc("Lab Test", lab_test_name)

	if lab_test.normal_test_items:
		result_type = "normal"
		items = [
			{
				"idx": row.idx,
				"label": row.lab_test_name,
				"result_value": row.result_value,
				"uom": row.lab_test_uom,
				"normal_range": row.normal_range,
			}
			for row in lab_test.normal_test_items
		]
	elif lab_test.descriptive_test_items:
		result_type = "descriptive"
		items = [
			{
				"idx": row.idx,
				"label": row.lab_test_particulars,
				"result_value": row.result_value,
			}
			for row in lab_test.descriptive_test_items
		]
	else:
		result_type = "other"
		items = []

	return {
		"name": lab_test.name,
		"patient_name": lab_test.patient_name,
		"template": lab_test.template,
		"lab_test_name": lab_test.lab_test_name,
		"status": lab_test.status,
		"docstatus": lab_test.docstatus,
		"result_type": result_type,
		"items": items,
		"lab_test_comment": lab_test.lab_test_comment,
	}


@frappe.whitelist()
def save_lab_test_result(lab_test_name, result_type, items, lab_test_comment=None, mark_completed=False):
	"""Saves the values entered in the "Open Lab Test" popup back onto the
	Lab Test doc. `items` is the list get_lab_test_detail() handed the
	dialog, each with its `result_value` possibly changed by the user -
	matched back to its row by `idx`, not position, in case rows were
	reordered on some other path in between.

	A partial save (mark_completed falsy) is a plain draft save - nothing
	here should silently complete or lock the test just because a value
	was entered along the way.

	Marking complete (mark_completed truthy) actually SUBMITS the
	document (docstatus 0 -> 1) rather than just flipping the status
	field on a draft, the way this used to work. Lab Test is a
	submittable doctype (is_submittable: 1) and its own on_submit()
	(lab_test.py, unmodified) is what Healthcare core relies on to
	finalize a result: it sets submitted_date, re-sets status to
	"Completed" itself (so the line below is for clarity/intent, not
	load-bearing - on_submit would set it either way), flips the linked
	Service Request to "completed-Request Status", and runs its own
	submit-time checks - validate_result_values() (mandatory result
	values are now actually enforced, where the old .save()-only path
	silently let them through blank) and validate_nursing_tasks() (a
	template with a required nursing checklist now genuinely blocks
	completion until those tasks are done, same as completing straight
	from the Lab Test form would). Either of those raising is a real
	validation failure for the lab tech to address, not a bug - it was
	only ever silently skipped before because this went through .save()
	instead of .submit(), so it may surface for tests that would
	previously have been marked "Completed" without actually satisfying
	either check.
	"""
	if isinstance(items, str):
		items = frappe.parse_json(items)

	lab_test = frappe.get_doc("Lab Test", lab_test_name)

	rows = lab_test.normal_test_items if result_type == "normal" else lab_test.descriptive_test_items
	rows_by_idx = {row.idx: row for row in rows}

	for item in items:
		row = rows_by_idx.get(item.get("idx"))
		if row:
			row.result_value = item.get("result_value")

	if lab_test_comment is not None:
		lab_test.lab_test_comment = lab_test_comment

	if frappe.utils.cint(mark_completed):
		lab_test.status = "Completed"
		lab_test.result_date = lab_test.result_date or today()
		# submit(), not save() - see the docstring above for why this
		# distinction actually matters here. ignore_permissions matches
		# the ignore_permissions=True the plain save() below has always
		# used - submit() takes it as a flag rather than a kwarg.
		lab_test.flags.ignore_permissions = True
		lab_test.submit()
	else:
		lab_test.save(ignore_permissions=True)

	return {"status": "Success", "lab_test_status": lab_test.status}