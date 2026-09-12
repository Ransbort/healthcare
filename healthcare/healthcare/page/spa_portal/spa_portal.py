# Copyright (c) 2026, Ransbort and contributors
# For license information, please see license.txt

"""
Backend for the Spa Portal page (page/spa_portal/spa_portal.js).

ASSUMPTIONS TO VERIFY:

- `Spa Type` doctype exists with fields: spa_type_name, enabled (Check),
  and a `durations` child table (Spa Type Duration) holding one row per
  duration/price tier: duration_minutes (0 = fixed/no duration options),
  rate, item (Link -> Item, billed on the invoice).
- `Spa Booking` doctype exists with fields: client_name, phone, spa_type
  (Link -> Spa Type), duration_minutes (Int, must match one of that Spa
  Type's duration rows), booking_date, booking_time, notes, status
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
from frappe.utils import add_days, cint, flt, get_first_day, get_last_day, getdate, nowdate, today


def _get_spa_type_duration(spa_type, duration_minutes):
	"""
	Look up the priced duration/tier row for a Spa Type. duration_minutes=0
	means "the fixed/no-duration-options tier". Throws if that Spa Type has
	no pricing configured for the requested duration.
	"""
	duration_minutes = cint(duration_minutes) or 0

	row = frappe.db.get_value(
		"Spa Type Duration",
		{"parent": spa_type, "parenttype": "Spa Type", "duration_minutes": duration_minutes},
		["rate", "item"],
		as_dict=True,
	)
	if not row:
		frappe.throw(
			_("Spa Type {0} has no pricing configured for duration {1} min").format(
				spa_type, duration_minutes
			)
		)
	return row


@frappe.whitelist()
def get_spa_type_durations(spa_type):
	"""
	Returns the duration/price tiers configured for a Spa Type, ordered by
	duration. Used by the portal to populate the duration selector once a
	Spa Type has been picked (add-service row and booking form).
	"""
	if not spa_type:
		return []

	return frappe.get_all(
		"Spa Type Duration",
		filters={"parent": spa_type, "parenttype": "Spa Type"},
		fields=["duration_minutes", "rate", "item"],
		order_by="duration_minutes asc",
	)


@frappe.whitelist()
def create_spa_invoice(spa_services, customer=None, patient=None, posting_date=None):
	"""
	spa_services: JSON string / list of
	  {"spa_type": <Spa Type name>, "duration_minutes": <int>, "qty": <int>}
	duration_minutes should be 0 (or omitted) for a spa type with a single
	fixed-price tier.
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
		duration_minutes = cint(service.get("duration_minutes")) or 0

		spa_type_name = frappe.db.get_value("Spa Type", spa_type, "spa_type_name")
		if not spa_type_name:
			frappe.throw(_("Spa Type {0} not found").format(spa_type))

		duration_row = _get_spa_type_duration(spa_type, duration_minutes)

		item_code = duration_row.item or spa_type
		rate = duration_row.rate or 0

		items.append(
			{
				"item_code": item_code,
				"item_name": spa_type_name,
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
def get_spa_invoices(date=None, to_date=None):
	filters = {"custom_invoice_from": "Spa", "docstatus": 1}
	if date and to_date:
		filters["posting_date"] = ["between", [date, to_date]]
	elif date:
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
def create_spa_booking(
	client_name, phone, spa_type, booking_date, booking_time, duration_minutes=0, notes=None
):
	if not (client_name and phone and spa_type and booking_date and booking_time):
		frappe.throw(_("Please fill in all required fields"))

	duration_minutes = cint(duration_minutes) or 0
	# Validates the duration against the Spa Type's configured tiers and
	# throws a clear error if it doesn't match one.
	_get_spa_type_duration(spa_type, duration_minutes)

	booking = frappe.get_doc(
		{
			"doctype": "Spa Booking",
			"client_name": client_name,
			"phone": phone,
			"spa_type": spa_type,
			"duration_minutes": duration_minutes,
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
			"duration_minutes",
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


def get_server_today():
	"""Same rationale as cashier_portal.get_server_today() - the browser's
	clock can be in a different timezone than the site, so default all
	date fields here to the site's own nowdate() rather than the
	browser's local clock. Matters more here than a plain single-day
	filter would suggest: get_spa_transactions() below uses this date to
	decide which Sun-Sat week or which calendar month a Weekly/Monthly
	report falls into."""
	return nowdate()


def _get_transaction_period_range(period, ref_date):
	"""
	Resolves a (period, from_date, to_date) window for the Transactions
	tab's Daily/Weekly/Monthly report, anchored on ref_date.

	Weekly uses a Sunday-start week to match the portal's own booking
	calendar (see spa_portal.js's cal-grid, dayNames = ['Sun', 'Mon', ...]) -
	getdate(...).weekday() is Monday=0..Sunday=6, so (weekday + 1) % 7
	gives how many days ref_date is *after* the most recent Sunday.
	"""
	ref_date = getdate(ref_date)
	period = period if period in ("Daily", "Weekly", "Monthly") else "Daily"

	if period == "Weekly":
		from_date = add_days(ref_date, -((ref_date.weekday() + 1) % 7))
		to_date = add_days(from_date, 6)
	elif period == "Monthly":
		from_date = get_first_day(ref_date)
		to_date = get_last_day(ref_date)
	else:
		from_date = to_date = ref_date

	return period, from_date, to_date


@frappe.whitelist()
def get_spa_transactions(period, ref_date):
	"""
	Returns Spa Sales Invoices (custom_invoice_from = "Spa") posted within
	the Daily/Weekly/Monthly window containing ref_date, for the
	Transactions tab. Sourced from Sales Invoices rather than Payment
	Entries (unlike cashier_portal.get_daily_transactions(), which is
	Payment-Entry-based) because a spa transaction is billed - and
	tracked here - as an invoice; get_spa_invoices() above already treats
	custom_invoice_from = "Spa" Sales Invoices as this portal's ledger.
	"""
	period, from_date, to_date = _get_transaction_period_range(period, ref_date)

	invoices = frappe.get_all(
		"Sales Invoice",
		filters={
			"custom_invoice_from": "Spa",
			"docstatus": 1,
			"posting_date": ["between", [from_date, to_date]],
		},
		fields=[
			"name",
			"posting_date",
			"customer",
			"customer_name",
			"patient",
			"patient_name",
			"grand_total",
			"outstanding_amount",
			"status",
			"creation",
		],
		order_by="posting_date asc, creation asc",
	)

	for inv in invoices:
		items = frappe.get_all(
			"Sales Invoice Item", filters={"parent": inv["name"]}, fields=["item_name"]
		)
		inv["services"] = ", ".join(i["item_name"] for i in items) if items else ""
		inv["posting_time"] = inv["creation"].strftime("%I:%M %p") if inv.get("creation") else ""
		inv["party_name"] = inv.get("patient_name") or inv.get("customer_name") or inv.get("customer")

	total_amount = sum(flt(i["grand_total"]) for i in invoices)
	outstanding_amount = sum(flt(i["outstanding_amount"]) for i in invoices)

	return {
		"period": period,
		"from_date": from_date,
		"to_date": to_date,
		"transactions": invoices,
		"total_count": len(invoices),
		"total_amount": total_amount,
		"paid_amount": total_amount - outstanding_amount,
		"outstanding_amount": outstanding_amount,
	}


@frappe.whitelist()
def get_spa_transactions_print(period, ref_date, transactions=None):
	"""Printable version of get_spa_transactions() - re-derives the same
	from_date/to_date window from (period, ref_date) rather than trusting
	client-supplied dates, then renders the transactions the caller
	already fetched (and may have had rendered on screen) into a
	print-ready HTML document, the same pattern cashier_portal.py's
	get_daily_transactions_print() uses."""
	if isinstance(transactions, str):
		transactions = json.loads(transactions)

	period, from_date, to_date = _get_transaction_period_range(period, ref_date)
	date_label = str(from_date) if from_date == to_date else f"{from_date} to {to_date}"
	currency = frappe.defaults.get_global_default("currency")
	total = sum(flt(t.get("grand_total")) for t in (transactions or []))

	rows = "".join(
		f"""
		<tr>
			<td>{i + 1}</td>
			<td>{t.get('name')}</td>
			<td>{t.get('posting_date')}</td>
			<td>{t.get('party_name', '')}</td>
			<td>{t.get('services', '')}</td>
			<td>{t.get('status', '')}</td>
			<td style="text-align:right">{frappe.utils.fmt_money(t.get('grand_total'), currency=currency)}</td>
		</tr>
		"""
		for i, t in enumerate(transactions or [])
	)

	html = f"""
		<html>
		<head>
			<title>Spa {period} Transactions - {date_label}</title>
			<style>
				body {{ font-family: Arial, sans-serif; padding: 20px; }}
				table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
				th, td {{ border: 1px solid #ccc; padding: 6px 8px; font-size: 12px; }}
				th {{ background: #f0f0f0; text-align: left; }}
				.total-row td {{ font-weight: bold; }}
			</style>
		</head>
		<body>
			<h2>Spa {period} Transactions Report</h2>
			<p><strong>Period:</strong> {date_label}</p>
			<table>
				<thead>
					<tr>
						<th>#</th><th>Invoice ID</th><th>Date</th><th>Customer/Patient</th>
						<th>Services</th><th>Status</th><th>Amount</th>
					</tr>
				</thead>
				<tbody>
					{rows}
					<tr class="total-row">
						<td colspan="6" style="text-align:right">GRAND TOTAL:</td>
						<td style="text-align:right">{frappe.utils.fmt_money(total, currency=currency)}</td>
					</tr>
				</tbody>
			</table>
		</body>
		</html>
	"""

	return {"html": html}
