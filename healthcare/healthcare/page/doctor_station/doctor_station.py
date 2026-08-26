import frappe
from frappe import _
from frappe.utils import nowdate, nowtime

from healthcare.healthcare.page.front_desk.front_desk import (
	_attach_latest_vitals,
	_resolve_patient_full_names,
	_patient_and_practitioner_names,
)

# =============================================
# NOTIFICATION HELPER
# =============================================
# Own copy rather than importing front_desk's - same duplication this
# codebase already uses for lab_portal.py/rehab_portal.py/nurse_station.py's
# private _notify(), so this page has no import-time dependency on
# front_desk.py beyond the three read-only helpers above.


def _notify(event, payload):
	"""Broadcast a realtime event to everyone listening in this site.
	Used to trigger department-specific sound/toast notifications on
	the front-end the instant a queue status changes, without needing
	to poll."""
	frappe.publish_realtime(event=event, message=payload)


# =============================================
# ACCESS CONTROL
# =============================================


def _user_can_access_doctor_station(user=None):
	"""Whether `user` (default: session user) is allowed to use Doctor
	Station, per the comma-separated role list in Healthcare Settings'
	front_desk_doctor_roles - the same setting Front Desk's own Doctor
	Queue tab read before this page existed, kept as-is so a site that
	already configured it doesn't lose that configuration just because
	the tab moved out to its own page. Left unconfigured/blank, this is
	open to anyone who can already reach this page via its own Page.roles
	gate (Physician, System Manager - see doctor_station.json).
	"""
	user = user or frappe.session.user

	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	configured = frappe.db.get_single_value("Healthcare Settings", "front_desk_doctor_roles")
	configured_roles = {r.strip() for r in (configured or "").split(",") if r.strip()}
	if not configured_roles:
		return True

	return bool(configured_roles & set(frappe.get_roles(user)))


def _require_doctor_access():
	"""Server-side gate for every whitelisted method on this page.
	Raises PermissionError (HTTP 403) rather than silently no-op'ing, so
	a blocked call fails loudly whether it came from the page, the
	console, or a direct API request - the Page doctype's own role list
	(doctor_station.json) is what actually stops an unauthorized user from
	opening the page at all; this is the matching guard for the API
	underneath it, same relationship front_desk.py's _require_tab_access
	had to its own tabs."""
	if not _user_can_access_doctor_station():
		frappe.throw(_("You are not permitted to access Doctor Station."), frappe.PermissionError)


# =============================================
# DOCTOR QUEUE
# =============================================
# Moved out of front_desk.py's get_queue()/start_consultation() (formerly
# the "Doctor Queue" tab there) - same relationship Nurse Station has to
# the Front Desk tab it replaced. Queue state itself still lives on Patient
# Appointment (queue_status/checked_in_at etc, stamped by Front Desk's
# check-in flow and Nurse Station's save_vitals()) - this page only reads
# and advances it from here on.


@frappe.whitelist()
def get_doctor_queue(date=None):
	"""Every appointment currently waiting on this doctor - checked in
	today and queue_status "With Doctor" (set by Nurse Station once vitals
	are recorded, or by an app layered on top of Healthcare via its own
	routing - see front_desk.py's _route_after_vitals()). Doesn't include
	anything still with the nurse or already in consultation/completed."""
	_require_doctor_access()
	date = date or nowdate()

	rows = frappe.get_all(
		"Patient Appointment",
		filters={
			"appointment_date": date,
			"checked_in_at": ["is", "set"],
			"queue_status": "With Doctor",
		},
		fields=[
			"name",
			"patient",
			"patient_name",
			"appointment_type",
			"practitioner",
			"practitioner_name",
			"department",
			"appointment_time",
			"queue_status",
			"checked_in_at",
		],
		order_by="appointment_time asc",
	)

	for row in rows:
		row["medical_department"] = row.pop("department")
		row["encounter_time"] = row.pop("appointment_time")

	_attach_latest_vitals(rows)
	_resolve_patient_full_names(rows)

	return rows


