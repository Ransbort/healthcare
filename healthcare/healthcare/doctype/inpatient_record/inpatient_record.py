# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json
from math import floor

import frappe
from frappe import _
from frappe.desk.reportview import get_match_cond
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import (
	flt,
	get_datetime,
	get_link_to_form,
	getdate,
	now,
	now_datetime,
	rounded,
	time_diff_in_hours,
	today,
)

from erpnext.stock.get_item_details import ItemDetailsCtx, get_item_details

from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import get_account
from healthcare.healthcare.doctype.nursing_task.nursing_task import NursingTask
from healthcare.healthcare.doctype.patient_insurance_coverage.patient_insurance_coverage import (
	make_insurance_coverage as generate_insurance_coverage,
)
from healthcare.healthcare.utils import (
	get_appointment_billing_item_and_rate,
	get_encounters_to_invoice,
	get_inpatient_services_to_invoice,
	get_service_requests_to_invoice,
	validate_nursing_tasks,
)


class InpatientRecord(Document):
	def after_insert(self):
		frappe.db.set_value("Patient", self.patient, "inpatient_record", self.name)
		frappe.db.set_value("Patient", self.patient, "inpatient_status", self.status)

		if self.admission_encounter:  # Update encounter
			frappe.db.set_value(
				"Patient Encounter",
				self.admission_encounter,
				{"inpatient_record": self.name, "inpatient_status": self.status},
			)

			filters = {"order_group": self.admission_encounter, "docstatus": 1}
			medication_requests = frappe.get_all("Medication Request", filters, ["name"])
			service_requests = frappe.get_all("Service Request", filters, ["name"])

			for service_request in service_requests:
				frappe.db.set_value(
					"Service Request",
					service_request.name,
					{"inpatient_record": self.name, "inpatient_status": self.status},
				)

			for medication_request in medication_requests:
				frappe.db.set_value(
					"Medication Request",
					medication_request.name,
					{"inpatient_record": self.name, "inpatient_status": self.status},
				)

		if self.admission_nursing_checklist_template:
			NursingTask.create_nursing_tasks_from_template(
				template=self.admission_nursing_checklist_template,
				doc=self,
			)

		insert_pending_service_request(self)

	def validate(self):
		self.validate_dates()
		self.validate_already_scheduled_or_admitted()
		if self.status in ["Discharged", "Cancelled"]:
			frappe.db.set_value("Patient", self.patient, {"inpatient_status": None, "inpatient_record": None})

		set_item_rate(self)
		set_total(self)

	def validate_dates(self):
		if (getdate(self.expected_discharge) < getdate(self.scheduled_date)) or (
			getdate(self.discharge_ordered_date) < getdate(self.scheduled_date)
		):
			frappe.throw(_("Expected and Discharge dates cannot be less than Admission Schedule date"))

		for entry in self.inpatient_occupancies:
			if (
				entry.check_in
				and entry.check_out
				and get_datetime(entry.check_in) > get_datetime(entry.check_out)
			):
				frappe.throw(
					_("Row #{0}: Check Out datetime cannot be less than Check In datetime").format(entry.idx)
				)

	def validate_already_scheduled_or_admitted(self):
		inpatient_record = frappe.qb.DocType("Inpatient Record")

		ip_record = (
			frappe.qb.from_(inpatient_record)
			.select(inpatient_record.name, inpatient_record.status)
			.where(inpatient_record.status.isin(["Admitted", "Admission Scheduled"]))
			.where(inpatient_record.name != self.name)
			.where(inpatient_record.patient == self.patient)
		).run(as_dict=True)

		if ip_record:
			msg = _(
				(f"Already {ip_record[0].status} Patient {self.patient} with Inpatient Record ")
				+ f""" <b><a href="/app/Form/Inpatient Record/{ip_record[0].name}">{ip_record[0].name}</a></b>"""
			)
			frappe.throw(msg)

	@frappe.whitelist()
	def admit(self, service_unit, check_in, expected_discharge=None, currency=None, price_list=None):
		admit_patient(self, service_unit, check_in, expected_discharge, currency, price_list)
		create_orders_from_treatment_counselling(self)

	@frappe.whitelist()
	def discharge(self):
		discharge_patient(self)

	@frappe.whitelist()
	def create_sales_invoice(self):
		return create_invoice_for_inpatient(self)

	@frappe.whitelist()
	def preview_sales_invoice(self):
		"""Read-only: what create_sales_invoice would bill right now, itemised,
		without creating anything - see preview_invoice_items() below."""
		return preview_invoice_items(self)

	@frappe.whitelist()
	def transfer(self, service_unit, check_in, leave_from=None, txred=0):
		if leave_from:
			patient_leave_service_unit(self, check_in, leave_from)
		if service_unit:
			transfer_patient(self, service_unit, check_in, txred)

	@frappe.whitelist()
	def add_service_unit_rent_to_billable_items(self):
		try:
			io = frappe.qb.DocType("Inpatient Occupancy")
			su = frappe.qb.DocType("Healthcare Service Unit")
			sut = frappe.qb.DocType("Healthcare Service Unit Type")

			query = (
				frappe.qb.from_(io)
				.left_join(su)
				.on(io.service_unit == su.name)
				.left_join(sut)
				.on(su.service_unit_type == sut.name)
				.select(
					io.check_in,
					io.check_out,
					io.left,
					io.parent,
					io.name,
					sut.item,
					sut.uom,
					sut.rate,
					sut.no_of_hours,
					sut.minimum_billable_qty,
				)
				.where(io.parent == self.name)
			)

			inpatient_details = query.run(as_dict=True)
			item_hours = {}

			# Calculate total hours for each item
			for record in inpatient_details:
				check_in = get_datetime(record["check_in"])
				check_out = get_datetime(record["check_out"]) if record["check_out"] else get_datetime()

				hours_diff = time_diff_in_hours(check_out, check_in)
				item = record.get("item")

				if item not in item_hours:
					record["total_hours"] = 0
					item_hours[item] = record

				item_hours[item]["total_hours"] += hours_diff

			ip_records = list(item_hours.values())

			price_list, price_list_currency = frappe.db.get_values(
				"Price List", {"selling": 1}, ["name", "currency"]
			)[0]

			for inpatient in ip_records:
				if not inpatient.get("item"):
					continue
				item_name, stock_uom = frappe.db.get_value(
					"Item", inpatient.get("item"), ["item_name", "stock_uom"]
				)
				item_row = frappe.db.get_value(
					"Inpatient Record Item",
					{"item_code": inpatient.get("item"), "parent": self.name},
					["name", "quantity", "invoiced"],
					order_by="idx DESC",
					as_dict=True,
				)

				if not self.price_list and not price_list:
					frappe.throw(
						_(
							"Selling Price List not found. Please configure a valid Price List in the document."
						)
					)
				ctx: ItemDetailsCtx = ItemDetailsCtx(
					{
						"doctype": "Sales Invoice",
						"item_code": inpatient.get("item"),
						"company": self.company,
						"customer": frappe.db.get_value("Patient", self.patient, "customer"),
						"selling_price_list": self.price_list or price_list,
						"price_list_currency": self.currency or price_list_currency,
						"currency": self.currency or price_list_currency,
						"plc_conversion_rate": 1.0,
						"conversion_rate": 1.0,
						"qty": 1,
					}
				)
				item_details = get_item_details(ctx)
				price_list_rate = item_details.get("price_list_rate")
				if price_list_rate is None or flt(price_list_rate) == 0:
					frappe.msgprint(
						_(
							f"Item Price for '{get_link_to_form('Item', inpatient.get('item'))}' is set to zero. Please verify."
						),
						alert=1,
						indicator="warning",
						title=_("Warning!"),
					)

				minimum_billable_qty = inpatient.get("minimum_billable_qty")
				total_qty = (
					(inpatient.get("total_hours") / (inpatient.get("no_of_hours") or 1))
					if inpatient.get("total_hours")
					else 0
				)
				quantity = max(total_qty, minimum_billable_qty)

				# Add or update item row based on existing data
				if not item_row:
					# Add new item row if none exists
					se_child = self.append("items")
					se_child.item_code = inpatient.get("item")
					se_child.item_name = item_name
					se_child.stock_uom = stock_uom
					se_child.uom = inpatient.get("uom")
					se_child.quantity = quantity
					se_child.rate = price_list_rate
				else:
					if item_row.get("invoiced"):
						# Add new row if invoiced and additional quantity exists
						if item_row.get("quantity") and quantity and quantity > item_row.get("quantity"):
							se_child = self.append("items")
							se_child.item_code = inpatient.get("item")
							se_child.item_name = item_name
							se_child.stock_uom = stock_uom
							se_child.uom = inpatient.get("uom")
							se_child.quantity = quantity - item_row.get("quantity")
							se_child.rate = price_list_rate
					else:
						# Update existing non-invoiced item row
						if quantity != item_row.get("quantity"):
							for item in self.items:
								if item.name == item_row.get("name"):
									item.uom = inpatient.get("uom")
									item.quantity = quantity
									item.rate = price_list_rate

			# Update inpatient occupancy billing time
			for test in self.inpatient_occupancies:
				if test.name == inpatient.get("name"):
					test.scheduled_billing_time = now()

			self.save()

		except Exception as e:
			frappe.log_error(message=e, title="Can't bill Service Unit occupancy")
			raise

	@frappe.whitelist()
	def create_insurance_coverage(self):
		if self.insurance_policy and self.inpatient_occupancies:
			if any(not data_row.insurance_coverage for data_row in self.inpatient_occupancies):
				for inpatient_occupancy in self.inpatient_occupancies:
					if inpatient_occupancy.left and not inpatient_occupancy.insurance_coverage:
						service_unit_type = frappe.db.get_value(
							"Healthcare Service Unit", inpatient_occupancy.service_unit, "service_unit_type"
						)
						service_unit_type = frappe.get_doc("Healthcare Service Unit Type", service_unit_type)
						hours_occupied = flt(
							time_diff_in_hours(inpatient_occupancy.check_out, inpatient_occupancy.check_in), 2
						)
						qty = 0.5
						if hours_occupied > 0 and service_unit_type.no_of_hours:
							actual_qty = hours_occupied / service_unit_type.no_of_hours
							floored_qty = floor(actual_qty)
							decimal_part = actual_qty - floored_qty
							if decimal_part > 0.5:
								qty = rounded(floored_qty + 1, 1)
							elif decimal_part < 0.5 and decimal_part > 0:
								qty = rounded(floored_qty + 0.5, 1)
							if qty <= 0:
								qty = 0.5
						coverage = self.make_insurance_coverage(service_unit_type.name, qty)
						if coverage and coverage.get("coverage"):
							frappe.db.set_value(
								"Inpatient Occupancy",
								inpatient_occupancy.name,
								{
									"insurance_coverage": coverage.get("coverage"),
									"coverage_status": coverage.get("coverage_status"),
								},
							)
			else:
				frappe.throw(_("Claim already created for all Inpatient Occupancies"))

	def make_insurance_coverage(self, service_unit_type, qty):
		billing_detail = get_appointment_billing_item_and_rate(self)
		return generate_insurance_coverage(
			patient=self.patient,
			policy=self.insurance_policy,
			company=self.company,
			template_dt="Healthcare Service Unit Type",
			template_dn=service_unit_type,
			item_code=billing_detail.get("service_item"),
			qty=qty,
		)


