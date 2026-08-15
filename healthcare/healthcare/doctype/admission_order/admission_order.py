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


def notify_nursing_team(doc):
	"""Send an in-app notification to every user with the Nursing User role."""
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
	return doc.name
