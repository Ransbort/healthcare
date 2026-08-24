import frappe
from frappe import _
from frappe.utils import nowdate, nowtime

from healthcare.healthcare.page.front_desk.front_desk import (
	_attach_latest_vitals,
	_resolve_patient_full_names,
)

# =============================================
# NOTIFICATION HELPER
# =============================================
# Own copy rather than importing front_desk's - same duplication this
# codebase already uses for lab_portal.py/rehab_portal.py's private
# _notify(), so this page has no import-time dependency on front_desk.py
# beyond the two read-only helpers above.


def _notify(event, payload):
	"""Broadcast a realtime event to everyone listening in this site.
	Used to trigger department-specific sound/toast notifications on
	the front-end the instant a queue status changes, without needing
	to poll."""
	frappe.publish_realtime(event=event, message=payload)


# =============================================
# ACCESS CONTROL
# =============================================


def _user_can_access_nurse_station(user=None):
	"""Whether `user` (default: session user) is allowed to use Nurse
	Station, per the comma-separated role list in Healthcare Settings'
	front_desk_nurse_roles - the same setting Front Desk's own Nurse
	Station tab read before this page existed, kept as-is so a site that
	already configured it doesn't lose that configuration just because
	the tab moved out to its own page. Left unconfigured/blank, this is
	open to anyone who can already reach this page via its own Page.roles
	gate (Nursing User, Physician, System Manager - see nurse_station.json).
	"""
	user = user or frappe.session.user

	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	configured = frappe.db.get_single_value("Healthcare Settings", "front_desk_nurse_roles")
	configured_roles = {r.strip() for r in (configured or "").split(",") if r.strip()}
	if not configured_roles:
		return True

	return bool(configured_roles & set(frappe.get_roles(user)))


def _require_nurse_access():
	"""Server-side gate for every whitelisted method on this page.
	Raises PermissionError (HTTP 403) rather than silently no-op'ing, so
	a blocked call fails loudly whether it came from the page, the
	console, or a direct API request - the Page doctype's own role list
	(nurse_station.json) is what actually stops an unauthorized user from
	opening the page at all; this is the matching guard for the API
	underneath it, same relationship front_desk.py's _require_tab_access
	had to its own tabs."""
	if not _user_can_access_nurse_station():
		frappe.throw(_("You are not permitted to access Nurse Station."), frappe.PermissionError)


# =============================================
# QUEUE
# =============================================