@frappe.whitelist()
def schedule_inpatient(admission_order):
	if isinstance(admission_order, str):
		admission_order = json.loads(admission_order)  # admission order via Encounter

	if admission_order.get("treatment_plan_template") and frappe.db.get_value(
		"Treatment Plan Template",
		admission_order.get("treatment_plan_template"),
		"treatment_counselling_required_for_ip",
	):
		create_treatment_counselling(admission_order)
	else:
		create_inpatient_record(admission_order)


def create_inpatient_record(admission_order):
	if isinstance(admission_order, str):
		admission_order = json.loads(admission_order)

	if not admission_order or not admission_order["patient"] or not admission_order["admission_encounter"]:
		frappe.throw(_("Missing required details, did not create Inpatient Record"))

	inpatient_record = frappe.new_doc("Inpatient Record")

	# Admission order details
	set_details_from_ip_order(inpatient_record, admission_order)

	# Patient details
	patient = frappe.get_doc("Patient", admission_order["patient"])
	inpatient_record.patient = patient.name
	inpatient_record.patient_name = patient.patient_name
	inpatient_record.gender = patient.sex
	inpatient_record.blood_group = patient.blood_group
	inpatient_record.dob = patient.dob
	inpatient_record.mobile = patient.mobile
	inpatient_record.email = patient.email
	inpatient_record.phone = patient.phone
	inpatient_record.scheduled_date = today()

	# Set encounter details
	encounter = frappe.get_doc("Patient Encounter", admission_order["admission_encounter"])
	if encounter and encounter.symptoms:
		set_ip_child_records(inpatient_record, "chief_complaint", encounter.symptoms)

	if encounter and encounter.diagnosis:
		set_ip_child_records(inpatient_record, "diagnosis", encounter.diagnosis)

	if encounter and encounter.drug_prescription:
		set_ip_child_records(inpatient_record, "drug_prescription", encounter.drug_prescription)

	if encounter and encounter.lab_test_prescription:
		set_ip_child_records(inpatient_record, "lab_test_prescription", encounter.lab_test_prescription)

	if encounter and encounter.procedure_prescription:
		set_ip_child_records(inpatient_record, "procedure_prescription", encounter.procedure_prescription)

	if encounter and encounter.therapies:  # Therapies
		inpatient_record.therapy_plan = encounter.therapy_plan
		set_ip_child_records(inpatient_record, "therapies", encounter.therapies)

	inpatient_record.insurance_policy = encounter.insurance_policy
	inpatient_record.status = "Admission Scheduled"
	inpatient_record.save(ignore_permissions=True)
	return inpatient_record.name


