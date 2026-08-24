# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

NURSE_ROLE = "Nursing User"


class AdmissionOrder(Document):
	def on_cancel(self):
		if self.status == "Accepted":
			frappe.throw(
				_(
					"Cannot cancel an Admission Order that has already been accepted. "
					"Cancel the linked Inpatient Record instead."
				)
			)
		self.db_set("status", "Cancelled")
		_clear_pending_admission_order(self.admission_encounter, self.name)

	def on_submit(self):
		notify_nursing_team(self)


def _clear_pending_admission_order(encounter, admission_order):
	"""Clear Patient Encounter.custom_pending_admission_order if it still
	points at `admission_order` (it may already have moved on to a newer
	order in edge cases, so this only clears a match)."""
	if not encounter:
		return
	current = frappe.db.get_value("Patient Encounter", encounter, "custom_pending_admission_order")
	if current == admission_order:
		frappe.db.set_value("Patient Encounter", encounter, "custom_pending_admission_order", None)


def _notify(event, payload):
	"""Broadcast a realtime event to everyone listening in this site - same
	private-copy pattern lab_portal.py/rehab_portal.py/front_desk.py/
	nurse_station.py each keep for their own sound/toast notifications,
	rather than a shared import."""
	frappe.publish_realtime(event=event, message=payload)


def _resolve_practitioner_user(practitioner):
	"""Best-effort: the Frappe User login linked to a Healthcare
	Practitioner, so an accept/reject outcome can reach the actual doctor
	who placed the order - not just sit as a comment on the Admission
	Order document they'd have to go looking for.

	Looked up defensively via frappe.get_meta() rather than assuming a
	hard-coded fieldname (e.g. "user_id") - Healthcare Practitioner is
	core Healthcare code, this app's own source tree has no local copy of
	its doctype JSON to check against directly. Returns the first
	Link-to-User field found, or None if the practitioner isn't set, the
	field can't be found, or it isn't linked to an enabled user."""
	if not practitioner:
		return None

	try:
		meta = frappe.get_meta("Healthcare Practitioner")
	except Exception:
		return None

	fieldname = None
	for df in meta.get("fields", []):
		if df.fieldtype == "Link" and df.options == "User":
			fieldname = df.fieldname
			break
	if not fieldname:
		return None

	user = frappe.db.get_value("Healthcare Practitioner", practitioner, fieldname)
	if user and user not in ("Administrator", "Guest") and frappe.db.get_value("User", user, "enabled"):
		return user
	return None


def _notify_referring_practitioner(doc, outcome, reason=None):
	"""Tell the doctor who placed this Admission Order that a nurse has
	accepted or rejected it - accept_admission_order()/reject_admission_order()
	below previously only left a comment on the document, which the
	ordering doctor would never see unless they happened to reopen it.

	Prefers referring_practitioner (whoever placed the order from the
	Patient Encounter) and falls back to primary_practitioner if that's
	blank. Silently does nothing if neither resolves to an enabled user -
	same "best-effort, never block the actual accept/reject" spirit as
	notify_nursing_team()'s own try/except below."""
	practitioner = doc.referring_practitioner or doc.primary_practitioner
	user = _resolve_practitioner_user(practitioner)
	if not user:
		return

	if outcome == "Accepted":
		message = _("Your admission order for {0} was accepted - the Inpatient Record has been created").format(
			doc.patient_name or doc.patient
		)
	else:
		message = _("Your admission order for {0} was rejected: {1}").format(
			doc.patient_name or doc.patient, reason or _("no reason given")
		)

	# Scoped to just this one user (unlike notify_nursing_team()'s
	# department-wide broadcast) - this is only relevant to the doctor who
	# placed the order, not every doctor in the department. Picked up by
	# doctor_station.js if they currently have that page open; either way
	# the Notification Log entry below still reaches them via the bell
	# icon.
	frappe.publish_realtime(
		event="admission_order_response",
		message={"message": message},
		user=user,
	)

	try:
		from frappe.desk.doctype.notification_log.notification_log import (
			enqueue_create_notification,
		)

		notification_doc = {
			"type": "Alert",
			"document_type": doc.doctype,
			"document_name": doc.name,
			"subject": message,
			"from_user": frappe.session.user,
		}
		enqueue_create_notification([user], notification_doc)
	except Exception:
		frappe.log_error(title="Failed to notify referring practitioner of Admission Order outcome")


