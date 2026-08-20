import frappe
from frappe import _
from frappe.utils import now_datetime, nowdate, nowtime, add_to_date
from healthcare.healthcare.utils import get_appointment_billing_item_and_rate
from healthcare.healthcare.doctype.appointment_type.appointment_type import (
	get_billing_details as get_appointment_type_billing_row,
)


def _get_billing_detail_or_none(doc):
	"""get_appointment_billing_item_and_rate() calls frappe.throw() when a
	practitioner has no OP Consulting Charge configured and there's no
	Appointment Type fallback either - fine for the native "Show Payment
	Prompt in Appointment" flow it was written for, where that's meant to
	be a hard stop, but front desk only ever wants this as a
	best-effort price lookup (both call sites below already have their
	own fallback/backoff for exactly this "not configured yet" case).

	Catching the exception alone isn't enough to suppress it though:
	frappe.throw() queues its message via frappe.msgprint(raise_exception=
	True), which appends to frappe.local.message_log *before* raising -
	so even a caught exception leaves that message sitting in the log,
	and Frappe still serializes it into the response's _server_messages
	and pops the "Missing Configuration" dialog on the client regardless
	of whether the request otherwise succeeded. Trimming the log back to
	its pre-call length is what actually swallows it end to end."""
	log_len = len(frappe.local.message_log)
	try:
		return get_appointment_billing_item_and_rate(doc)
	except Exception:
		del frappe.local.message_log[log_len:]
		return None


# =============================================
# GET SERVER TODAY
# =============================================

@frappe.whitelist()
def get_server_today():
	"""The site's own idea of 'today', for the front-end to default its
	date filters against instead of the browser's local clock/timezone —
	the two can disagree by a day if the browser sits in a different
	timezone than the site, since encounter_date is always stamped with
	server-side nowdate()."""
	return nowdate()


@frappe.whitelist()
def get_default_appointment_type():
	"""Healthcare Settings' configured default (e.g. "walk-in"), so the
	Check-In form's Appointment Type field starts pre-filled instead of
	blank, matching what's set under Healthcare Settings > Patient Portal
	> Default Appointment Type."""
	return frappe.db.get_single_value("Healthcare Settings", "default_appointment_type")

# =============================================
# NOTIFICATION HELPER
# =============================================

def _notify(event, payload):
	"""Broadcast a realtime event to everyone listening in this site.
	Used to trigger department-specific sound/toast notifications on
	the front-end the instant a queue status changes, without needing
	to poll."""
	frappe.publish_realtime(event=event, message=payload)


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

# =============================================
# TAB ACCESS CONTROL
# =============================================

FRONT_DESK_TABS = ["checkin", "queue", "nurse", "lab", "doctor"]

TAB_ROLES_FIELD = {
	"checkin": "front_desk_checkin_roles",
	"queue": "front_desk_queue_roles",
	"nurse": "front_desk_nurse_roles",
	"lab": "front_desk_lab_roles",
	"doctor": "front_desk_doctor_roles",
}

TAB_LABEL = {
	"checkin": _("Check-In"),
	"queue": _("Queue"),
	"nurse": _("Nurse Station"),
	"lab": _("Lab"),
	"doctor": _("Doctor Queue"),
}


def _configured_roles_for_tab(tab):
	fieldname = TAB_ROLES_FIELD[tab]
	configured = frappe.db.get_single_value("Healthcare Settings", fieldname)
	return {r.strip() for r in (configured or "").split(",") if r.strip()}


def _user_can_access_tab(tab, user=None):
	"""Whether `user` (default: session user) is allowed to access the
	given Front Desk tab, per the comma-separated role list configured
	in Healthcare Settings (front_desk_<tab>_roles). A tab left
	unconfigured/blank is open to anyone - so a site that has never
	touched this settings section behaves exactly as before this
	feature existed.
	"""
	user = user or frappe.session.user

	# Admins/System Managers always pass, so nobody can lock themselves
	# out of their own Front Desk configuration.
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	configured_roles = _configured_roles_for_tab(tab)
	if not configured_roles:
		return True

	return bool(configured_roles & set(frappe.get_roles(user)))


def _get_allowed_tabs(user=None):
	return [tab for tab in FRONT_DESK_TABS if _user_can_access_tab(tab, user)]


def _require_tab_access(tab):
	"""Server-side gate for any whitelisted method that belongs to a
	specific Front Desk tab. Raises PermissionError (HTTP 403) rather
	than silently no-op'ing, so a blocked call fails loudly whether it
	came from the page, the console, or a direct API request - the
	front-end hiding the tab (see get_front_desk_settings) is a UX
	nicety on top of this, never a substitute for it.
	"""
	if not _user_can_access_tab(tab):
		frappe.throw(
			_("You are not permitted to access the {0} area of Front Desk.").format(TAB_LABEL[tab]),
			frappe.PermissionError,
		)

# =============================================
# BULK SEND TO NURSE
# =============================================

@frappe.whitelist()
def bulk_send_to_nurse(appointments):
	"""Send every currently 'Paid - Awaiting Vitals' appointment in the
	given list to the nurse queue in one action. Re-checks queue_status
	server-side rather than trusting the front-end's snapshot, in case
	something changed between page load and this click.

	Queue state lives on Patient Appointment, not Patient Encounter - see
	start_consultation() below for why (the Encounter isn't created until
	a practitioner is actually ready to see the patient)."""
	_require_tab_access("queue")
	import json
	if isinstance(appointments, str):
		appointments = json.loads(appointments)

	if not appointments:
		return {"status": "Success", "updated": []}

	eligible = frappe.get_all(
		"Patient Appointment",
		filters={
			"name": ["in", appointments],
			"queue_status": "Paid - Awaiting Vitals",
		},
		pluck="name",
	)

	for name in eligible:
		frappe.db.set_value("Patient Appointment", name, "queue_status", "With Nurse")

	if eligible:
		_notify("queue_update", {
			"department": "nurse",
			"message": f"{len(eligible)} patient(s) sent to nurse station",
			"encounter": None,
		})

	return {"status": "Success", "updated": eligible}