@frappe.whitelist()
def schedule_discharge(discharge_order: str):
	discharge_order = json.loads(discharge_order)
	inpatient_record_id = frappe.db.get_value("Patient", discharge_order["patient"], "inpatient_record")

	if inpatient_record_id:
		inpatient_record = frappe.get_doc("Inpatient Record", inpatient_record_id)

		set_details_from_ip_order(inpatient_record, discharge_order)
		inpatient_record.status = "Discharge Scheduled"
		inpatient_record.save(ignore_permissions=True)

		frappe.db.set_value(
			"Patient", discharge_order["patient"], "inpatient_status", inpatient_record.status
		)
		if inpatient_record.discharge_encounter:
			frappe.db.set_value(
				"Patient Encounter",
				inpatient_record.discharge_encounter,
				"inpatient_status",
				inpatient_record.status,
			)

		if inpatient_record.discharge_nursing_checklist_template:
			NursingTask.create_nursing_tasks_from_template(
				inpatient_record.discharge_nursing_checklist_template,
				inpatient_record,
				start_time=now_datetime(),
			)


def set_details_from_ip_order(inpatient_record, ip_order):
	for key in ip_order:
		inpatient_record.set(key, ip_order[key])


def set_ip_child_records(inpatient_record, inpatient_record_child, encounter_child):
	for item in encounter_child:
		table = inpatient_record.append(inpatient_record_child)
		for df in table.meta.get("fields"):
			table.set(df.fieldname, item.get(df.fieldname))


def check_out_inpatient(inpatient_record):
	if inpatient_record.inpatient_occupancies:
		for inpatient_occupancy in inpatient_record.inpatient_occupancies:
			if inpatient_occupancy.left != 1:
				inpatient_occupancy.left = True
				inpatient_occupancy.check_out = now_datetime()
				frappe.db.set_value(
					"Healthcare Service Unit", inpatient_occupancy.service_unit, "occupancy_status", "Vacant"
				)


def discharge_patient(inpatient_record):
	validate_nursing_tasks(inpatient_record)

	validate_inpatient_invoicing(inpatient_record)

	validate_invoice_payment(inpatient_record)

	validate_incomplete_service_requests(inpatient_record)

	check_out_inpatient(inpatient_record)
	inpatient_record.discharge_datetime = now_datetime()
	inpatient_record.status = "Discharged"

	inpatient_record.save(ignore_permissions=True)


def validate_inpatient_invoicing(inpatient_record):
	if frappe.db.get_single_value("Healthcare Settings", "allow_discharge_despite_unbilled_services"):
		return

	pending_invoices = get_pending_invoices(inpatient_record)

	if pending_invoices:
		message = _("Cannot mark Inpatient Record as Discharged since there are unbilled services. ")

		formatted_doc_rows = ""

		for doctype, docnames in pending_invoices.items():
			formatted_doc_rows += f"""
				<td>{doctype}</td>
				<td>{docnames}</td>
			</tr>"""

		message += f"""
			<table class='table'>
				<thead>
					<th>{_("Healthcare Service")}</th>
					<th>{_("Documents")}</th>
				</thead>
				{formatted_doc_rows}
			</table>
		"""

		frappe.throw(message, title=_("Unbilled Services"), is_minimizable=True, wide=True)


def get_pending_invoices(inpatient_record):
	pending_invoices = {}
	if not frappe.db.get_single_value("Healthcare Settings", "automatically_generate_billable"):
		if inpatient_record.inpatient_occupancies:
			service_unit_names = False
			for inpatient_occupancy in inpatient_record.inpatient_occupancies:
				if not inpatient_occupancy.invoiced:
					if is_service_unit_billable(inpatient_occupancy.service_unit):
						if service_unit_names:
							service_unit_names += ", " + inpatient_occupancy.service_unit
						else:
							service_unit_names = inpatient_occupancy.service_unit
			if service_unit_names:
				pending_invoices["Inpatient Occupancy"] = service_unit_names
	else:
		if inpatient_record.items:
			service_unit_names = False
			for item in inpatient_record.items:
				if not item.invoiced:
					if service_unit_names:
						service_unit_names += ", " + item.item_code
					else:
						service_unit_names = item.item_code
			if service_unit_names:
				pending_invoices["Items"] = service_unit_names

	if not frappe.db.get_single_value("Healthcare Settings", "do_not_bill_inpatient_encounters"):
		docs = ["Patient Appointment", "Patient Encounter", "Lab Test", "Clinical Procedure"]
	else:
		docs = ["Lab Test", "Clinical Procedure"]

	for doc in docs:
		doc_name_list = get_unbilled_inpatient_docs(doc, inpatient_record)
		if doc_name_list:
			pending_invoices = get_pending_doc(doc, doc_name_list, pending_invoices)

	return pending_invoices


