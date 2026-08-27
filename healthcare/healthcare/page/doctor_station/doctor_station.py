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
#
# get_doctor_queue() used to only return appointments already "With
# Doctor" - the queue looked empty right up until someone landed on the
# doctor's desk, with no visibility into who was still moving through
# Front Desk/Nurse Station/Lab. It now returns everyone checked in today
# who hasn't finished (queue_status != Completed), each tagged with a
# normalized `stage` the front-end groups/badges by - see
# _stage_for_queue_status() below. Same filter shape as front_desk.py's
# own get_queue() (checked in today, not yet Completed) - re-implemented
# here rather than calling that directly, since front_desk.get_queue() is
# gated by its own front_desk_queue_roles setting, not doctor access; this
# stays gated by _require_doctor_access() like every other method on this
# page.

# Raw queue_status values (see front_desk.py/nurse_station.py/this page's
# own start_consultation()) mapped to the stage labels doctor_station.js
# groups and badges by. Anything not listed here (there shouldn't be
# anything) falls back to the raw value unchanged - see
# _stage_for_queue_status().
_STAGE_LABELS = {
	"Payment Pending": "Front Desk",
	"Paid - Awaiting Vitals": "Front Desk",
	"With Nurse": "With Nurse",
	"With Lab": "With Lab",
	"With Doctor": "With Doctor",
	"In Consultation": "In Consultation",
}


def _stage_for_queue_status(queue_status):
	return _STAGE_LABELS.get(queue_status, queue_status)


@frappe.whitelist()
def get_doctor_queue(date=None):
	"""Every appointment still moving through today's pipeline - not just
	the ones already "With Doctor" - so a doctor can see how close the
	next few patients actually are instead of the queue looking empty
	until someone lands on their desk. "With Lab" rows don't carry lab
	progress here (this app doesn't depend on sports_complex) -
	doctor_station.js fetches that separately from sports_complex.
	healthcare_integration.get_trial_lab_queue() and merges it in by
	appointment name, same as this page's old Lab tab did.
	"""
	_require_doctor_access()
	date = date or nowdate()

	rows = frappe.get_all(
		"Patient Appointment",
		filters={
			"appointment_date": date,
			"checked_in_at": ["is", "set"],
			"queue_status": ["!=", "Completed"],
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
		row["stage"] = _stage_for_queue_status(row["queue_status"])

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


# save_quick_consultation() used to live here, saving a small hand-picked
# subset of fields (symptoms/diagnosis/encounter_comment) posted from a
# custom quick-capture Dialog. Removed: doctor_station.js now opens the
# Patient Encounter's real, complete form embedded directly inside a
# Dialog (see openEncounterDialog() there) instead of a hand-built
# stand-in, so saving goes through that form's own frm.save() - the same
# frappe.client.save path every ordinary form uses - and there's no
# custom subset-of-fields endpoint left to maintain here.


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
