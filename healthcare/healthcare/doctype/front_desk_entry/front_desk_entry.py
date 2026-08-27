# Copyright (c) 2026, Ransbort and contributors
# For license information, please see license.txt

"""Front Desk Entry is a lightweight, auto-created log of what Front Desk
did for a patient - one row per consultation check-in/walk-in and one row
per lab-only booking (see front_desk.py's "Lab Test(s) Only" visit type).
It's purely a reporting/audit trail: nothing here is meant to be created
or edited by hand (see front_desk_entry.json's permissions - Healthcare
Receptionist gets read/report/export/print only, no write/create/delete),
and front_desk.py inserts these itself with ignore_permissions=True right
alongside the actions they record.

Two entry points, both called from front_desk.py:
  - log_consultation_entry() - from _finalize_checkin(), right after a
	check-in (booked-appointment or walk-in) is processed.
  - log_lab_only_entry() - from book_lab_only_visit(), right after that
	call's lab tests have all been created/invoiced.

Deliberately living in this module rather than duplicated inline in
front_desk.py - unlike the small per-page helpers this codebase usually
duplicates (_notify(), statusBadge(), etc.), this is doctype-shaping logic
that belongs with the doctype it builds, and it's only ever called from
the one file that produces both kinds of entries.
"""

import frappe
from frappe.model.document import Document


class FrontDeskEntry(Document):
	pass


def log_consultation_entry(appointment):
	"""Log one Front Desk Entry for a consultation check-in/walk-in.
	`appointment` is a Patient Appointment name - read fresh from the
	database rather than passed in as a doc, since _finalize_checkin()
	has already written queue_status/consultation_invoice/paid_amount via
	db_set() by the time this runs, and a stale in-memory doc could miss
	those.

	Best-effort: a logging failure should never take down an actual
	check-in, so this swallows and logs its own errors rather than letting
	them propagate back through _finalize_checkin() to the operator.
	"""
	try:
		appt = frappe.db.get_value(
			"Patient Appointment",
			appointment,
			[
				"patient",
				"patient_name",
				"practitioner",
				"practitioner_name",
				"department",
				"appointment_type",
				"paid_amount",
				"consultation_invoice",
				"appointment_based_on_check_in",
			],
			as_dict=True,
		)
		if not appt:
			return

		frappe.get_doc({
			"doctype": "Front Desk Entry",
			"entry_type": "Consultation",
			"patient": appt.patient,
			"patient_name": appt.patient_name,
			"appointment": appointment,
			"is_walkin": 1 if appt.appointment_based_on_check_in else 0,
			"practitioner": appt.practitioner,
			"practitioner_name": appt.practitioner_name,
			"medical_department": appt.department,
			"appointment_type": appt.appointment_type,
			"consultation_fee": appt.paid_amount,
			"consultation_invoice": appt.consultation_invoice,
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title="Front Desk Entry: failed to log consultation check-in",
			message=f"appointment={appointment}\n{frappe.get_traceback()}",
		)


def log_lab_only_entry(patient, patient_name, rows):
	"""Log one Front Desk Entry for a lab-only booking, with one child row
	per test booked in that same visit (see book_lab_only_visit() in
	front_desk.py, the only caller). `rows` is a list of dicts, each
	already carrying the template/display name/rate/created Lab Test/
	invoice for one test - resolved server-side in book_lab_only_visit()
	from what actually got created, not trusted from the client.

	Best-effort, same reasoning as log_consultation_entry() above - a
	logging failure shouldn't undo or block a booking that already
	succeeded and was already invoiced.
	"""
	try:
		entry = frappe.get_doc({
			"doctype": "Front Desk Entry",
			"entry_type": "Lab Only",
			"patient": patient,
			"patient_name": patient_name,
			"lab_test_count": len(rows),
			"lab_total": sum(float(row.get("rate") or 0) for row in rows),
		})
		for row in rows:
			entry.append("lab_tests", {
				"lab_test_template": row.get("template"),
				"lab_test_name": row.get("lab_test_name"),
				"rate": row.get("rate"),
				"lab_test": row.get("lab_test"),
				"invoice": row.get("invoice"),
			})
		entry.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title="Front Desk Entry: failed to log lab-only booking",
			message=f"patient={patient}\nrows={rows}\n{frappe.get_traceback()}",
		)