def get_pending_doc(doc, doc_name_list, pending_invoices):
	if doc_name_list:
		doc_ids = False
		for doc_name in doc_name_list:
			doc_link = get_link_to_form(doc, doc_name.name)
			if doc_ids:
				doc_ids += ", " + doc_link
			else:
				doc_ids = doc_link
		if doc_ids:
			pending_invoices[doc] = doc_ids

	return pending_invoices


def get_unbilled_inpatient_docs(doc, inpatient_record):
	filters = {
		"patient": inpatient_record.patient,
		"inpatient_record": inpatient_record.name,
		"docstatus": 1,
	}
	if doc in ["Service Request", "Medication Request"]:
		filters.update(
			{
				"billing_status": "Pending",
			}
		)
	else:
		if doc == "Patient Encounter":
			filters.update(
				{
					"appointment": "",
				}
			)
		else:
			del filters["docstatus"]
		filters.update(
			{
				"invoiced": 0,
			}
		)
	if doc in ["Lab Test", "Clinical Procedure"]:
		filters.update(
			{
				"service_request": "",
			}
		)
	return frappe.db.get_list(doc, filters=filters)


def get_inpatient_invoices(inpatient_record, only_outstanding=False):
	"""Submitted Sales Invoices that cover THIS specific admission -
	identified by carrying a line whose reference_dn is one of this
	Inpatient Record's own Inpatient Record Item or Inpatient Occupancy
	child rows (the same two reference types create_invoice_for_inpatient()
	tags when it bills this admission).

	Deliberately scoped to this admission, not just "this patient" - an
	older, already-settled admission's invoice (or a brand new one for a
	readmission) shouldn't count against this one, whether that's
	validate_invoice_payment() below deciding what blocks discharge, or
	the Nurse Station deciding what balance/invoiced-state to show for
	this row (see get_admitted_patients() in nurse_station.py, the other
	caller of this function).

	With only_outstanding=False (the default) this includes fully-paid
	invoices too - used to tell whether this admission has EVER been
	invoiced, not just whether something's still owed, so a "Create
	Invoice" action can disable itself once billing's already been done
	rather than risk creating a second, duplicate invoice for the same
	charges. Pass only_outstanding=True for the payment-still-owed
	question instead (see get_unpaid_inpatient_invoices below).

	Takes either a loaded Inpatient Record doc or just its name - the
	Nurse Station's Admitted Patients list calls this once per row from
	a plain record dict, so it only has the name on hand.
	"""
	inpatient_record_name = (
		inpatient_record if isinstance(inpatient_record, str) else inpatient_record.name
	)

	reference_names = frappe.get_all(
		"Inpatient Record Item", filters={"parent": inpatient_record_name}, pluck="name"
	)
	reference_names += frappe.get_all(
		"Inpatient Occupancy", filters={"parent": inpatient_record_name}, pluck="name"
	)
	if not reference_names:
		return []

	sii = frappe.qb.DocType("Sales Invoice Item")
	si = frappe.qb.DocType("Sales Invoice")

	query = (
		frappe.qb.from_(si)
		.join(sii)
		.on(sii.parent == si.name)
		.select(si.name)
		.where((si.docstatus == 1) & (sii.reference_dn.isin(reference_names)))
		.distinct()
	)
	if only_outstanding:
		query = query.where(si.outstanding_amount > 0)

	invoice_names = [row[0] for row in query.run()]
	if not invoice_names:
		return []

	return frappe.get_all(
		"Sales Invoice",
		filters={"name": ["in", invoice_names]},
		fields=["name", "outstanding_amount", "currency", "grand_total"],
		order_by="posting_date asc",
	)


def get_unpaid_inpatient_invoices(inpatient_record):
	"""Just this admission's invoices that still have money owed on them -
	see get_inpatient_invoices() above for the full picture (this is a
	thin, only_outstanding=True wrapper over it). Used by
	validate_invoice_payment() below to decide what blocks discharge."""
	return get_inpatient_invoices(inpatient_record, only_outstanding=True)


def validate_invoice_payment(inpatient_record):
	"""Cannot discharge while money is still owed on this admission's own
	Sales Invoice(s). Being billed (validate_inpatient_invoicing above)
	is a different thing from being paid - that check only cares whether
	a Sales Invoice was ever raised, not whether it was settled - so a
	hospital that wants payment collected before the bed is released
	needs this checked separately, after invoicing but before the
	"Incomplete Services" check.

	Unlike validate_inpatient_invoicing, there's deliberately no
	Healthcare Settings escape hatch here - this is a hard stop every
	time, since it was asked for as an unconditional rule ("once paid,
	before patient can be discharged"), not a configurable one.
	"""
	unpaid = get_unpaid_inpatient_invoices(inpatient_record)
	if not unpaid:
		return

	rows = "".join(
		f"""<tr>
			<td>{get_link_to_form("Sales Invoice", inv.name)}</td>
			<td style="text-align:right">{frappe.utils.fmt_money(inv.outstanding_amount, currency=inv.currency)}</td>
		</tr>"""
		for inv in unpaid
	)
	message = _(
		"Cannot discharge - the following invoice(s) for this admission still have an outstanding balance. "
		"Payment must be collected (see the Cashier's Inpatient Billing tab) before discharge."
	)
	message += f"""
		<table class='table'>
			<thead>
				<th>{_("Invoice")}</th>
				<th>{_("Outstanding")}</th>
			</thead>
			{rows}
		</table>
	"""
	frappe.throw(message, title=_("Payment Pending"), is_minimizable=True, wide=True)