def notify_nursing_team(doc):
	"""Send an in-app notification to every user with the Nursing User role,
	plus a realtime sound/toast at Nurse Station - same "department": "nurse"
	queue_update contract front_desk.py's send_to_nurse() already uses, so
	Nurse Station's existing realtime handler picks this up automatically
	(it also refreshes its own pending-admission-orders list on this event -
	see nurse_station.js). Fired unconditionally, independent of the
	Has Role lookup below, so a nurse with the page open live still gets the
	toast even on a site where no user happens to carry the Nursing User
	role yet."""
	_notify("queue_update", {
		"department": "nurse",
		"message": _("New admission order for {0} awaiting acceptance").format(
			doc.patient_name or doc.patient
		),
		"encounter": None,
	})

	nurses = frappe.get_all(
		"Has Role",
		filters={"role": NURSE_ROLE, "parenttype": "User"},
		pluck="parent",
	)
	nurses = [
		user
		for user in nurses
		if user not in ("Administrator", "Guest") and frappe.db.get_value("User", user, "enabled")
	]
	if not nurses:
		return

	try:
		from frappe.desk.doctype.notification_log.notification_log import (
			enqueue_create_notification,
		)

		notification_doc = {
			"type": "Alert",
			"document_type": doc.doctype,
			"document_name": doc.name,
			"subject": _("New admission order for {0} is awaiting your acceptance").format(
				doc.patient_name or doc.patient
			),
			"from_user": doc.owner,
		}
		enqueue_create_notification(nurses, notification_doc)
	except Exception:
		frappe.log_error(title="Failed to notify nursing team of Admission Order")


@frappe.whitelist()
def create_admission_order(admission_order):
	"""Create and submit an Admission Order from a Patient Encounter's 'Order Admission' dialog.

	This is wired in as a drop-in replacement for
	healthcare.healthcare.doctype.inpatient_record.inpatient_record.schedule_inpatient via
	hooks.py's override_whitelisted_methods - patient_encounter.js still calls the original
	method name and is not edited. The Inpatient Record is now only created once a Nursing
	User accepts the resulting order (see accept_admission_order below).
	"""
	if isinstance(admission_order, str):
		admission_order = json.loads(admission_order)

	if (
		not admission_order
		or not admission_order.get("patient")
		or not admission_order.get("admission_encounter")
	):
		frappe.throw(_("Missing required details, did not create Admission Order"))

	encounter = admission_order["admission_encounter"]

	existing = frappe.db.exists(
		"Admission Order",
		{
			"admission_encounter": encounter,
			"status": "Pending",
			"docstatus": 1,
		},
	)
	if existing:
		frappe.throw(_("An Admission Order for this encounter is already pending nurse acceptance"))

	doc = frappe.new_doc("Admission Order")
	doc.patient = admission_order.get("patient")
	doc.admission_encounter = encounter
	doc.referring_practitioner = admission_order.get("referring_practitioner")
	doc.company = admission_order.get("company")
	doc.medical_department = admission_order.get("medical_department")
	doc.primary_practitioner = admission_order.get("primary_practitioner")
	doc.secondary_practitioner = admission_order.get("secondary_practitioner")
	doc.admission_ordered_for = admission_order.get("admission_ordered_for")
	doc.admission_service_unit_type = admission_order.get("admission_service_unit_type")
	doc.treatment_plan_template = admission_order.get("treatment_plan_template")
	doc.expected_length_of_stay = admission_order.get("expected_length_of_stay")
	doc.admission_instruction = admission_order.get("admission_instruction")
	doc.admission_nursing_checklist_template = admission_order.get(
		"admission_nursing_checklist_template"
	)
	doc.status = "Pending"
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	doc.submit()

	# custom_pending_admission_order is a Custom Field added via
	# setup.py's get_custom_fields() - not a change to patient_encounter.json.
	frappe.db.set_value("Patient Encounter", encounter, "custom_pending_admission_order", doc.name)

	return doc.name