# =============================================
# PATIENT REGISTRATION
# =============================================

@frappe.whitelist()
def get_front_desk_settings():
	"""Front-end config lookup, called once when the page loads. Right
	now this only covers whether the patient UID should be typed in by
	the front desk or generated automatically - see
	_resolve_patient_uid() below - but it's the natural place to add
	any other Healthcare Settings the front desk page needs to react
	to without hardcoding them into front_desk.js."""

	return {
		"auto_generate_patient_uid": bool(
			frappe.db.get_single_value("Healthcare Settings", "auto_generate_patient_uid")
		),
		"allowed_tabs": _get_allowed_tabs(),
	}


def _resolve_patient_uid(uid):
	"""Healthcare Settings can be configured to auto-generate the
	patient UID instead of leaving it to be typed in by front desk /
	nursing staff (a manual UID is an easy place for a typo or a
	duplicate to slip in). When that's switched on, front_desk.js
	disables the UID input entirely - see get_front_desk_settings()
	above - so whatever comes through in `uid` here is ignored in
	favour of the next value off the configured naming series.
	When it's switched off, fall back to what was typed in, exactly
	as before.
	"""

	if not frappe.db.get_single_value("Healthcare Settings", "auto_generate_patient_uid"):
		return uid

	from frappe.model.naming import make_autoname

	naming_series = (
		frappe.db.get_single_value("Healthcare Settings", "patient_uid_naming_series")
		or "UID-.#####"
	)
	return make_autoname(naming_series)


def _defer_customer_creation(patient_doc):
	"""Patient.on_update() (see healthcare/healthcare/doctype/patient/patient.py
	in the core Healthcare app) auto-creates and links a Customer as part
	of patient.insert() itself, whenever Healthcare Settings has "Link
	Customer to Patient" enabled - before any of our code below even
	runs. We don't want that Customer to exist until the operator has
	actually confirmed the registration in the popup, so immediately
	undo it here: delete the just-created Customer and clear the link.
	It's re-created in _create_customer_for_patient() once
	confirm_patient_registration() runs.

	One complication: that same on_update() call runs set_contact()
	right after create_customer(), by which point self.customer is
	already set - so it also creates a Contact linked to BOTH the
	Patient and this brand-new Customer, in the same request. That
	Contact link blocks deleting the Customer below (Frappe won't
	delete a Customer something still links to), so it has to be
	stripped off the Contact first - just the Customer link row, not
	the whole Contact, since the Patient's own link on it is legitimate
	and worth keeping.
	"""

	customer_name = patient_doc.customer
	if not customer_name:
		return

	patient_doc.db_set("customer", None, update_modified=False)

	contact_name = frappe.db.get_value(
		"Dynamic Link",
		{"link_doctype": "Customer", "link_name": customer_name, "parenttype": "Contact"},
		"parent",
	)
	if contact_name:
		try:
			contact = frappe.get_doc("Contact", contact_name)
			contact.links = [
				link for link in contact.links
				if not (link.link_doctype == "Customer" and link.link_name == customer_name)
			]
			contact.save(ignore_permissions=True)
		except Exception:
			frappe.log_error(
				title="Front Desk: could not unlink auto-created Contact before deferring Customer",
				message=frappe.get_traceback(),
			)

	if frappe.db.exists("Customer", customer_name):
		try:
			frappe.delete_doc("Customer", customer_name, ignore_permissions=True, force=True)
		except Exception:
			# Unexpected reference already picked up the Customer -
			# don't fail the registration over it, just leave it linked
			# rather than losing track of it.
			frappe.log_error(
				title="Front Desk: could not defer Customer creation",
				message=frappe.get_traceback(),
			)
			patient_doc.db_set("customer", customer_name, update_modified=False)


def _create_customer_for_patient(patient_doc):
	"""Re-run the same Customer creation Patient.validate() would have
	done automatically, now that the operator has confirmed the
	registration. Reuses Healthcare's own create_customer() so the
	result is identical to what the normal (non-deferred) flow would
	have produced - just delayed until confirmation.
	"""

	if patient_doc.customer:
		return

	if not frappe.db.get_single_value("Healthcare Settings", "link_customer_to_patient"):
		return

	from healthcare.healthcare.doctype.patient.patient import create_customer
	create_customer(patient_doc)
	patient_doc.reload()