def _get_inpatient_consulting_charges(patient, company, inpatient_record):
	"""Just this admission's own slice of what get_encounters_to_invoice()
	would bill - the Inpatient/Consulting Visit Charge for a not-yet-
	invoiced, submitted Patient Encounter tied to THIS Inpatient Record.

	Uses the Patient Encounter doctype's own existing inpatient_record
	Link field to tell "this encounter happened during this admission"
	from "this was an ordinary walk-in encounter" - no new field needed:
	patient_encounter.js's set_patient_info() already auto-fills this the
	moment a currently-admitted patient is selected on any encounter, so
	a genuine walk-in (patient not currently admitted) always leaves it
	blank, and every encounter taken during this stay always has it set
	to this Inpatient Record.

	Reuses get_encounters_to_invoice()'s own logic (insurance coverage,
	the appointment-linked skip, the "do_not_bill_inpatient_encounters"
	Healthcare Settings check, get_appointment_billing_item_and_rate() for
	the actual rate) rather than duplicating it - just filters its result
	down to encounters that belong to this admission. That function on
	its own is patient-wide: it bills EVERY unbilled encounter the
	patient has, inpatient or outpatient, which is exactly what pulled
	unrelated charges into an admission invoice before this split.
	"""
	this_admissions_encounters = set(
		frappe.get_all(
			"Patient Encounter",
			filters={"inpatient_record": inpatient_record.name, "invoiced": 0, "docstatus": 1},
			pluck="name",
		)
	)
	if not this_admissions_encounters:
		return []

	return [
		entry
		for entry in (get_encounters_to_invoice(patient, company) or [])
		if entry.get("reference_name") in this_admissions_encounters
	]


def _get_inpatient_service_unit_charges(patient, company, inpatient_record):
	"""Just this admission's own Service Unit (ward) occupancy charges,
	plus any other un-invoiced row already sitting in this Inpatient
	Record's own Inpatient Billables table - reuses
	get_inpatient_services_to_invoice()'s own logic (it already respects
	Healthcare Settings > "Automatically Generate Billable") but filters
	its result down to occupancy/item rows that belong to THIS Inpatient
	Record specifically (its own inpatient_occupancies/items child
	tables), not just any admission this patient's ever had - that
	function on its own only scopes by patient, not by admission.
	"""
	this_admissions_occupancy_names = {row.name for row in inpatient_record.inpatient_occupancies}
	this_admissions_item_names = {row.name for row in inpatient_record.items}

	charges = []
	for entry in get_inpatient_services_to_invoice(patient, company) or []:
		reference_type = entry.get("reference_type")
		reference_name = entry.get("reference_name")
		if reference_type == "Inpatient Occupancy" and reference_name in this_admissions_occupancy_names:
			charges.append(entry)
		elif reference_type == "Inpatient Record Item" and reference_name in this_admissions_item_names:
			charges.append(entry)
	return charges


def _get_inpatient_lab_charges(patient, company, inpatient_record):
	"""Just this admission's own lab orders - deliberately NOT every lab
	the patient's ever had ordered through any encounter (that's what
	get_lab_tests_to_invoice()/the old get_healthcare_services_to_invoice()
	swept in before).

	A lab order is "this admission's" if its Service Request's order_group
	is either this Inpatient Record itself (labs ordered straight onto the
	admission - e.g. create_orders_from_treatment_counselling() at Admit
	time) or one of THIS admission's own encounters (the same
	inpatient_record-tagged encounters _get_inpatient_consulting_charges()
	above uses - not every encounter the patient has ever had). No new
	field needed: order_group + the encounter's existing inpatient_record
	link are enough to tell "ordered during this stay" from "ordered on
	some other visit".

	Reuses get_service_requests_to_invoice()'s own billing/insurance logic
	rather than duplicating it - just filters its result down to Service
	Requests against a Lab Test Template that belong to this admission.
	"""
	this_admissions_encounters = frappe.get_all(
		"Patient Encounter",
		filters={"inpatient_record": inpatient_record.name},
		pluck="name",
	)
	eligible_order_groups = set(this_admissions_encounters) | {inpatient_record.name}

	this_admissions_lab_requests = set(
		frappe.get_all(
			"Service Request",
			filters={
				"order_group": ["in", list(eligible_order_groups)],
				"template_dt": "Lab Test Template",
				"billing_status": ["!=", "Invoiced"],
				"docstatus": 1,
			},
			pluck="name",
		)
	)
	if not this_admissions_lab_requests:
		return []

	return [
		entry
		for entry in (get_service_requests_to_invoice(patient, company) or [])
		if entry.get("reference_type") == "Service Request"
		and entry.get("reference_name") in this_admissions_lab_requests
	]