@frappe.whitelist()
def accept_admission_order(admission_order):
	"""Nurse accepts a pending Admission Order - this creates the Inpatient Record
	(or Treatment Counselling, if required by the Treatment Plan Template), using the
	same, unmodified inpatient_record.py functions the original direct flow used."""
	if NURSE_ROLE not in frappe.get_roles():
		frappe.throw(_("Only users with the Nursing User role can accept an Admission Order"))

	doc = frappe.get_doc("Admission Order", admission_order)
	if doc.docstatus != 1:
		frappe.throw(_("Admission Order must be submitted before it can be accepted"))
	if doc.status != "Pending":
		frappe.throw(_("This Admission Order has already been {0}").format(doc.status.lower()))

	from healthcare.healthcare.doctype.inpatient_record.inpatient_record import (
		create_inpatient_record,
		create_treatment_counselling,
	)

	order_details = {
		"patient": doc.patient,
		"admission_encounter": doc.admission_encounter,
		"referring_practitioner": doc.referring_practitioner,
		"company": doc.company,
		"medical_department": doc.medical_department,
		"primary_practitioner": doc.primary_practitioner,
		"secondary_practitioner": doc.secondary_practitioner,
		"admission_ordered_for": doc.admission_ordered_for,
		"admission_service_unit_type": doc.admission_service_unit_type,
		"treatment_plan_template": doc.treatment_plan_template,
		"expected_length_of_stay": doc.expected_length_of_stay,
		"admission_instruction": doc.admission_instruction,
		"admission_nursing_checklist_template": doc.admission_nursing_checklist_template,
	}

	# Same branching healthcare.healthcare.doctype.inpatient_record.inpatient_record
	# .schedule_inpatient() does - replicated here (rather than calling
	# schedule_inpatient itself) since that function doesn't return the name of
	# whatever it created, and it isn't edited to add a return value.
	inpatient_record_name = None
	if order_details.get("treatment_plan_template") and frappe.db.get_value(
		"Treatment Plan Template",
		order_details.get("treatment_plan_template"),
		"treatment_counselling_required_for_ip",
	):
		create_treatment_counselling(order_details)
	else:
		inpatient_record_name = create_inpatient_record(order_details)

	doc.db_set("status", "Accepted")
	if inpatient_record_name:
		doc.db_set("inpatient_record", inpatient_record_name)
		# custom_admission_order is a Custom Field added via setup.py's
		# get_custom_fields() - not a change to inpatient_record.json.
		frappe.db.set_value(
			"Inpatient Record", inpatient_record_name, "custom_admission_order", doc.name
		)

	_clear_pending_admission_order(doc.admission_encounter, doc.name)
	doc.add_comment("Info", _("Accepted by {0}").format(frappe.utils.get_fullname()))
	_notify_referring_practitioner(doc, "Accepted")
	return doc.name


@frappe.whitelist()
def reject_admission_order(admission_order, reason=None):
	if NURSE_ROLE not in frappe.get_roles():
		frappe.throw(_("Only users with the Nursing User role can reject an Admission Order"))

	doc = frappe.get_doc("Admission Order", admission_order)
	if doc.docstatus != 1:
		frappe.throw(_("Admission Order must be submitted before it can be rejected"))
	if doc.status != "Pending":
		frappe.throw(_("This Admission Order has already been {0}").format(doc.status.lower()))

	doc.db_set("status", "Rejected")
	doc.db_set("rejection_reason", reason)
	_clear_pending_admission_order(doc.admission_encounter, doc.name)
	doc.add_comment("Info", _("Rejected by {0}: {1}").format(frappe.utils.get_fullname(), reason or ""))
	_notify_referring_practitioner(doc, "Rejected", reason)
	return doc.name