def _nurse_queue_appointments(date):
	"""Every appointment that belongs on the Nurse Station's own list for
	`date` right now: checked in that day, not yet dismissed (see
	clear_nurse_queue()), and either still waiting on vitals or already
	has a submitted Vital Signs record - regardless of how far the
	appointment has since moved on its own (With Doctor, In
	Consultation, even Completed). A doctor progressing their own queue
	never removes a row from here - only clear_nurse_queue() does, via
	custom_nurse_queue_dismissed.

	Shared by get_nurse_queue() (which decorates the result for display)
	and clear_nurse_queue() (which only needs to know which appointments
	to act on) - keeping both on the exact same definition of "what's on
	the nurse's list" so Clear All can never miss or over-clear relative
	to what's actually shown.
	"""
	candidates = frappe.get_all(
		"Patient Appointment",
		filters={
			"appointment_date": date,
			"checked_in_at": ["is", "set"],
			"custom_nurse_queue_dismissed": 0,
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
	if not candidates:
		return []

	candidate_ids = [c["name"] for c in candidates]
	has_vitals = set(frappe.get_all(
		"Vital Signs",
		filters={"appointment": ["in", candidate_ids], "docstatus": 1},
		pluck="appointment",
	))

	return [c for c in candidates if c["queue_status"] == "With Nurse" or c["name"] in has_vitals]


@frappe.whitelist()
def get_nurse_queue(date=None):
	"""Nurse Station's own queue - deliberately broader than a plain
	get_queue(queue_status="With Nurse") call, and deliberately NOT tied
	to current queue_status at all beyond _nurse_queue_appointments()'s
	own definition. Without this, a patient dropped off the nurse's own
	list the moment save_vitals() sent them on - or, further down the
	line, the moment a doctor advanced past "With Doctor" - even though
	the nurse might still need to see or correct what they recorded. The
	only thing that removes a row from this list is the nurse explicitly
	clearing it - see clear_nurse_queue().
	"""
	_require_nurse_access()
	date = date or nowdate()

	rows = _nurse_queue_appointments(date)

	for row in rows:
		row["medical_department"] = row.pop("department")
		row["encounter_time"] = row.pop("appointment_time")

	_attach_latest_vitals(rows)
	_resolve_patient_full_names(rows)

	return rows


@frappe.whitelist()
def clear_nurse_queue(date=None):
	"""Clears everything currently on the Nurse Station's own list for
	the given date (see _nurse_queue_appointments()) - both patients
	still waiting on vitals and ones already sent on. This is the only
	thing that ever removes a row from that list; it no longer disappears
	on its own as a doctor's consultation progresses.

	Two different things happen depending on where each appointment
	actually is, so a doctor already mid-consultation is never disturbed:
	  - Still "With Nurse" (never sent): queue_status resets to "Paid -
	    Awaiting Vitals" - the real workflow state right before the
	    nurse claimed it, so it's simply available to send again.
	  - Already sent on (has a submitted Vital Signs record, whatever its
	    current queue_status is - With Doctor, In Consultation, even
	    Completed): queue_status is left completely alone. Instead this
	    flips custom_nurse_queue_dismissed so it drops off *this* list,
	    without touching the real pipeline at all.

	Either way, no Vital Signs record is ever touched or deleted here -
	this only ever affects queue/view state, never clinical data.
	"""
	_require_nurse_access()
	date = date or nowdate()

	rows = _nurse_queue_appointments(date)

	cleared = []
	for row in rows:
		if row["queue_status"] == "With Nurse":
			frappe.db.set_value("Patient Appointment", row["name"], "queue_status", "Paid - Awaiting Vitals")
		else:
			frappe.db.set_value("Patient Appointment", row["name"], "custom_nurse_queue_dismissed", 1)
		cleared.append(row["name"])

	if cleared:
		_notify("queue_update", {
			"department": "nurse",
			"message": f"Cleared {len(cleared)} patient(s) from the nurse queue",
			"encounter": None,
		})

	return {"status": "Success", "cleared": cleared}


# =============================================
# VITALS
# =============================================


def _route_after_vitals(appointment, appointment_type):
	"""Extension point for an app layered on top of Healthcare (e.g.
	sports_complex) to redirect an appointment somewhere other than
	straight to the doctor queue once vitals are recorded - e.g. a
	predetermined lab panel that has to complete first. Called from
	save_vitals() below, right where queue_status would otherwise become
	"With Doctor" unconditionally.

	Returns True if some other app claimed this appointment and fully
	handled the routing itself (queue_status + notification both done) -
	False means save_vitals() should run its own default "With Doctor"
	path, unchanged. A soft/lazy import keeps this file free of any hard
	dependency on sports_complex (or any other app) being installed - a
	site running plain Healthcare behaves exactly as it always has.
	"""
	try:
		from sports_complex.sports_complex.healthcare_integration import route_trial_after_vitals
	except ImportError:
		return False

	return bool(route_trial_after_vitals(appointment, appointment_type))


def _calculate_bmi(weight, height_cm):
	"""BMI = weight(kg) / height(m)^2. Computed server-side (rather than
	trusting a client-supplied value) so it can never drift out of sync
	with the weight/height actually saved on the Vital Signs doc. Returns
	None if either input is missing, non-numeric, or height is
	non-positive (would otherwise divide by zero / produce a nonsense
	negative BMI). height_cm is in centimetres, matching what the nurse
	station form collects."""

	try:
		weight = float(weight)
		height_cm = float(height_cm)
	except (TypeError, ValueError):
		return None

	if not weight or not height_cm or height_cm <= 0:
		return None

	height_m = height_cm / 100
	return round(weight / (height_m ** 2), 2)


def _split_blood_pressure(blood_pressure):
	"""The nurse station form still collects blood pressure as one
	"120/80" text field, but the standard Vital Signs doctype stores it
	as separate bp_systolic/bp_diastolic numbers. Split it here rather
	than changing the front-end. Returns (systolic, diastolic), either or
	both of which may be None if the value is missing or not in
	"NNN/NNN" form."""

	if not blood_pressure:
		return None, None

	parts = str(blood_pressure).split("/")
	if len(parts) != 2:
		return None, None

	try:
		return float(parts[0].strip()), float(parts[1].strip())
	except ValueError:
		return None, None


@frappe.whitelist()
def save_vitals(
	appointment,
	temperature=None,
	blood_pressure=None,
	pulse=None,
	respiratory_rate=None,
	tongue=None,
	abdomen=None,
	reflexes=None,
	weight=None,
	height=None,
	spo2=None,
	fbs=None,
	rbs=None,
	notes=None
):
	_require_nurse_access()

	appt = frappe.db.get_value("Patient Appointment", appointment, ["patient"], as_dict=True)
	bp_systolic, bp_diastolic = _split_blood_pressure(blood_pressure)
	default_company = frappe.defaults.get_global_default("company")

	vitals_doc = frappe.get_doc({
		"doctype": "Vital Signs",
		"naming_series": "HLC-VTS-.YYYY.-",

		"patient": appt.patient,
		"appointment": appointment,
		# No Patient Encounter exists yet at this point - it's only
		# created once a practitioner clicks Start Consultation, see
		# front_desk.py's start_consultation(), which backfills this
		# Vital Signs doc's `encounter` field once that happens.
		"company": default_company,

		"signs_date": nowdate(),
		"signs_time": nowtime(),

		"temperature": temperature,
		"pulse": pulse,
		"respiratory_rate": respiratory_rate,
		"tongue": tongue,
		"abdomen": abdomen,
		"reflexes": reflexes,
		"bp_systolic": bp_systolic,
		"bp_diastolic": bp_diastolic,
		# bp_systolic/diastolic are the real stored values; "bp" is only a
		# read-only display column that nothing in the standard Vital
		# Signs controller populates automatically, so set it explicitly
		# from the same text the nurse typed.
		"bp": blood_pressure,
		"height": (float(height) / 100) if height else None,
		"weight": weight,
		"bmi": _calculate_bmi(weight, height),

		"custom_spo2": spo2,
		"custom_fbs": fbs,
		"custom_rbs": rbs,

		# Always the signed-in nurse, stamped server-side - never take this
		# from the client, or anyone could attribute a recording to
		# whoever they like.
		"custom_vitals_recorded_by": frappe.session.user,

		"vital_signs_note": notes,
	})
	vitals_doc.insert(ignore_permissions=True)
	vitals_doc.submit()

	appointment_type = frappe.db.get_value("Patient Appointment", appointment, "appointment_type")
	routed = _route_after_vitals(appointment, appointment_type)

	if not routed:
		frappe.db.set_value("Patient Appointment", appointment, "queue_status", "With Doctor")

		patient_name = frappe.db.get_value("Patient Appointment", appointment, "patient_name")
		_notify("queue_update", {
			"department": "doctor",
			"message": f"{patient_name} ready for consultation",
			"encounter": None,
		})

	return {"status": "Success"}


@frappe.whitelist()
def update_vitals(
	appointment,
	temperature=None,
	blood_pressure=None,
	pulse=None,
	respiratory_rate=None,
	tongue=None,
	abdomen=None,
	reflexes=None,
	weight=None,
	height=None,
	spo2=None,
	fbs=None,
	rbs=None,
	notes=None
):
	"""In-place correction of the vitals already recorded for this
	appointment - same Vital Signs record, not a new one, matching how
	this app already treats other submitted-but-operationally-mutable
	records elsewhere (Facility Booking's booking_status, Paystack
	Payment Log, etc). Deliberately doesn't touch
	custom_vitals_recorded_by - that stays attributed to whichever nurse
	originally recorded it, not whoever corrects a typo later.

	Only ever updates the *latest* submitted Vital Signs doc for this
	appointment - same "latest wins" rule get_nurse_queue() (via
	front_desk.py's _attach_latest_vitals()) uses to decide which one to
	display in the first place, so an edit always lands on the same
	record the nurse is looking at.
	"""
	_require_nurse_access()

	vitals_name = frappe.db.get_value(
		"Vital Signs",
		{"appointment": appointment, "docstatus": 1},
		"name",
		order_by="creation desc",
	)
	if not vitals_name:
		frappe.throw(_("No vitals have been recorded yet for this appointment - use Record Vitals instead."))

	bp_systolic, bp_diastolic = _split_blood_pressure(blood_pressure)

	updates = {
		"temperature": temperature,
		"pulse": pulse,
		"respiratory_rate": respiratory_rate,
		"tongue": tongue,
		"abdomen": abdomen,
		"reflexes": reflexes,
		"bp_systolic": bp_systolic,
		"bp_diastolic": bp_diastolic,
		"bp": blood_pressure,
		"height": (float(height) / 100) if height else None,
		"weight": weight,
		"bmi": _calculate_bmi(weight, height),
		"custom_spo2": spo2,
		"custom_fbs": fbs,
		"custom_rbs": rbs,
		"vital_signs_note": notes,
	}

	vitals_doc = frappe.get_doc("Vital Signs", vitals_name)
	for fieldname, value in updates.items():
		vitals_doc.db_set(fieldname, value, update_modified=True)

	return {"status": "Success", "vitals": vitals_name}