@frappe.whitelist()
def create_walkin_patient(
	first_name,
	last_name=None,
	mobile=None,
	gender=None,
	dob=None,
	uid=None,
	email=None,
):
	_require_tab_access("checkin")
	"""Register a brand-new walk-in patient.

	This only creates the Patient record and hands its details straight
	back to the front-end - it does NOT raise the registration-fee
	invoice, and does NOT leave a Customer record linked, yet. The
	front desk is expected to show the entered details back to the
	operator in a confirmation popup and call
	confirm_patient_registration() once they confirm; that's the point
	at which both the Customer and the invoice actually get created.
	This gives the operator a chance to catch typos before records that
	are harder to unwind (an invoice, a billing Customer) get raised
	against them.

	If Healthcare Settings has "Collect Fee for Patient Registration"
	checked, Patient.after_insert() has already flipped this record to
	status=Disabled (see healthcare/patient.py) - regardless of whether
	the invoice has been raised yet. The patient stays Disabled - and
	blocked from check-in (see _ensure_patient_enabled below) - until
	the registration invoice is raised (via confirm_patient_registration)
	AND paid off, at which point on_payment_entry_submit() re-enables
	them.
	"""

	# Defense in depth: the front-end form already marks these required
	# (matching Healthcare's own native New Patient quick-entry, which
	# has the same fields), but this is a whitelisted endpoint reachable
	# on its own - don't rely on the client to enforce it. Email is
	# deliberately not in this list - it's optional, both here and on
	# the front-end.
	missing = [
		label
		for value, label in (
			(last_name, _("Last Name")),
			(mobile, _("Mobile")),
			(gender, _("Gender")),
			(dob, _("Date of Birth")),
		)
		if not value
	]
	if missing:
		frappe.throw(_("Please provide: {0}").format(", ".join(missing)))

	patient = frappe.get_doc({
		"doctype": "Patient",
		"first_name": first_name,
		"last_name": last_name,
		"mobile": mobile,
		"sex": gender,
		"dob": dob,
		"uid": _resolve_patient_uid(uid),
		"email": email,
		# Patient.invite_user defaults to checked (1) at the doctype
		# level, which would silently create a portal account
		# (Patient.validate() -> create_website_user() in
		# healthcare/patient.py) for every walk-in with an email -
		# forced off here, since Front Desk doesn't offer any way for
		# the operator to grant portal access from this form.
		"invite_user": 0,
	})

	patient.insert(ignore_permissions=True)
	_defer_customer_creation(patient)

	# Surface the actual fee amount (not just whether one will be
	# charged) so the front-end confirmation dialog can show the
	# operator exactly what's about to be invoiced, instead of a vague
	# "a fee will be charged" message.
	collect_fee = bool(
		frappe.db.get_single_value("Healthcare Settings", "collect_registration_fee")
	)
	registration_fee = (
		frappe.db.get_single_value("Healthcare Settings", "registration_fee")
		if collect_fee else None
	)

	return {
		"status": "Success",
		"patient": patient.name,
		"patient_name": patient.patient_name,
		"first_name": patient.first_name,
		"last_name": patient.last_name,
		"mobile": patient.mobile,
		"gender": patient.sex,
		"dob": patient.dob,
		"uid": patient.uid,
		"email": patient.email,
		"patient_status": frappe.db.get_value("Patient", patient.name, "status"),
		"fee_will_be_charged": collect_fee,
		"registration_fee": registration_fee,
	}


@frappe.whitelist()
def confirm_patient_registration(patient):
	_require_tab_access("checkin")
	"""Operator has reviewed the just-created patient's details in the
	front-end confirmation popup and confirmed them. Only now do we
	create the linked Customer (if Healthcare Settings calls for one)
	and raise the registration-fee invoice (if Healthcare Settings
	calls for one) - see create_walkin_patient() above for why these
	are deferred to a separate step."""

	patient_doc = frappe.get_doc("Patient", patient)

	_create_customer_for_patient(patient_doc)

	registration_invoice = None
	if frappe.db.get_single_value("Healthcare Settings", "collect_registration_fee"):
		registration_invoice = _raise_registration_invoice(patient_doc)

	# No fee actually got invoiced (collection is off entirely, or on
	# but nothing's configured to invoice) - registration is complete
	# right now, there's no cashier payment step to wait for. A
	# fee-owing patient gets this later instead, from
	# _enable_patient_after_registration_payment() once actually paid -
	# see _send_registration_email()'s docstring.
	#
	# Note: this only covers the email - native Patient.after_insert()/
	# invoice_patient_registration() (healthcare/doctype/patient/patient.py)
	# send the registration SMS themselves, at their own (earlier) timing:
	# on raw insert when no fee is collected, or the moment the invoice
	# is raised when one is. That's real native behaviour, not a bug in
	# this file - patient.py is intentionally left untouched.
	if not registration_invoice:
		_send_registration_email(patient_doc)

	return {
		"status": "Success",
		"patient": patient_doc.name,
		"patient_name": patient_doc.patient_name,
		"registration_invoice": registration_invoice,
		"patient_status": frappe.db.get_value("Patient", patient_doc.name, "status"),
	}


@frappe.whitelist()
def cancel_patient_registration(patient):
	_require_tab_access("checkin")
	"""Operator caught a mistake in the confirmation popup and backed
	out instead of confirming. Safe to hard-delete here because this
	only ever runs before confirm_patient_registration() has had a
	chance to create a Customer or raise any invoice against the
	patient - nothing meaningful links to the record yet, except one
	thing: Patient.on_update() (healthcare/doctype/patient/patient.py)
	unconditionally auto-creates a Contact linked to the Patient on
	every insert whenever email/mobile/phone is set - which, since New
	Patient made Email and Mobile required, now means every walk-in
	registration. Frappe's own link-integrity check then refuses to
	delete a Patient that Contact still points at, so that has to go
	first - it was only ever created moments ago for this
	still-unconfirmed draft, nothing else could have referenced it."""

	if frappe.db.exists("Sales Invoice Item", {"reference_dt": "Patient", "reference_dn": patient}):
		frappe.throw(_("This patient already has an invoice raised and can no longer be discarded."))

	contact_name = frappe.db.get_value(
		"Dynamic Link",
		{"link_doctype": "Patient", "link_name": patient, "parenttype": "Contact"},
		"parent",
	)
	if contact_name:
		frappe.delete_doc("Contact", contact_name, ignore_permissions=True, force=True)

	frappe.delete_doc("Patient", patient, ignore_permissions=True)

	return {"status": "Success"}


