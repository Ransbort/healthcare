import frappe
from frappe import _
from frappe.utils import now_datetime, nowdate, nowtime, add_to_date


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

# =============================================
# NOTIFICATION HELPER
# =============================================

def _notify(event, payload):
	"""Broadcast a realtime event to everyone listening in this site.
	Used to trigger department-specific sound/toast notifications on
	the front-end the instant a queue status changes, without needing
	to poll."""
	frappe.publish_realtime(event=event, message=payload)

# =============================================
# BULK SEND TO NURSE
# =============================================

@frappe.whitelist()
def bulk_send_to_nurse(encounters):
	"""Send every currently 'Paid - Awaiting Vitals' encounter in the
	given list to the nurse queue in one action. Re-checks queue_status
	server-side rather than trusting the front-end's snapshot, in case
	something changed between page load and this click."""
	import json
	if isinstance(encounters, str):
		encounters = json.loads(encounters)

	if not encounters:
		return {"status": "Success", "updated": []}

	eligible = frappe.get_all(
		"Patient Encounter",
		filters={
			"name": ["in", encounters],
			"queue_status": "Paid - Awaiting Vitals",
			"docstatus": 0,
		},
		pluck="name",
	)

	for name in eligible:
		frappe.db.set_value("Patient Encounter", name, "queue_status", "With Nurse")

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
	"""Patient.validate() (see healthcare/healthcare/doctype/patient/patient.py
	in the core Healthcare app) auto-creates and links a Customer as part
	of patient.insert() itself, whenever Healthcare Settings has "Link
	Customer to Patient" enabled - before any of our code below even
	runs. We don't want that Customer to exist until the operator has
	actually confirmed the registration in the popup, so immediately
	undo it here: delete the just-created Customer and clear the link.
	It's re-created in _create_customer_for_patient() once
	confirm_patient_registration() runs - nothing else can have
	referenced this Customer yet since the Patient itself was only
	just inserted.
	"""

	customer_name = patient_doc.customer
	if not customer_name:
		return

	patient_doc.db_set("customer", None, update_modified=False)

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
def create_walkin_patient(first_name, last_name=None, mobile=None, gender=None, dob=None, uid=None):
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

	patient = frappe.get_doc({
		"doctype": "Patient",
		"first_name": first_name,
		"last_name": last_name,
		"mobile": mobile,
		"sex": gender,
		"dob": dob,
		"uid": _resolve_patient_uid(uid),
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
		"patient_status": frappe.db.get_value("Patient", patient.name, "status"),
		"fee_will_be_charged": collect_fee,
		"registration_fee": registration_fee,
	}


@frappe.whitelist()
def confirm_patient_registration(patient):
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

	return {
		"status": "Success",
		"patient": patient_doc.name,
		"patient_name": patient_doc.patient_name,
		"registration_invoice": registration_invoice,
		"patient_status": frappe.db.get_value("Patient", patient_doc.name, "status"),
	}


@frappe.whitelist()
def cancel_patient_registration(patient):
	"""Operator caught a mistake in the confirmation popup and backed
	out instead of confirming. Safe to hard-delete here because this
	only ever runs before confirm_patient_registration() has had a
	chance to create a Customer or raise any invoice against the
	patient - nothing else links to the record yet."""

	if frappe.db.exists("Sales Invoice Item", {"reference_dt": "Patient", "reference_dn": patient}):
		frappe.throw(_("This patient already has an invoice raised and can no longer be discarded."))

	frappe.delete_doc("Patient", patient, ignore_permissions=True)

	return {"status": "Success"}


def _raise_registration_invoice(patient):
	"""Create (or reuse) the registration-fee Sales Invoice for `patient`
	and make sure it's submitted so it actually shows up as payable at
	the Cashier Portal.

	Patient.invoice_patient_registration() already does the fee/item
	lookup and de-dupes against an existing draft invoice for this
	patient, but it leaves the invoice in draft (docstatus=0) - submit
	it here ourselves, same as _create_consultation_invoice() does for
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
	"""Booked appointments for `date` that have not yet been checked in
	(i.e. no Patient Encounter has been created against them yet)."""

	date = date or nowdate()

	filters = {
		"appointment_date": date,
		"status": ["!=", "Cancelled"],
	}
	if patient:
		filters["patient"] = patient

	appointments = frappe.get_all(
		"Patient Appointment",
		filters=filters,
		fields=["name", "patient", "patient_name", "practitioner", "practitioner_name", "appointment_time"],
		order_by="appointment_time asc",
	)

	if not appointments:
		return []

	already_checked_in = set(frappe.get_all(
		"Patient Encounter",
		filters={"appointment": ["in", [a.name for a in appointments]]},
		pluck="appointment",
	))

	return [a for a in appointments if a.name not in already_checked_in]


# =============================================
# CHECK-IN (creates the draft Patient Encounter
# that carries the queue from here on)
# =============================================

def _patient_and_practitioner_names(patient, practitioner):
	"""Resolve display names explicitly rather than relying on Frappe's
	automatic fetch-from mechanism, which isn't reliably populating
	patient_name/practitioner_name when the Encounter is built from a
	plain dict and inserted via the API (as opposed to being saved
	through the desk form, where fetch-from is triggered on change)."""
	return (
		frappe.db.get_value("Patient", patient, "patient_name"),
		frappe.db.get_value("Healthcare Practitioner", practitioner, "practitioner_name"),
	)


@frappe.whitelist()
def check_in_appointment(appointment, consultation_fee=0):
	"""Patient with a booked appointment has physically arrived.

	Creates the draft Patient Encounter (docstatus=0) that now owns
	queue_status / checked_in_at / vitals_* / consultation_invoice.
	The Patient Appointment record itself is left untouched (it stays
	a plain schedule record) apart from being linked via `appointment`.
	"""

	appt = frappe.get_doc("Patient Appointment", appointment)

	_ensure_patient_enabled(appt.patient)

	# Idempotency: if this appointment was already checked in, don't
	# spin up a second Encounter — just hand back the existing one.
	existing = frappe.db.get_value("Patient Encounter", {"appointment": appt.name}, "name")
	if existing:
		return {
			"status": "Success",
			"encounter": existing,
			"invoice": frappe.db.get_value("Patient Encounter", existing, "consultation_invoice"),
			"queue_status": frappe.db.get_value("Patient Encounter", existing, "queue_status"),
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
		# front-desk user to re-enter something already captured.
		"appointment_type": appt.appointment_type,
		"appointment": appt.name,
		"encounter_date": nowdate(),
		"encounter_time": nowtime(),
		"queue_status": "Registered",
		"checked_in_at": now_datetime(),
	})
	encounter.insert(ignore_permissions=True)

	return _finalize_checkin(encounter, appt.patient, consultation_fee)


@frappe.whitelist()
def create_walkin_encounter(patient, practitioner, appointment_type, department=None, consultation_fee=0):
	"""Walk-in patient with no prior booking. Skips Patient Appointment
	entirely and creates the draft Patient Encounter directly.

	appointment_type is required because Patient Encounter itself has it
	as a mandatory field with no Patient Appointment to inherit it from.
	"""

	_ensure_patient_enabled(patient)

	patient_name, practitioner_name = _patient_and_practitioner_names(patient, practitioner)

	encounter = frappe.get_doc({
		"doctype": "Patient Encounter",
		"patient": patient,
		"patient_name": patient_name,
		"practitioner": practitioner,
		"practitioner_name": practitioner_name,
		"medical_department": department,
		"appointment_type": appointment_type,
		"encounter_date": nowdate(),
		"encounter_time": nowtime(),
		"queue_status": "Registered",
		"checked_in_at": now_datetime(),
	})
	encounter.insert(ignore_permissions=True)

	return _finalize_checkin(encounter, patient, consultation_fee)


def _finalize_checkin(encounter, patient, consultation_fee):

	invoice_name = None

	if float(consultation_fee or 0) > 0:
		invoice_name = _create_consultation_invoice(patient, consultation_fee, encounter.name)
		encounter.db_set("consultation_invoice", invoice_name)
		encounter.db_set("queue_status", "Payment Pending")
		_notify("queue_update", {
			"department": "cashier",
			"message": f"New invoice pending: {invoice_name}",
			"encounter": encounter.name,
		})
	else:
		encounter.db_set("queue_status", "Paid - Awaiting Vitals")

	return {
		"status": "Success",
		"encounter": encounter.name,
		"invoice": invoice_name,
		"queue_status": encounter.queue_status,
	}


def _create_consultation_invoice(patient, amount, encounter_name):
	"""Create the consultation Sales Invoice, submitted but UNPAID —
	outstanding_amount == grand_total. The Cashier Portal is responsible
	for actually receiving payment against this invoice (via whatever
	mechanism cashier_portal.py already uses for Pharmacy/Lab/Rehab
	invoices — Payment Entry, or its own accept/confirm method).

	custom_department = "Consultation" tags this invoice the same way
	Pharmacy/Spa invoices are tagged (see setup.py's get_custom_fields()),
	so it can be bucketed into its own tab on the Cashier Portal instead
	of falling into "Other" unlabelled.
	"""

	patient_doc = frappe.get_doc("Patient", patient)
	customer = patient_doc.customer or patient_doc.name

	default_company = frappe.defaults.get_global_default("company")

	invoice = frappe.get_doc({
		"doctype": "Sales Invoice",

		"customer": customer,
		"patient": patient,
		"company": default_company,
		"posting_date": nowdate(),
		"due_date": nowdate(),

		"items": [{
			"item_code": "Consultation",
			"qty": 1,
			"rate": float(amount),
		}],

		"remarks": f"Consultation fee for Patient Encounter {encounter_name}",
	})

	invoice.insert(ignore_permissions=True)
	invoice.submit()

	return invoice.name

def on_payment_entry_submit(doc, method=None):
	"""Doc event hook (wire up in hooks.py against Payment Entry's
	on_submit) — once a Payment Entry is submitted against a
	consultation invoice we created, check if that invoice is now
	fully paid and, if so, advance the linked encounter from
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

		_advance_consultation_encounter(ref.reference_name)
		_enable_patient_after_registration_payment(ref.reference_name)


def _advance_consultation_encounter(invoice_name):
	encounter_name = frappe.db.get_value(
		"Patient Encounter",
		{"consultation_invoice": invoice_name, "queue_status": "Payment Pending"},
		"name",
	)
	if not encounter_name:
		return

	frappe.db.set_value("Patient Encounter", encounter_name, "queue_status", "Paid - Awaiting Vitals")
	patient_name = frappe.db.get_value("Patient Encounter", encounter_name, "patient_name")
	_notify("queue_update", {
		"department": "nurse",
		"message": f"{patient_name} paid — ready for vitals",
		"encounter": encounter_name,
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

# =============================================
# QUEUE (reads Patient Encounter, filtered to
# docstatus=0 — a submitted Encounter has
# already left the front-desk queue)
# =============================================

@frappe.whitelist()
def get_queue(date=None, queue_status=None):

	date = date or nowdate()

	filters = {
		"encounter_date": date,
		"docstatus": 0,
	}

	if queue_status:
		filters["queue_status"] = queue_status

	rows = frappe.get_all(
		"Patient Encounter",

		filters=filters,

		fields=[
			"name",
			"patient",
			"patient_name",

			"practitioner",
			"practitioner_name",

			"medical_department",

			"appointment",

			"encounter_time",

			"queue_status",

			"consultation_invoice",

			"checked_in_at",

			"vitals_temperature",
			"vitals_blood_pressure",
			"vitals_pulse",
			"vitals_weight",
			"vitals_height",
			"vitals_notes",
		],

		order_by="encounter_time asc",
	)

	# patient_name stored on the Encounter can be stale/incomplete (e.g.
	# just a first name) depending on what was on the Patient record at
	# check-in time. Always resolve the full display name fresh from
	# the Patient doctype (first_name + last_name) rather than trusting
	# whatever got cached on the Encounter.
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
def send_to_nurse(encounter):
	frappe.db.set_value("Patient Encounter", encounter, "queue_status", "With Nurse")
	patient_name = frappe.db.get_value("Patient Encounter", encounter, "patient_name")
	_notify("queue_update", {
		"department": "nurse",
		"message": f"{patient_name} sent to nurse station",
		"encounter": encounter,
	})
	return {"status": "Success"}


@frappe.whitelist()
def save_vitals(
	encounter,
	temperature=None,
	blood_pressure=None,
	pulse=None,
	weight=None,
	height=None,
	notes=None
):

	doc_updates = {
		"vitals_temperature": temperature,
		"vitals_blood_pressure": blood_pressure,
		"vitals_pulse": pulse,
		"vitals_weight": weight,
		"vitals_height": height,
		"vitals_notes": notes,

		"vitals_recorded_by": frappe.session.user,
		"vitals_recorded_on": now_datetime(),

		"queue_status": "With Doctor",
	}

	for field, value in doc_updates.items():
		frappe.db.set_value("Patient Encounter", encounter, field, value)

	patient_name = frappe.db.get_value("Patient Encounter", encounter, "patient_name")
	_notify("queue_update", {
		"department": "doctor",
		"message": f"{patient_name} ready for consultation",
		"encounter": encounter,
	})

	return {"status": "Success"}


# =============================================
# DOCTOR QUEUE
# =============================================

@frappe.whitelist()
def start_consultation(encounter):
	"""The Encounter already exists (created at check-in) — this just
	flips it into 'In Consultation' so the doctor can open and complete
	the same draft document."""

	enc = frappe.get_doc("Patient Encounter", encounter)

	frappe.db.set_value("Patient Encounter", encounter, "queue_status", "In Consultation")

	return {
		"status": "Success",
		"patient": enc.patient,
		"practitioner": enc.practitioner,
		"encounter": enc.name,
	}


def on_patient_encounter_submit(doc, method=None):
	"""Doctor completes + submits the Encounter -> queue_status = Completed.
	No more lookup into Patient Appointment: the queue state lives on
	this document itself now."""

	doc.db_set("queue_status", "Completed")