@frappe.whitelist()
def start_consultation(appointment):
	"""Practitioner is ready to see this patient - this is where the
	Patient Encounter actually gets created (not at check-in), pre-filled
	from the appointment. Queue tracking keeps living on the Patient
	Appointment right through to Completed - see front_desk.py's
	on_patient_encounter_submit(), which stays there since it's a Patient
	Encounter lifecycle hook, not specific to this page."""
	_require_doctor_access()

	appt = frappe.get_doc("Patient Appointment", appointment)

	# Idempotency: if this appointment somehow already has an Encounter
	# (e.g. a double-click), reuse it instead of creating a second one.
	existing = frappe.db.get_value("Patient Encounter", {"appointment": appt.name}, "name")
	if existing:
		frappe.db.set_value("Patient Appointment", appointment, "queue_status", "In Consultation")
		return {
			"status": "Success",
			"patient": appt.patient,
			"practitioner": appt.practitioner,
			"encounter": existing,
		}

	patient_name, practitioner_name = _patient_and_practitioner_names(appt.patient, appt.practitioner)

	encounter = frappe.get_doc({
		"doctype": "Patient Encounter",
		"patient": appt.patient,
		"patient_name": patient_name,
		"practitioner": appt.practitioner,
		"practitioner_name": practitioner_name,
		"medical_department": appt.department,
		# Patient Encounter has appointment_type as a mandatory field of
		# its own — inherit it from the booking rather than asking the
		# doctor to re-enter something already captured.
		"appointment_type": appt.appointment_type,
		"appointment": appt.name,
		"encounter_date": nowdate(),
		"encounter_time": nowtime(),
	})
	encounter.insert(ignore_permissions=True)
	# Patient Encounter's own on_update() (see patient_encounter.py, not
	# customized here) closes the Patient Appointment the moment
	# `appointment` is set on an inserted/saved Encounter - nothing extra
	# needed here for that.

	# Link whatever vitals the nurse already recorded against the
	# appointment back to the new Encounter too, so anything that expects
	# vitals to be reachable from the Encounter side (print formats,
	# reports) still finds them.
	frappe.db.set_value(
		"Vital Signs",
		{"appointment": appt.name, "docstatus": 1},
		"encounter",
		encounter.name,
	)

	frappe.db.set_value("Patient Appointment", appointment, "queue_status", "In Consultation")

	return {
		"status": "Success",
		"patient": encounter.patient,
		"practitioner": encounter.practitioner,
		"encounter": encounter.name,
	}


# The Lab tab that used to live here (trial-candidate patients parked at
# queue_status "With Lab" - see sports_complex's route_trial_after_vitals()/
# create_trial_lab_panel()) has moved to Lab Portal's own Trial Labs tab -
# see healthcare/page/lab_portal/lab_portal.js and sports_complex's
# get_trial_lab_queue()/get_trial_lab_tests()/send_trial_to_doctor(). Nothing
# in this file was ever involved in serving it (doctor_station.js called
# those sports_complex methods directly), so there's nothing left here to
# remove beyond doctor_station.js's own markup/JS.


# =============================================
# PATIENT SEARCH
# =============================================


@frappe.whitelist()
def search_patients(search_text=None):
	"""Search across every patient in the system - by Patient ID, name, or
	mobile number - not scoped to today's queue, this doctor's own
	appointments, or admission status. A blank search deliberately returns
	nothing rather than the entire Patient list, so this stays a lookup
	tool rather than an unbounded browse; results are capped at 50 for the
	same reason.
	"""
	_require_doctor_access()

	search_text = (search_text or "").strip()
	if not search_text:
		return []

	like = f"%{search_text}%"
	return frappe.db.sql(
		"""
		select
			name, patient_name, sex, dob, mobile, email, blood_group, status
		from `tabPatient`
		where name like %(search)s
			or patient_name like %(search)s
			or mobile like %(search)s
		order by patient_name asc
		limit 50
		""",
		{"search": like},
		as_dict=True,
	)