def _raise_registration_invoice(patient):
	"""Create (or reuse) the registration-fee Sales Invoice for `patient`
	and make sure it's submitted so it actually shows up as payable at
	the Cashier Portal.

	Patient.invoice_patient_registration() already does the fee/item
	lookup and de-dupes against an existing draft invoice for this
	patient, but it leaves the invoice in draft (docstatus=0) - submit
	it here ourselves, same as _invoice_consultation() does for
	consultation fees below.
	"""

	invoice_dict = patient.invoice_patient_registration()
	if not invoice_dict:
		# No registration_fee configured in Healthcare Settings even
		# though the "collect fee" checkbox is on - nothing to invoice,
		# so leave the patient exactly as after_insert() left them.
		return None

	invoice = frappe.get_doc("Sales Invoice", invoice_dict.get("name"))
	if invoice.docstatus == 0:
		invoice.submit()

	return invoice.name


def _ensure_patient_enabled(patient):
	"""Block check-in for a patient who still owes the registration
	fee. Enforced server-side (not just hidden/disabled in the UI) so
	a stale page or a direct API call can't skip payment."""

	status = frappe.db.get_value("Patient", patient, "status")
	if status == "Disabled":
		frappe.throw(
			_(
				"Patient {0} still owes the registration fee. Please collect "
				"payment at the Cashier Portal before checking them in."
			).format(patient)
		)


@frappe.whitelist()
def get_patient_checkin_status(patient):
	_require_tab_access("checkin")
	"""Whether `patient` is currently blocked from check-in pending
	registration fee payment, so the front desk can warn about it
	before staff even try to check the patient in (rather than only
	finding out from the server error raised by _ensure_patient_enabled)."""

	status = frappe.db.get_value("Patient", patient, "status")
	return {"status": status, "registration_fee_pending": status == "Disabled"}


DEFAULT_APPOINTMENT_DURATION_MINUTES = 15
MINIMUM_APPOINTMENT_DURATION_MINUTES = 5


def _resolve_duration(appointment_type):
	"""Resolve appointment duration.

	Healthcare validates that appointment_end_datetime
	must be after appointment_datetime.

	Prefer Appointment Type duration.
	Fallback to default duration.

	Hard floor at MINIMUM_APPOINTMENT_DURATION_MINUTES so that,
	regardless of what Appointment Type / Practitioner-level
	overrides do downstream inside Healthcare's own validate(),
	we never hand off a 0/negative/None duration.
	"""

	duration = None

	if appointment_type:
		duration = frappe.db.get_value(
			"Appointment Type",
			appointment_type,
			"default_duration"
		)

	try:
		duration = int(duration) if duration else DEFAULT_APPOINTMENT_DURATION_MINUTES
	except (TypeError, ValueError):
		duration = DEFAULT_APPOINTMENT_DURATION_MINUTES

	if duration < MINIMUM_APPOINTMENT_DURATION_MINUTES:
		duration = MINIMUM_APPOINTMENT_DURATION_MINUTES

	return duration


# =============================================
# BOOKING (schedule only — no queue, no invoice)
# =============================================

@frappe.whitelist()
def create_consultation(
	patient,
	practitioner,
	department=None,
	appointment_type=None,
	appointment_date=None,
	appointment_time=None,
):
	"""Book a Patient Appointment.

	This is a pure schedule record now: no queue_status, no
	checked_in_at, no invoice. Those only come into existence once the
	patient physically arrives — see check_in_appointment() below.
	"""

	appointment_date = appointment_date or nowdate()
	appointment_time = appointment_time or nowtime()

	duration = int(_resolve_duration(appointment_type))

	appointment_datetime = f"{appointment_date} {appointment_time}"
	appointment_end_datetime = add_to_date(appointment_datetime, minutes=duration)

	appointment = frappe.get_doc({
		"doctype": "Patient Appointment",

		"patient": patient,
		"practitioner": practitioner,
		"department": department,
		"appointment_type": appointment_type,

		"appointment_date": appointment_date,
		"appointment_time": appointment_time,

		"appointment_datetime": appointment_datetime,
		"appointment_end_datetime": appointment_end_datetime,

		"duration": duration,

		"status": "Open",
	})

	try:
		appointment.insert(ignore_permissions=True)
	except frappe.ValidationError:
		frappe.log_error(
			title="Front Desk: create_consultation appointment insert failed",
			message=(
				f"patient={patient}\n"
				f"practitioner={practitioner}\n"
				f"department={department}\n"
				f"appointment_type={appointment_type}\n"
				f"appointment_date={appointment_date!r}\n"
				f"appointment_time={appointment_time!r}\n"
				f"resolved_duration={duration!r}\n"
				f"appointment_datetime={appointment_datetime!r}\n"
				f"appointment_end_datetime={appointment_end_datetime!r}\n"
			),
		)
		raise

	return {
		"status": "Success",
		"appointment": appointment.name,
	}


@frappe.whitelist()
def get_pending_checkins(date=None, patient=None):
	_require_tab_access("checkin")
	"""Booked appointments for `date` that have not yet been checked in
	(checked_in_at not yet stamped - see check_in_appointment() below)."""

	date = date or nowdate()

	filters = {
		"appointment_date": date,
		"status": ["!=", "Cancelled"],
		# Frappe's "is"/"not set" operator, not ["in", ["", None]] - a
		# plain IN/NOT IN list containing None triggers SQL's NULL
		# three-valued-logic trap ("x IN (a, NULL)" never matches rows
		# where x IS NULL, since "x = NULL" is never true - you need
		# "IS NULL" specifically), so it silently matched nothing.
		"checked_in_at": ["is", "not set"],
	}
	if patient:
		filters["patient"] = patient

	return frappe.get_all(
		"Patient Appointment",
		filters=filters,
		fields=["name", "patient", "patient_name", "practitioner", "practitioner_name", "appointment_time"],
		order_by="appointment_time asc",
	)