def _build_unsaved_inpatient_invoice(inpatient_record):
	"""Build (but never insert or submit) an in-memory Sales Invoice covering
	just three things for THIS specific admission: the Inpatient Consulting
	(Visit) Charge for its own encounter(s), its own Service Unit (ward)
	occupancy charges, and its own lab orders - see
	_get_inpatient_consulting_charges(), _get_inpatient_service_unit_charges()
	and _get_inpatient_lab_charges() above.

	Shared by create_invoice_for_inpatient() (which inserts and submits this)
	and preview_invoice_items() (which reads it back without saving anything)
	so the itemised breakdown a nurse is shown before confirming is built by
	the identical code path that then actually bills it - never two separate
	calculations that could drift apart.

	Deliberately narrow, and this was NOT always the case: this used to
	call get_healthcare_services_to_invoice(), which bills every
	outstanding healthcare charge for the PATIENT - any appointment, any
	encounter (inpatient or not), any lab the patient's ever had ordered
	through any encounter, clinical procedures, therapy, any other
	Service Request. That's what silently swept in unrelated
	encounter-ordered lab tests (and, worse, auto-created real Lab Test
	records for them - see manage_invoice_submit_cancel() in
	healthcare/utils.py) the moment an admission invoice was created.
	Anything outside these three - other encounters, appointments,
	procedures, therapy, lab orders placed on a different visit, unrelated
	Service Requests - is billed through its own normal flow (Lab Portal,
	the standard Sales Invoice "Get Items From > Healthcare Services"
	dialog, etc.), never swept in by this one-click admission action.
	"""
	patient = frappe.get_doc("Patient", inpatient_record.patient)
	if not patient.customer:
		frappe.throw(
			_("Patient {0} is not linked to a Customer - link one before an invoice can be created").format(
				patient.patient_name
			)
		)

	# Mirrors what "Schedule Discharge" already triggers via
	# generate_billables() - make sure today's ward rent is reflected in
	# the Inpatient Billables table before pulling the invoice list, so a
	# preview (or an actual "Sales Invoice" click) taken any time during
	# the stay bills/shows the right amount rather than whatever ward
	# rent was last saved. Note this does write - it saves the Inpatient
	# Record's own Inpatient Billables table - even when only previewing;
	# that's the same refresh create_invoice_for_inpatient() already did
	# unconditionally before this was split out, so a preview's total
	# matches what actually gets billed a moment later.
	inpatient_record.add_service_unit_rent_to_billable_items()

	items_to_invoice = []
	items_to_invoice += _get_inpatient_consulting_charges(patient, inpatient_record.company, inpatient_record)
	items_to_invoice += _get_inpatient_service_unit_charges(patient, inpatient_record.company, inpatient_record)
	items_to_invoice += _get_inpatient_lab_charges(patient, inpatient_record.company, inpatient_record)

	si = frappe.new_doc("Sales Invoice")
	si.patient = patient.name
	si.customer = patient.customer
	si.company = inpatient_record.company
	si.due_date = today()

	for entry in items_to_invoice:
		if not entry.get("service"):
			# A couple of aggregators (e.g. a Patient Encounter with no
			# practitioner charge configured) can surface a row with no
			# billable item at all - skip it rather than let it fail
			# set_missing_values()/insert() with a blank item_code.
			continue
		row = si.append("items", {})
		row.item_code = entry.get("service")
		row.qty = flt(entry.get("qty") or 1)
		row.reference_dt = entry.get("reference_type")
		row.reference_dn = entry.get("reference_name")
		if entry.get("rate"):
			row.rate = flt(entry.get("rate"))
		if entry.get("discount_percentage"):
			row.discount_percentage = flt(entry.get("discount_percentage"))
		if entry.get("income_account"):
			row.income_account = entry.get("income_account")
		if entry.get("insurance_coverage"):
			row.insurance_coverage = entry.get("insurance_coverage")
			row.insurance_payor = entry.get("insurance_payor")
			row.patient_insurance_policy = entry.get("patient_insurance_policy")

	if not si.items:
		frappe.throw(_("Nothing outstanding to invoice for {0}").format(patient.patient_name))

	si.set_missing_values()
	si.calculate_taxes_and_totals()
	return si


def create_invoice_for_inpatient(inpatient_record):
	"""Bill everything currently unbilled for this admission's patient into
	one submitted Sales Invoice - see _build_unsaved_inpatient_invoice()
	above for how the line items are put together.

	Exposed as a one-click "Sales Invoice" action from this doctype's
	Create menu (and the Nurse Station's Admitted Patients tab, which
	shows preview_invoice_items()'s breakdown first) so a nurse or
	front-desk user doesn't have to open a blank Sales Invoice and drive
	that dialog by hand before a patient can pay towards discharge.
	"""
	si = _build_unsaved_inpatient_invoice(inpatient_record)
	si.insert(ignore_permissions=True)
	si.submit()

	return {"invoice": si.name, "grand_total": si.grand_total, "currency": si.currency}


def preview_invoice_items(inpatient_record):
	"""Read-only itemised preview of exactly what create_invoice_for_inpatient()
	would bill right now - same builder, minus insert()/submit(), so a nurse
	or front-desk user can see the actual services, quantities, rates and
	total before committing to creating the invoice, instead of a bare
	yes/no confirm. Nothing here is inserted or submitted to the database
	(add_service_unit_rent_to_billable_items() still saves the Inpatient
	Record's own billables table - see that function's docstring above).
	"""
	si = _build_unsaved_inpatient_invoice(inpatient_record)
	return {
		"currency": si.currency,
		"grand_total": si.grand_total,
		"items": [
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": row.qty,
				"uom": row.uom,
				"rate": row.rate,
				"amount": row.amount,
				"reference_dt": row.reference_dt,
				"reference_dn": row.reference_dn,
			}
			for row in si.items
		],
	}


def admit_patient(
	inpatient_record, service_unit, check_in, expected_discharge=None, currency=None, price_list=None
):
	validate_nursing_tasks(inpatient_record)

	inpatient_record.admitted_datetime = check_in
	inpatient_record.status = "Admitted"
	inpatient_record.expected_discharge = expected_discharge
	inpatient_record.currency = currency or inpatient_record.currency
	inpatient_record.price_list = price_list

	inpatient_record.set("inpatient_occupancies", [])
	transfer_patient(inpatient_record, service_unit, check_in)

	frappe.db.set_value(
		"Patient",
		inpatient_record.patient,
		{"inpatient_status": "Admitted", "inpatient_record": inpatient_record.name},
	)


def transfer_patient(inpatient_record, service_unit, check_in, txred=0):
	if any(
		(inpat_occup.service_unit == service_unit and inpat_occup.left == 0)
		for inpat_occup in inpatient_record.inpatient_occupancies
	):
		return

	if frappe.get_cached_value("Healthcare Service Unit", service_unit, "occupancy_status") != "Vacant":
		frappe.throw(
			_(
				"The selected Service Unit <strong>{0}</strong> is already occupied. Please choose a vacant Service Unit."
			).format(service_unit),
			title=_("Service Unit Occupied"),
		)

	item_line = inpatient_record.append("inpatient_occupancies", {})
	item_line.service_unit = service_unit
	item_line.check_in = check_in

	if txred:
		item_line.transferred_for_procedure = 1
	else:
		for inpat_occup in inpatient_record.inpatient_occupancies:
			if inpat_occup.transferred_for_procedure == 0 and inpat_occup.left == 0:
				inpat_occup.left = 1

	inpatient_record.save(ignore_permissions=True)

	frappe.db.set_value("Healthcare Service Unit", service_unit, "occupancy_status", "Occupied")


def patient_leave_service_unit(inpatient_record, check_out, leave_from):
	if inpatient_record.inpatient_occupancies:
		for inpatient_occupancy in inpatient_record.inpatient_occupancies:
			if inpatient_occupancy.left != 1 and inpatient_occupancy.service_unit == leave_from:
				inpatient_occupancy.left = True
				inpatient_occupancy.check_out = check_out
				frappe.db.set_value(
					"Healthcare Service Unit", inpatient_occupancy.service_unit, "occupancy_status", "Vacant"
				)
	inpatient_record.save(ignore_permissions=True)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_leave_from(doctype, txt, searchfield, start, page_len, filters):
	docname = filters["docname"]

	query = """select io.service_unit
		from `tabInpatient Occupancy` io, `tabInpatient Record` ir
		where io.parent = '{docname}' and io.parentfield = 'inpatient_occupancies'
		and io.left!=1 and io.parent = ir.name"""

	return frappe.db.sql(
		query.format(**{"docname": docname, "searchfield": searchfield, "mcond": get_match_cond(doctype)}),
		{"txt": f"%{txt}%", "_txt": txt.replace("%", ""), "start": start, "page_len": page_len},
	)


