# Copyright (c) 2026, Ransbort and contributors
# For license information, please see license.txt

"""
Backend for the Spa Portal page (page/spa_portal/spa_portal.js).

ASSUMPTIONS TO VERIFY:

- `Spa Type` doctype exists with fields: spa_type_name, rate, item
  (Link -> Item, billed on the invoice), enabled (Check).
- `Spa Booking` doctype exists with fields: client_name, phone, spa_type
  (Link -> Spa Type), booking_date, booking_time, notes, status
  (Select: Scheduled/Completed/Cancelled/No Show).
- Sales Invoices created here are tagged `custom_invoice_from = "Spa"`,
  mirroring the same custom field pharmacy.py's Sales Orders use
  (custom_invoice_from = "Pharmacy") -- confirm Sales Invoice actually has
  this custom field, or add it via Customize Form if not.
- `Patient` has a `customer` field (standard in ERPNext Healthcare) used
  to resolve a Customer when booking against a Patient instead of a
  walk-in Customer.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, today


@frappe.whitelist()
def create_spa_invoice(spa_services, customer=None, patient=None, posting_date=None):
	"""
	spa_services: JSON string / list of {"spa_type": <Spa Type name>, "qty": <int>}
	"""

	if isinstance(spa_services, str):
		spa_services = json.loads(spa_services)

	if not spa_services:
		frappe.throw(_("Please add at least one spa service"))

	if not customer and not patient:
		frappe.throw(_("Please select a customer or patient"))

	if patient:
		customer = frappe.db.get_value("Patient", patient, "customer")
		if not customer:
			frappe.throw(_("Patient {0} has no linked Customer").format(patient))

	items = []
	for service in spa_services:
		spa_type = service.get("spa_type")
		qty = flt(service.get("qty")) or 1

		spa_type_doc = frappe.db.get_value(
			"Spa Type", spa_type, ["item", "rate", "spa_type_name"], as_dict=True
		)
		if not spa_type_doc:
			frappe.throw(_("Spa Type {0} not found").format(spa_type))

		item_code = spa_type_doc.item or spa_type
		rate = spa_type_doc.rate or 0

		items.append(
			{
				"item_code": item_code,
				"item_name": spa_type_doc.spa_type_name or spa_type,
				"qty": qty,
				"rate": rate,
			}
		)

	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": customer,
			"patient": patient or None,
			"posting_date": posting_date or today(),
			"custom_invoice_from": "Spa",
			"items": items,
		}
	)
	invoice.insert(ignore_permissions=True)
	invoice.submit()

	return {
		"status": "Success",
		"invoice_name": invoice.name,
		"grand_total": invoice.grand_total,
	}


@frappe.whitelist()
def get_spa_invoices(date=None):
	filters = {"custom_invoice_from": "Spa", "docstatus": 1}
	if date:
		filters["posting_date"] = date

	invoices = frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=[
			"name",
			"customer",
			"customer_name",
			"patient",
			"patient_name",
			"posting_date",
			"due_date",
			"grand_total",
			"outstanding_amount",
			"status",
		],
		order_by="posting_date desc",
	)

	for inv in invoices:
		inv["items"] = frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": inv["name"]},
			fields=["item_code", "item_name", "qty", "rate", "amount"],
		)

	return invoices


@frappe.whitelist()
def create_spa_booking(client_name, phone, spa_type, booking_date, booking_time, notes=None):
	if not (client_name and phone and spa_type and booking_date and booking_time):
		frappe.throw(_("Please fill in all required fields"))

	booking = frappe.get_doc(
		{
			"doctype": "Spa Booking",
			"client_name": client_name,
			"phone": phone,
			"spa_type": spa_type,
			"booking_date": booking_date,
			"booking_time": booking_time,
			"notes": notes,
			"status": "Scheduled",
		}
	)
	booking.insert(ignore_permissions=True)

	return {"status": "Success", "name": booking.name}


@frappe.whitelist()
def get_spa_bookings(date=None, from_date=None, to_date=None):
	"""
	Two calling shapes from the frontend:
	  - list view:     { date: <single date> }
	  - calendar view: { from_date: <start>, to_date: <end> }
	"""

	filters = {}
	if date:
		filters["booking_date"] = date
	elif from_date and to_date:
		filters["booking_date"] = ["between", [from_date, to_date]]

	return frappe.get_all(
		"Spa Booking",
		filters=filters,
		fields=[
			"name",
			"client_name",
			"phone",
			"spa_type",
			"booking_date",
			"booking_time",
			"status",
			"notes",
		],
		order_by="booking_date asc, booking_time asc",
	)


@frappe.whitelist()
def update_spa_booking_status(booking_name, status):
	frappe.db.set_value("Spa Booking", booking_name, "status", status)
	return {"status": "Success"}