# =============================================
# CHECK-IN (stamps queue_status / checked_in_at /
# consultation_invoice directly on Patient
# Appointment - that's what carries the queue
# from here on. The Patient Encounter isn't
# created until a practitioner clicks Start
# Consultation - see start_consultation() below.)
# =============================================

def _patient_and_practitioner_names(patient, practitioner):
	"""Resolve display names explicitly rather than relying on Frappe's
	automatic fetch-from mechanism, which isn't reliably populating
	patient_name/practitioner_name when a doc is built from a plain dict
	and inserted via the API (as opposed to being saved through the desk
	form, where fetch-from is triggered on change)."""
	return (
		frappe.db.get_value("Patient", patient, "patient_name"),
		frappe.db.get_value("Healthcare Practitioner", practitioner, "practitioner_name"),
	)


@frappe.whitelist()
def get_consultation_fee(appointment=None, practitioner=None, appointment_type=None, department=None):
	_require_tab_access("checkin")
	"""Look up the billable rate the same way the native make_encounter()/
	invoice flow prices it (practitioner's OP Consulting Charge, falling
	back to the appointment type's default), so front desk doesn't have
	to guess/re-key it.

	Pass `appointment` for an already-booked appointment being checked
	in. For a walk-in still being drafted on the Check-In form - before
	any Patient Appointment exists to look one up - pass whatever subset
	of practitioner/appointment_type/department has been picked so far
	instead.

	Fails soft (0) rather than raising: this is a convenience auto-fill,
	not a hard billing gate, and the walk-in form calls this on every
	field change, so a still-incomplete selection (e.g. practitioner
	picked but not yet appointment type) shouldn't pop a blocking
	"missing configuration" dialog at staff mid-selection. Front desk can
	always key the fee in by hand regardless."""

	if appointment:
		doc = frappe.get_doc("Patient Appointment", appointment)
		appointment_type = doc.appointment_type
		department = doc.department
	else:
		doc = frappe._dict({
			"doctype": "Patient Appointment",
			"practitioner": practitioner,
			"appointment_type": appointment_type,
			"department": department,
			"service_unit": None,
			"inpatient_record": None,
		})

	# Practitioner's own charge takes priority when there is one - same
	# order native billing resolves in.
	billing_detail = _get_billing_detail_or_none(doc)
	if billing_detail and billing_detail.get("practitioner_charge"):
		return {"consultation_fee": billing_detail.get("practitioner_charge")}

	# get_appointment_billing_item_and_rate() (via
	# get_appointment_type_billing_details() in healthcare/utils.py)
	# skips the Appointment Type's own Billing table entirely whenever
	# no department/service unit is set - which is exactly the state a
	# walk-in starts in before staff pick a department. Read Appointment
	# Type's own get_billing_details() directly instead: it already
	# knows how to match a department-specific row (e.g. "walk-in" +
	# "General") and, if none matches, fall back to a department-less
	# generic row - so a plain "walk-in -> ₵135" setup works whether or
	# not a department has been chosen yet.
	if appointment_type:
		row = get_appointment_type_billing_row(appointment_type, department)
		if row and row.get("op_consulting_charge"):
			return {"consultation_fee": row.get("op_consulting_charge")}

	return {"consultation_fee": 0}


@frappe.whitelist()
def check_in_appointment(appointment, consultation_fee=0):
	_require_tab_access("checkin")
	"""Patient with a booked appointment has physically arrived."""

	appt = frappe.get_doc("Patient Appointment", appointment)

	_ensure_patient_enabled(appt.patient)

	# Idempotency: already checked in? hand back the current state rather
	# than re-charging / re-stamping it.
	if appt.checked_in_at:
		return {
			"status": "Success",
			"appointment": appt.name,
			"invoice": appt.consultation_invoice,
			"queue_status": appt.queue_status,
		}

	return _check_in(appt, consultation_fee)


@frappe.whitelist()
def create_walkin_checkin(patient, practitioner, appointment_type, department=None, consultation_fee=0):
	_require_tab_access("checkin")
	"""Walk-in patient with no prior booking. Creates today's Patient
	Appointment on the spot (same shape create_consultation() books ahead
	of time), then checks it straight in - see check_in_appointment()
	above for what that means. No Patient Encounter is created yet."""

	_ensure_patient_enabled(patient)

	duration = int(_resolve_duration(appointment_type))
	appointment_datetime = f"{nowdate()} {nowtime()}"
	appointment_end_datetime = add_to_date(appointment_datetime, minutes=duration)

	appt = frappe.get_doc({
		"doctype": "Patient Appointment",
		"patient": patient,
		"practitioner": practitioner,
		"department": department,
		"appointment_type": appointment_type,
		"appointment_date": nowdate(),
		"appointment_time": nowtime(),
		"appointment_datetime": appointment_datetime,
		"appointment_end_datetime": appointment_end_datetime,
		"duration": duration,
		"status": "Open",
		# A walk-in arrives whenever they arrive - it's not a real booked
		# slot, so it has no business colliding with the practitioner's
		# actual schedule. patient_appointment.py's validate_overlaps()
		# only runs its broad practitioner/patient time-range overlap
		# check when this is falsy; when true it instead only guards
		# against the same patient double-booking the exact same
		# date/time/appointment_for, which is what a walk-in actually
		# needs. Native Healthcare already uses this exact flag for its
		# own "book on check-in" flow (see validate_based_on_appointments_for()
		# a few lines below in the same file) - without it, any walk-in
		# whose arrival time happens to fall inside another one of the
		# practitioner's scheduled appointments gets rejected with
		# "Not allowed, cannot overlap appointment ...".
		"appointment_based_on_check_in": 1,
	})
	appt.insert(ignore_permissions=True)

	return _check_in(appt, consultation_fee)