def is_service_unit_billable(service_unit):
	service_unit_doc = frappe.qb.DocType("Healthcare Service Unit")
	service_unit_type = frappe.qb.DocType("Healthcare Service Unit Type")
	result = (
		frappe.qb.from_(service_unit_doc)
		.left_join(service_unit_type)
		.on(service_unit_doc.service_unit_type == service_unit_type.name)
		.select(service_unit_type.is_billable)
		.where(service_unit_doc.name == service_unit)
	).run(as_dict=1)
	return result[0].get("is_billable", 0)


@frappe.whitelist()
def set_ip_order_cancelled(inpatient_record, reason, encounter=None):
	inpatient_record = frappe.get_doc("Inpatient Record", inpatient_record)
	if inpatient_record.status == "Admission Scheduled":
		inpatient_record.status = "Cancelled"
		inpatient_record.reason_for_cancellation = reason
		inpatient_record.save(ignore_permissions=True)
		encounter_name = encounter if encounter else inpatient_record.admission_encounter
		if encounter_name:
			frappe.db.set_value(
				"Patient Encounter", encounter_name, {"inpatient_status": None, "inpatient_record": None}
			)


@frappe.whitelist()
def cancel_amend_treatment_counselling(args, treatment_counselling):
	if isinstance(args, str):
		args = json.loads(args)
	tpc_doc = frappe.get_doc("Treatment Counselling", treatment_counselling)
	tpc_doc.flags.ignore_validate = True
	tpc_doc.cancel()
	args["amended_from"] = treatment_counselling
	create_treatment_counselling(args)


@frappe.whitelist()
def make_discharge_summary(source_name, target_doc=None, ignore_permissions=False):
	doclist = get_mapped_doc(
		"Inpatient Record",
		source_name,
		{
			"Inpatient Record": {
				"doctype": "Discharge Summary",
				"field_map": {
					"name": "inpatient_record",
				},
				"field_no_map": ["status", "chief_complaint", "diagnosis"],
			},
		},
		target_doc,
	)

	return doclist


@frappe.whitelist()
def create_treatment_counselling(ip_order):
	if isinstance(ip_order, str):
		ip_order = json.loads(ip_order)
	financial_counselling = frappe.new_doc("Treatment Counselling")
	set_details_from_ip_order(financial_counselling, ip_order)
	financial_counselling.encounter_status = "Admission Scheduled"
	financial_counselling.status = "Active"
	financial_counselling.save(ignore_permissions=True)


@frappe.whitelist()
def create_stock_entry(items, inpatient_record):
	items = json.loads(items)
	ip_record_doc = frappe.get_doc("Inpatient Record", inpatient_record)
	stock_entry = frappe.new_doc("Stock Entry")

	stock_entry.stock_entry_type = "Material Issue"
	stock_entry.to_warehouse = ip_record_doc.warehouse
	stock_entry.company = ip_record_doc.company
	expense_account = get_account(None, "expense_account", "Healthcare Settings", ip_record_doc.company)
	for item in items:
		se_child = stock_entry.append("items")
		se_child.item_code = item.get("item_code")
		se_child.uom = item.get("uom")
		se_child.qty = item.get("quantity")
		se_child.s_warehouse = ip_record_doc.warehouse
		cost_center = frappe.get_cached_value("Company", ip_record_doc.company, "cost_center")
		se_child.cost_center = cost_center
		se_child.expense_account = expense_account
	stock_entry.save().submit()

	return stock_entry.name


def set_item_rate(doc):
	price_list, price_list_currency = frappe.db.get_values(
		"Price List", {"selling": 1}, ["name", "currency"]
	)[0]

	for item in doc.items:
		if not item.rate:
			ctx: ItemDetailsCtx = ItemDetailsCtx(
				{
					"doctype": "Sales Invoice",
					"item_code": item.get("item_code"),
					"company": doc.company,
					"customer": frappe.db.get_value("Patient", doc.patient, "customer"),
					"selling_price_list": doc.price_list or price_list,
					"price_list_currency": doc.currency or price_list_currency,
					"plc_conversion_rate": 1.0,
					"conversion_rate": 1.0,
					"currency": doc.currency or price_list_currency,
				}
			)
			item_details = get_item_details(ctx)
			item.rate = item_details.get("price_list_rate")
			item.amount = item.rate * item.quantity

		item.amount = item.rate * item.quantity


def add_occupied_service_unit_in_ip_to_billables():
	if not frappe.db.get_single_value("Healthcare Settings", "automatically_generate_billable"):
		return

	inpatient_records = frappe.get_all(
		"Inpatient Record", {"status": ("in", ["Admitted", "Discharge Scheduled"])}
	)

	for inpatient_record in inpatient_records:
		frappe.get_doc("Inpatient Record", inpatient_record.name).add_service_unit_rent_to_billable_items()


def set_total(self):
	total = 0
	if self.items:
		for p in self.items:
			if p.get("amount"):
				total += p.get("amount")
	self.total = total


def validate_incomplete_service_requests(inpatient_record):
	if frappe.db.get_single_value(
		"Healthcare Settings", "allow_discharge_despite_pending_healthcare_services"
	):
		return

	filters = {
		"patient": inpatient_record.patient,
		"inpatient_record": inpatient_record.name,
		"docstatus": 1,
		# Service Request.status is a Link to Code Value, not a plain Select -
		# every place in this app that actually completes an order (Lab Test,
		# Clinical Procedure, Therapy Session, all via
		# service_request.set_service_request_status()) writes the Code
		# Value's own name, "completed-Request Status", never the literal
		# string "Completed". Filtering on "Completed" here matched nothing
		# real, ever, so every submitted Service Request on an admission -
		# including ones genuinely marked Completed - got listed as an
		# incomplete order blocking discharge.
		"status": ["not in", ["completed-Request Status"]],
	}

	service_requests = frappe.db.get_list("Service Request", filters=filters, pluck="name")
	if service_requests and len(service_requests) > 0:
		service_requests = [
			get_link_to_form("Service Request", service_request) for service_request in service_requests
		]
		service_request_list = ", ".join(str(request) for request in service_requests)
		message = _("There are Orders yet to be carried out<b> {0}").format(frappe.bold(service_request_list))

		frappe.throw(message, title=_("Incomplete Services"), is_minimizable=True, wide=True)