def _check_in(appt, consultation_fee):
	"""Common tail for both check_in_appointment() and
	create_walkin_checkin(): stamp checked_in_at and hand off to
	_finalize_checkin() for the payment-status / invoice part."""
	appt.db_set("checked_in_at", now_datetime())
	return _finalize_checkin(appt, appt.patient, consultation_fee)


def _finalize_checkin(appt, patient, consultation_fee):

	invoice_name = None
	covered_by_free_followup = False

	if float(consultation_fee or 0) > 0:
		invoice_name, covered_by_free_followup = _invoice_consultation(appt, consultation_fee)

	if invoice_name:
		appt.db_set("queue_status", "Payment Pending")
		_notify("queue_update", {
			"department": "cashier",
			"message": f"New invoice pending: {invoice_name}",
			"encounter": None,
		})
	else:
		appt.db_set("queue_status", "Paid - Awaiting Vitals")
		# No invoice means no "cashier" notify above - fire one here too
		# so an already-open Queue tab still picks this arrival up live,
		# same as the paid path does, instead of only showing up on the
		# next manual tab switch/refresh.
		_notify("queue_update", {
			"department": "queue",
			"message": (
				f"{appt.name} checked in - free follow-up"
				if covered_by_free_followup
				else f"{appt.name} checked in - no fee due"
			),
			"encounter": None,
		})

	return {
		"status": "Success",
		"appointment": appt.name,
		"invoice": invoice_name,
		"queue_status": appt.queue_status,
	}


def _invoice_consultation(appt, consultation_fee):
	"""Raise the consultation Sales Invoice for a checked-in appointment,
	submitted but UNPAID (outstanding_amount == grand_total) - the
	Cashier Portal is responsible for actually receiving payment against
	it, same as Pharmacy/Lab/Rehab invoices - or skip invoicing entirely
	when an active Fee Validity window (Healthcare Settings' "Enable
	Free Follow-ups") already covers this visit for free.

	Reuses native Healthcare's own invoicing/free-follow-up machinery
	(patient_appointment.py's create_sales_invoice()/update_fee_validity(),
	fee_validity.py's check_fee_validity()) rather than a second,
	parallel invoice-creation path that duplicated it (this used to
	build its own Sales Invoice by hand here).

	Deliberately does NOT go through native's own invoice_appointment()
	wrapper - that function's decision whether to invoice AT ALL is
	gated on Healthcare Settings' "Show Payment Prompt in Appointment"
	(show_payment_popup), which is about whether a payment dialog pops
	up on the standard desk form, not about whether Front Desk should
	charge for a consultation. Front Desk's own trigger for invoicing
	stays exactly what it's always been - whether `consultation_fee`
	(confirmed/editable by the operator at check-in) is greater than
	zero - independent of that setting, so leaving that dialog off
	elsewhere in the app can't silently stop Front Desk from billing.

	Returns (invoice_name, covered_by_free_followup) - invoice_name is
	None when a Fee Validity window covered this visit instead.
	"""

	from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
		create_sales_invoice,
		update_fee_validity,
	)
	from healthcare.healthcare.doctype.fee_validity.fee_validity import (
		check_fee_validity,
	)

	# Operator's confirmed/edited fee wins over whatever
	# Patient Appointment.set_payment_details() auto-suggested at
	# insert time (native's own after_insert(), when "Show Payment
	# Prompt in Appointment" is on) - create_sales_invoice()'s own
	# get_appointment_item() prefers appt.paid_amount over the billing
	# config's practitioner_charge whenever it's set.
	appt.db_set("paid_amount", consultation_fee)

	# create_sales_invoice() reads appointment_doc.company directly
	# (both for the invoice itself and for its receivable-account
	# lookup) - none of Front Desk's own appointment-creation code sets
	# it explicitly (see create_consultation()/create_walkin_checkin()
	# above), instead relying on Frappe's own insert-time default. The
	# previous hand-rolled invoice here never trusted that either -  it
	# always fetched the global default company independently - so
	# match that same guarantee rather than assume it landed here.
	if not appt.company:
		appt.db_set("company", frappe.defaults.get_global_default("company"))

	fee_validity = check_fee_validity(appt)
	if fee_validity and fee_validity.status != "Active":
		fee_validity = None

	if fee_validity:
		# Already covered - record/advance the visit against the
		# existing window (increments `visited`, links this
		# appointment into ref_appointments) instead of invoicing.
		update_fee_validity(appt)
		return None, True

	# create_sales_invoice() ends with its own alert-style msgprint
	# ("Sales Invoice X created") - trimmed the same way
	# _get_billing_detail_or_none() above trims a frappe.throw(), since
	# Front Desk already raises its own "Checked in" toast for this and
	# a second one would just be confusing/duplicated.
	log_len = len(frappe.local.message_log)
	create_sales_invoice(appt)
	del frappe.local.message_log[log_len:]

	# create_sales_invoice() writes invoiced/ref_sales_invoice/paid_amount
	# straight to the database (frappe.db.set_value(), not appt.db_set()),
	# so they never land on this in-memory `appt` object - read the
	# invoice name back rather than trusting appt.ref_sales_invoice.
	invoice_name = frappe.db.get_value("Patient Appointment", appt.name, "ref_sales_invoice")

	# create_sales_invoice() tags neither Front Desk's own
	# `consultation_invoice` field (which the rest of this file - the
	# queue, on_payment_entry_submit() below - reads) nor Cashier
	# Portal's `custom_department` bucketing field (setup.py). It hands
	# back an already-submitted invoice, so custom_department needs a
	# direct db write rather than a normal save (submitted docs reject
	# plain field edits).
	appt.db_set("consultation_invoice", invoice_name)
	frappe.db.set_value("Sales Invoice", invoice_name, "custom_department", "Consultation")

	# First paid visit for this patient/practitioner combo establishes a
	# fresh free-follow-up window (when the feature's enabled), so a
	# later visit within it hits the fee_validity branch above instead
	# of being charged again.
	update_fee_validity(appt)

	return invoice_name, False

def on_payment_entry_submit(doc, method=None):
	"""Doc event hook (wire up in hooks.py against Payment Entry's
	on_submit) — once a Payment Entry is submitted against a
	consultation invoice we created, check if that invoice is now
	fully paid and, if so, advance the linked appointment from
	Payment Pending to Paid - Awaiting Vitals.

	Hooking here instead of Sales Invoice's on_update: ERPNext updates
	the referenced invoice's outstanding_amount as part of Payment
	Entry submission, but not always via a full doc.save() that would
	re-fire Sales Invoice's own doc events - so on_update on Sales
	Invoice is not a reliable place to catch this. Payment Entry
	submission itself always fires exactly once per payment.
	"""

	if doc.payment_type != "Receive":
		return

	for ref in doc.references:
		if ref.reference_doctype != "Sales Invoice":
			continue

		outstanding = frappe.db.get_value("Sales Invoice", ref.reference_name, "outstanding_amount")
		if outstanding != 0:
			continue

		_advance_consultation_appointment(ref.reference_name)
		_enable_patient_after_registration_payment(ref.reference_name)


def _advance_consultation_appointment(invoice_name):
	appointment_name = frappe.db.get_value(
		"Patient Appointment",
		{"consultation_invoice": invoice_name, "queue_status": "Payment Pending"},
		"name",
	)
	if not appointment_name:
		return

	frappe.db.set_value("Patient Appointment", appointment_name, "queue_status", "Paid - Awaiting Vitals")
	patient_name = frappe.db.get_value("Patient Appointment", appointment_name, "patient_name")
	_notify("queue_update", {
		"department": "nurse",
		"message": f"{patient_name} paid — ready for vitals",
		"encounter": None,
	})


def _enable_patient_after_registration_payment(invoice_name):
	"""Registration-fee invoices carry a Sales Invoice Item whose
	reference_dt/reference_dn point back at the Patient (see
	make_invoice() / Patient.invoice_patient_registration() in
	healthcare/patient.py) - that's how we recognise one here, as
	opposed to a consultation, pharmacy, or lab invoice. Once such an
	invoice is fully paid, flip that patient from Disabled back to
	Active so the front desk can check them in.
	"""

	patient_name = frappe.db.get_value(
		"Sales Invoice Item",
		{"parent": invoice_name, "reference_dt": "Patient"},
		"reference_dn",
	)
	if not patient_name:
		return

	if frappe.db.get_value("Patient", patient_name, "status") != "Disabled":
		return

	frappe.db.set_value("Patient", patient_name, "status", "Active")
	_notify("queue_update", {
		"department": "front-desk",
		"message": f"Registration fee paid — {patient_name} is now enabled for check-in",
		"encounter": None,
	})

	# Registration is only genuinely complete once the fee actually owed
	# is paid, not merely invoiced - see _send_registration_email()'s
	# docstring for the other half of this (patients who owe no fee at all).
	_send_registration_email(frappe.get_doc("Patient", patient_name))


def _send_registration_email(patient_doc):
	"""Email confirming a completed registration, sent from two places
	depending on whether this patient owes a registration fee:

	- confirm_patient_registration(), immediately, for a patient who
	  owes no fee at all (nothing further to wait for).
	- _enable_patient_after_registration_payment() above, once a fee
	  that WAS owed has actually been paid in full - not merely invoiced.

	Native Healthcare's "Out Patient SMS Alerts" (Healthcare Settings)
	only ever sends SMS, and does so itself at its own (earlier) timing -
	Patient.after_insert() on raw insert when no fee is collected, or
	Patient.invoice_patient_registration() the moment the invoice is
	raised when one is (see healthcare/doctype/patient/patient.py,
	intentionally left untouched). There's no built-in email equivalent,
	so this fills that gap, correctly timed to when registration is
	actually done - reusing the exact same "Patient Registration" toggle
	and Registration Message template that SMS uses, so one message is
	maintained in one place for both channels, even though they now fire
	at different points in the flow.

	Only fires once both an email and mobile number are on file - Front
	Desk's New Patient form makes both required, but this is a second,
	server-side check in case this patient predates that (or was
	created some other way).
	"""

	if not patient_doc.email or not patient_doc.mobile:
		return

	if not frappe.db.get_single_value("Healthcare Settings", "send_registration_msg"):
		return

	message = frappe.db.get_single_value("Healthcare Settings", "registration_msg")
	if not message:
		return

	rendered = frappe.render_template(message, {"doc": patient_doc, "alert": patient_doc})

	frappe.sendmail(
		recipients=[patient_doc.email],
		subject=_("Registration Confirmation"),
		message=rendered,
	)


# =============================================
# QUEUE (reads Patient Appointment, filtered to
# checked_in_at being set — a not-yet-arrived
# appointment isn't in the front-desk queue yet)
# =============================================