def insert_pending_service_request(doc):
	treatment_counselling = frappe.db.exists(
		{"doctype": "Treatment Counselling", "inpatient_record": doc.name}
	)
	if treatment_counselling:
		counselling_doc = frappe.get_doc("Treatment Counselling", treatment_counselling)

		for treatment_items in counselling_doc.treatment_plan_template_items:
			if not treatment_items.service_request:
				template_doc = frappe.get_doc(treatment_items.type, treatment_items.template)
				order = frappe.get_doc(
					{
						"doctype": "Service Request",
						"order_date": today(),
						"order_time": now(),
						"company": doc.company,
						"status": "Draft",
						"patient": doc.get("patient"),
						"practitioner": doc.primary_practitioner,
						"source_doc": "Inpatient Record",
						"order_group": doc.name,
						"patient_care_type": template_doc.get("patient_care_type"),
						"staff_role": template_doc.get("staff_role"),
						"medical_code": template_doc.get("medical_code"),
						"medical_code_standard": template_doc.get("medical_code_standard"),
						"template_dt": treatment_items.get("type"),
						"template_dn": treatment_items.get("template"),
					}
				)
				order.insert(ignore_permissions=True, ignore_mandatory=True)
				order.submit()


def create_orders_from_treatment_counselling(doc):
	treatment_councelling = frappe.db.get_value(
		"Treatment Counselling", {"inpatient_record": doc.name, "status": "Completed"}, "name"
	)
	if not treatment_councelling:
		return
	tc_doc = frappe.get_doc("Treatment Counselling", treatment_councelling)
	create_orders = False
	for item in tc_doc.treatment_plan_template_items:
		if not item.service_request:
			if item.get("type") == "Medication":
				medication = frappe.get_doc("Medication", item.get("template"))
				order = get_order_details(tc_doc, medication, item, doc.name, True)
				order.insert(ignore_permissions=True, ignore_mandatory=True)
				order.submit()
				item.service_request = order.name
				create_orders = True

			elif item.get("type") in [
				"Observation Template",
				"Lab Test Template",
				"Therapy Type",
				"Clinical Procedure Template",
			]:
				lab_template = frappe.get_doc(item.get("type"), item.get("template"))
				order = get_order_details(tc_doc, lab_template, item, doc.name)
				order.insert(ignore_permissions=True, ignore_mandatory=True)
				order.submit()
				item.service_request = order.name
				create_orders = True
	tc_doc.save("Update")

	if create_orders:
		frappe.msgprint(
			_("Orders Created from Treatment Counselling"),
			alert=True,
		)


def get_order_details(doc, template_doc, line_item, ip_name, medication_request=False):
	order = frappe.get_doc(
		{
			"doctype": "Medication Request" if medication_request else "Service Request",
			"order_date": frappe.utils.nowdate(),
			"order_time": frappe.utils.nowtime(),
			"company": doc.company,
			"status": "draft-Medication Request Status" if medication_request else "draft-Request Status",
			"patient": doc.get("patient"),
			"practitioner": doc.primary_practitioner,
			"source_doc": "Inpatient Record",
			"order_group": doc.admission_encounter if medication_request else ip_name,
			"sequence": line_item.get("sequence"),
			"patient_care_type": template_doc.get("patient_care_type"),
			"intent": line_item.get("intent"),
			"priority": line_item.get("priority"),
			"quantity": line_item.get_quantity() if line_item.get("doctype") == "Drug Prescription" else 1,
			"dose": line_item.get("dose"),
			"dosage": line_item.get("dosage"),
			"dosage_form": line_item.get("dosage_form"),
			"period": line_item.get("period"),
			"expected_date": line_item.get("expected_date"),
			"as_needed": line_item.get("as_needed"),
			"staff_role": template_doc.get("staff_role"),
			"note": line_item.get("note"),
			"patient_instruction": line_item.get("patient_instruction"),
			"medical_code": template_doc.get("medical_code"),
			"medical_code_standard": template_doc.get("medical_code_standard"),
			# Same gap as patient_encounter.py's get_order_details(): Drug
			# Prescription's own comment field is "comment" (singular), not
			# "comments"/"lab_test_comment" (those belong to Procedure/Lab
			# Test Prescription) - without this a drug ordered at admission
			# time via Treatment Counselling never carried its comment onto
			# the Medication Request this creates.
			"comment": line_item.get("comments")
			or line_item.get("lab_test_comment")
			or line_item.get("comment"),
		}
	)

	if not line_item.get("description"):
		if template_doc.doctype == "Lab Test Template":
			description = template_doc.get("lab_test_description")
		else:
			description = template_doc.get("description")
	else:
		description = line_item.get("description")

	if template_doc.doctype == "Clinical Procedure Template":
		order.update(
			{
				"referred_to_practitioner": line_item.get("practitioner"),
				"ordered_for": line_item.get("date"),
			}
		)
	elif template_doc.doctype == "Healthcare Activity":
		order.update(
			{
				"repeat_in_every": line_item.get("repeat_in_every"),
			}
		)
	if medication_request:
		order.update(
			{
				"source_dt": "Inpatient Record",
				"medication": template_doc.name,
				"number_of_repeats_allowed": line_item.get("number_of_repeats_allowed"),
				"medication_item": line_item.get("drug_code") if line_item.get("drug_code") else "",
				"healthcare_activity": line_item.get("healthcare_activity")
				if line_item.get("healthcare_activity")
				else "",
			}
		)
	else:
		order.update({"template_dt": template_doc.doctype, "template_dn": template_doc.name})

	order.update({"order_description": description})

	return order