@frappe.whitelist()
def get_queue(date=None, queue_status=None):

	tab_for_status = {
		"With Nurse": "nurse",
		"With Lab": "lab",
		"With Doctor": "doctor",
	}
	_require_tab_access(tab_for_status.get(queue_status, "queue"))

	date = date or nowdate()

	filters = {
		"appointment_date": date,
		# See get_pending_checkins() above for why this isn't
		# ["not in", ["", None]] - that form silently matches zero rows
		# ever, due to SQL's NULL three-valued-logic trap.
		"checked_in_at": ["is", "set"],
	}

	if queue_status:
		filters["queue_status"] = queue_status
	else:
		# The general Queue tab (no specific queue_status requested) shows
		# everyone still moving through the pipeline today - not anyone
		# who's already finished with the doctor.
		filters["queue_status"] = ["!=", "Completed"]

	rows = frappe.get_all(
		"Patient Appointment",

		filters=filters,

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

			"consultation_invoice",

			"checked_in_at",
		],

		order_by="appointment_time asc",
	)

	# front_desk.js reads these under their original (Patient
	# Encounter-era) key names - alias here rather than touch every
	# render/lookup call site on the front-end.
	for row in rows:
		row["medical_department"] = row.pop("department")
		row["encounter_time"] = row.pop("appointment_time")

	# Vitals live on the standard "Vital Signs" doctype (one submitted doc
	# per nurse-station recording). It's linked back via its `appointment`
	# field now, not `encounter` - the Encounter doesn't exist yet at the
	# point vitals get recorded; see save_vitals() below and
	# start_consultation() for where the Encounter finally gets created.
	# Pull the latest submitted Vital Signs per appointment and fold it
	# into each row under the same vitals_* keys the front-end reads.
	appointment_ids = [row["name"] for row in rows]
	if appointment_ids:
		vitals = frappe.get_all(
			"Vital Signs",
			filters={"appointment": ["in", appointment_ids], "docstatus": 1},
			fields=[
				"appointment",
				"temperature",
				"bp",
				"pulse",
				"bmi",
				"custom_spo2",
				"custom_fbs",
				"custom_rbs",
				"vital_signs_note",
			],
			order_by="creation desc",
		)
		# order_by desc + first-write-wins gives the latest Vital Signs per
		# appointment (an appointment can in principle have more than one,
		# e.g. a re-check).
		latest_vitals_by_appointment = {}
		for v in vitals:
			latest_vitals_by_appointment.setdefault(v["appointment"], v)

		for row in rows:
			v = latest_vitals_by_appointment.get(row["name"])
			row["vitals_temperature"] = v["temperature"] if v else None
			row["vitals_blood_pressure"] = v["bp"] if v else None
			row["vitals_pulse"] = v["pulse"] if v else None
			row["vitals_bmi"] = v["bmi"] if v else None
			row["vitals_spo2"] = v["custom_spo2"] if v else None
			row["vitals_fbs"] = v["custom_fbs"] if v else None
			row["vitals_rbs"] = v["custom_rbs"] if v else None
			row["vitals_notes"] = v["vital_signs_note"] if v else None

	# patient_name stored on the Appointment can be stale/incomplete (e.g.
	# just a first name) depending on what was on the Patient record at
	# booking time. Always resolve the full display name fresh from
	# the Patient doctype (first_name + last_name) rather than trusting
	# whatever got cached on the Appointment.
	patient_ids = list({row["patient"] for row in rows if row.get("patient")})
	if patient_ids:
		patients = frappe.get_all(
			"Patient",
			filters={"name": ["in", patient_ids]},
			fields=["name", "first_name", "last_name"],
		)

		def _resolve_full_name(p):
			first = (p.get("first_name") or "").strip()
			last = (p.get("last_name") or "").strip()
			if last:
				return f"{first} {last}".strip()
			# last_name was never filled in at registration (the whole
			# name was typed into First Name instead) - the Patient ID
			# itself is built from what was typed, so it's the only
			# place the full name actually survived. Fall back to it,
			# collapsing any accidental double spaces from that.
			return " ".join(p["name"].split()) or first

		full_name_map = {p["name"]: _resolve_full_name(p) for p in patients}

		for row in rows:
			if row.get("patient") in full_name_map:
				row["patient_name"] = full_name_map[row["patient"]] or row["patient_name"]

	return rows


# =============================================
# NURSE STATION
# =============================================

@frappe.whitelist()
def send_to_nurse(appointment):
	_require_tab_access("queue")
	frappe.db.set_value("Patient Appointment", appointment, "queue_status", "With Nurse")
	patient_name = frappe.db.get_value("Patient Appointment", appointment, "patient_name")
	_notify("queue_update", {
		"department": "nurse",
		"message": f"{patient_name} sent to nurse station",
		"encounter": None,
	})
	return {"status": "Success"}


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
	_require_tab_access("nurse")

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
		# start_consultation() below, which backfills this Vital Signs
		# doc's `encounter` field once that happens.
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


# =============================================
# DOCTOR QUEUE
# =============================================

@frappe.whitelist()
def start_consultation(appointment):
	_require_tab_access("doctor")
	"""Practitioner is ready to see this patient - this is where the
	Patient Encounter actually gets created (not at check-in), pre-filled
	from the appointment. Queue tracking keeps living on the Patient
	Appointment right through to Completed - see on_patient_encounter_submit()
	below."""

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


def on_patient_encounter_submit(doc, method=None):
	"""Doctor completes + submits the Encounter -> the linked Patient
	Appointment's queue_status becomes Completed. Queue state lives on
	the Appointment for the whole visit now, not on the Encounter - see
	start_consultation() above for where the Encounter gets created."""

	if doc.appointment:
		frappe.db.set_value("Patient Appointment", doc.appointment, "queue_status", "Completed")
