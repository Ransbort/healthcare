# healthcare/healthcare/page/cashier_portal/cashier_portal.py
#
# Backend for the Cashier Portal desk page.
# Path must match the JS calls exactly:
#   healthcare.healthcare.page.cashier_portal.cashier_portal.<method>

import frappe
from frappe import _
from frappe.utils import flt, nowdate, getdate
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice, make_delivery_note


# ---------------------------------------------------------------------------
# NOTE ON DEPARTMENT CLASSIFICATION
# ---------------------------------------------------------------------------
# The portal needs to bucket invoices into Other / Pharmacy / Laboratory /
# Rehabilitation. This assumes a custom Select field on Sales Invoice AND
# Sales Order called `custom_department` with options:
#   Pharmacy, Laboratory, Rehabilitation   (blank/other -> "Other Invoices" tab)
#
# front_desk.py's _create_consultation_invoice() tags its invoices
# custom_department="Consultation" - there's no dedicated tab for that here,
# so those fall into "Other Invoices" along with anything else untagged
# (see the exclude_departments branch in _get_department_invoices below and
# the "other_invoices" query in get_all_pending_payments).
#
# If you already tag department differently (e.g. by Item Group, Cost Center,
# or Healthcare "Medical Department" link), just change the filters in
# get_patient_data / get_customer_data below - the rest of the file doesn't
# care how the bucket was decided.
DEPARTMENT_FIELD = "custom_department"

# Inpatient invoices are a separate case from the DEPARTMENT_FIELD scheme
# above - inpatient_record.create_invoice_for_inpatient() never sets
# custom_department, so these are identified instead by carrying a Sales
# Invoice Item whose reference_dt is one of these two child doctypes (the
# same two types that function tags, and the same approach
# sports_complex/page/cashier/cashier.py's own get_inpatient_pending_payments()
# uses independently for its own Cashier page). See _get_inpatient_invoices()
# below - and note _get_department_invoices()'s "Other Invoices" bucket has
# to explicitly exclude these names, since an untagged custom_department
# would otherwise put them there too.
INPATIENT_REFERENCE_DOCTYPES = ["Inpatient Record Item", "Inpatient Occupancy"]


def _notify(event, payload):
    """Broadcast a realtime event to everyone listening in this site.
    Kept as a local copy (rather than importing the private helper from
    front_desk.py) so this file doesn't take on a cross-page dependency
    on another page's private function."""
    frappe.publish_realtime(event=event, message=payload)


@frappe.whitelist()
def get_server_today():
    """Same rationale as front_desk.get_server_today() — the cashier's
    browser can be in a different timezone than the site, so default
    all date fields here to the site's own nowdate() rather than the
    browser's local clock."""
    return nowdate()


@frappe.whitelist()
def get_patient_data(patient_id):
    if not frappe.db.exists("Patient", patient_id):
        frappe.throw(_("Patient {0} not found").format(patient_id))

    patient = frappe.get_doc("Patient", patient_id).as_dict()

    inpatient_invoices = _get_inpatient_invoices(patient_id, "patient")
    other_invoices = _get_department_invoices(
        patient_id, "patient", exclude_departments=True,
        exclude_invoice_names=[inv["name"] for inv in inpatient_invoices],
    )
    laboratory_invoices = _get_department_invoices(patient_id, "patient", department="Laboratory")
    rehabilitation_invoices = _get_department_invoices(patient_id, "patient", department="Rehabilitation")
    pharmacy_orders = _get_pharmacy_orders(patient_id, "patient")
    payments = _get_payment_history(patient_id, "Patient")

    return {
        "patient": patient,
        "other_invoices": other_invoices,
        "laboratory_invoices": laboratory_invoices,
        "rehabilitation_invoices": rehabilitation_invoices,
        "pharmacy_orders": pharmacy_orders,
        "inpatient_invoices": inpatient_invoices,
        "payments": payments,
    }


@frappe.whitelist()
def get_customer_data(customer_id):
    if not frappe.db.exists("Customer", customer_id):
        frappe.throw(_("Customer {0} not found").format(customer_id))

    customer = frappe.get_doc("Customer", customer_id).as_dict()

    inpatient_invoices = _get_inpatient_invoices(customer_id, "customer")
    other_invoices = _get_department_invoices(
        customer_id, "customer", exclude_departments=True,
        exclude_invoice_names=[inv["name"] for inv in inpatient_invoices],
    )
    laboratory_invoices = _get_department_invoices(customer_id, "customer", department="Laboratory")
    rehabilitation_invoices = _get_department_invoices(customer_id, "customer", department="Rehabilitation")
    pharmacy_orders = _get_pharmacy_orders(customer_id, "customer")
    payments = _get_payment_history(customer_id, "Customer")

    return {
        "customer": customer,
        "other_invoices": other_invoices,
        "laboratory_invoices": laboratory_invoices,
        "rehabilitation_invoices": rehabilitation_invoices,
        "pharmacy_orders": pharmacy_orders,
        "inpatient_invoices": inpatient_invoices,
        "payments": payments,
    }


def _get_customer_for_patient(patient_id):
    """Sales Order and Payment Entry are only ever linked to a Customer, not
    a Patient (that link only exists on Sales Invoice via the healthcare
    domain). So when the portal is searching 'by Patient', we need the
    Patient's linked Customer to find their orders/payments at all -
    filtering those doctypes directly on `patient` silently returns nothing."""
    customer = frappe.db.get_value("Patient", patient_id, "customer")
    if not customer:
        frappe.throw(
            _("Patient {0} has no linked Customer - cannot look up orders or payments").format(patient_id)
        )
    return customer


def _party_filters(party_id, party_type, doctype="Sales Invoice"):
    """party_type is 'patient' or 'customer' (lowercase, matches search_type).

    doctype matters: Sales Invoice can carry a real `patient` link (healthcare
    domain field), but Sales Order and Payment Entry cannot - those must
    always be filtered by `customer`, so a patient search has to resolve to
    the linked customer first.
    """
    if party_type == "patient":
        if doctype == "Sales Invoice":
            return {"patient": party_id}
        return {"customer": _get_customer_for_patient(party_id)}
    return {"customer": party_id}


def _get_department_invoices(party_id, party_type, department=None, exclude_departments=False,
                              exclude_invoice_names=None):
    filters = {
        "docstatus": 1,
        "outstanding_amount": [">", 0],
    }
    filters.update(_party_filters(party_id, party_type, doctype="Sales Invoice"))

    if department:
        filters[DEPARTMENT_FIELD] = department
    elif exclude_departments:
        # "Consultation" has no dedicated bucket - it lands here in
        # "Other Invoices" along with anything genuinely untagged.
        filters[DEPARTMENT_FIELD] = ["in", ["", "Other", "Consultation", None]]
        # Inpatient invoices are untagged too (see INPATIENT_REFERENCE_
        # DOCTYPES above) - without this they'd land here as well as in
        # their own Inpatient tab. Callers pass the names their own
        # _get_inpatient_invoices() call already found for this same
        # party, so this never re-runs that query.
        if exclude_invoice_names:
            filters["name"] = ["not in", exclude_invoice_names]

    invoices = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=[
            "name", "posting_date", "due_date", "status",
            "outstanding_amount", "grand_total", "currency",
        ],
        order_by="posting_date desc",
    )
    return invoices


def _get_inpatient_invoices(party_id=None, party_type=None):
    """Submitted Sales Invoices with something still outstanding that carry
    at least one Inpatient Ward charge - identified by a line whose
    reference_dn is one of INPATIENT_REFERENCE_DOCTYPES, the same
    reference-based approach used throughout this admission's billing (see
    get_inpatient_invoices() in healthcare/doctype/inpatient_record/
    inpatient_record.py and get_inpatient_pending_payments() in
    sports_complex/page/cashier/cashier.py - this is a third, independent
    copy of the same idea for this portal, kept local rather than
    cross-app imported for the same reason cashier.py gives its own copy).

    Pass party_id/party_type (same 'patient'/'customer' + id convention as
    _party_filters above) to scope this to one patient or customer; leave
    both None for the portal-wide queue (get_all_pending_payments).
    """
    sii = frappe.qb.DocType("Sales Invoice Item")
    si = frappe.qb.DocType("Sales Invoice")

    query = (
        frappe.qb.from_(si)
        .join(sii)
        .on(sii.parent == si.name)
        .select(si.name)
        .where(
            (si.docstatus == 1)
            & (si.outstanding_amount > 0)
            & (sii.reference_dt.isin(INPATIENT_REFERENCE_DOCTYPES))
        )
        .distinct()
    )
    if party_id:
        for field, value in _party_filters(party_id, party_type, doctype="Sales Invoice").items():
            query = query.where(getattr(si, field) == value)

    invoice_names = [row[0] for row in query.run()]
    if not invoice_names:
        return []

    return frappe.get_all(
        "Sales Invoice",
        filters={"name": ["in", invoice_names]},
        fields=[
            "name", "posting_date", "due_date", "status",
            "outstanding_amount", "grand_total", "currency",
            "patient", "patient_name", "customer", "customer_name",
        ],
        order_by="posting_date desc",
    )


def _get_pharmacy_orders(party_id, party_type):
    """Pharmacy items are picked at POS as a Sales Order, invoiced+paid at the
    counter. We show open/partially-billed orders here (per_billed < 100)."""
    filters = {
        "docstatus": 1,
        DEPARTMENT_FIELD: "Pharmacy",
        "per_billed": ["<", 100],
    }
    filters.update(_party_filters(party_id, party_type, doctype="Sales Order"))

    orders = frappe.get_all(
        "Sales Order",
        filters=filters,
        fields=[
            "name", "transaction_date as date", "delivery_date",
            "per_billed", "grand_total", "currency",
        ],
        order_by="transaction_date desc",
    )
    return orders


def _get_payment_history(party_id, party_type):
    """Payment Entry only ever has party_type 'Customer' in ERPNext - there's
    no 'Patient' party type - so a patient-based lookup must resolve to the
    linked customer first, same as pharmacy orders above."""
    if party_type == "Patient":
        customer = _get_customer_for_patient(party_id)
    else:
        customer = party_id

    payments = frappe.get_all(
        "Payment Entry",
        filters={
            "party_type": "Customer",
            "party": customer,
            "docstatus": 1,
        },
        fields=[
            "name", "posting_date", "mode_of_payment", "reference_no",
            "reference_date", "paid_amount", "remarks", "owner",
        ],
        order_by="posting_date desc, creation desc",
    )

    # Pull the linked invoice numbers for display (Payment Entry Reference child table)
    for p in payments:
        refs = frappe.get_all(
            "Payment Entry Reference",
            filters={"parent": p["name"]},
            fields=["reference_name"],
        )
        p["invoices"] = ", ".join(r["reference_name"] for r in refs) if refs else ""

    return payments

def _attach_party_names(rows, id_field, doctype):
	"""Sales Order doesn't carry patient_name (only custom_patient, the
	Patient ID) - so for pharmacy orders we need a second lookup to turn
	those IDs into display names. Sales Invoice already has patient_name
	and customer_name as real fields, so this is a no-op for those rows
	(id_field won't be missing there), it's really just for the pharmacy
	order case below.
	"""
	ids = list({r.get(id_field) for r in rows if r.get(id_field)})
	if not ids:
		return rows
	names = frappe.db.get_all(
		doctype,
		filters={"name": ["in", ids]},
		fields=["name", "patient_name" if doctype == "Patient" else "customer_name"],
	)
	name_map = {n["name"]: n.get("patient_name") or n.get("customer_name") for n in names}
	for r in rows:
		if r.get(id_field):
			r["party_display_name"] = name_map.get(r[id_field], r[id_field])
	return rows


@frappe.whitelist()
def get_all_pending_payments():
	"""Global (not party-scoped) view of every outstanding invoice/order,
	bucketed the same way as get_patient_data/get_customer_data, so the
	cashier can work a queue without knowing who to search for first.
	"""
	base_invoice_fields = [
		"name", "posting_date", "due_date", "status",
		"outstanding_amount", "grand_total", "currency",
		"patient", "patient_name", "customer", "customer_name",
	]

	inpatient_invoices = _get_inpatient_invoices()

	other_filters = {
		"docstatus": 1,
		"outstanding_amount": [">", 0],
		# "Consultation" has no dedicated bucket - it lands here
		# along with anything genuinely untagged.
		DEPARTMENT_FIELD: ["in", ["", "Other", "Consultation", None]],
	}
	if inpatient_invoices:
		# Same exclusion _get_department_invoices() applies per-party -
		# inpatient invoices are untagged, so without this they'd land
		# here too, alongside their own Inpatient bucket.
		other_filters["name"] = ["not in", [inv["name"] for inv in inpatient_invoices]]

	other_invoices = frappe.get_all(
		"Sales Invoice",
		filters=other_filters,
		fields=base_invoice_fields,
		order_by="posting_date desc",
	)

	laboratory_invoices = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": [">", 0], DEPARTMENT_FIELD: "Laboratory"},
		fields=base_invoice_fields,
		order_by="posting_date desc",
	)

	rehabilitation_invoices = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": [">", 0], DEPARTMENT_FIELD: "Rehabilitation"},
		fields=base_invoice_fields,
		order_by="posting_date desc",
	)

	pharmacy_orders = frappe.get_all(
		"Sales Order",
		filters={"docstatus": 1, DEPARTMENT_FIELD: "Pharmacy", "per_billed": ["<", 100]},
		fields=[
			"name", "transaction_date as date", "delivery_date",
			"per_billed", "grand_total", "currency",
			"customer", "customer_name", "custom_patient",
		],
		order_by="transaction_date desc",
	)
	pharmacy_orders = _attach_party_names(pharmacy_orders, "custom_patient", "Patient")

	return {
		"other_invoices": other_invoices,
		"laboratory_invoices": laboratory_invoices,
		"rehabilitation_invoices": rehabilitation_invoices,
		"pharmacy_orders": pharmacy_orders,
		"inpatient_invoices": inpatient_invoices,
	}


@frappe.whitelist()
def get_invoice_items(invoice_name, doctype="Sales Invoice"):
    doc = frappe.get_doc(doctype, invoice_name)
    items = []
    total = 0

    for item in doc.items:
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description if item.description != item.item_name else None,
            "qty": item.qty,
            "rate": item.rate,
            "amount": item.amount,
        })
        total += flt(item.amount)

    return {"items": items, "total": total}


@frappe.whitelist()
def get_payment_methods():
    methods = frappe.get_all(
        "Mode of Payment",
        filters={"enabled": 1},
        fields=["name", "type"],
        order_by="name",
    )
    return methods


@frappe.whitelist()
def create_payment_entry(invoice_name, mode_of_payment, remarks=None, reference_no=None, reference_date=None):
    invoice = frappe.get_doc("Sales Invoice", invoice_name)

    pe = get_payment_entry("Sales Invoice", invoice_name)
    pe.mode_of_payment = mode_of_payment
    pe.paid_amount = invoice.outstanding_amount
    pe.received_amount = invoice.outstanding_amount

    if remarks:
        pe.remarks = remarks
    if reference_no:
        pe.reference_no = reference_no
    if reference_date:
        pe.reference_date = reference_date
    else:
        pe.reference_no = pe.reference_no or invoice_name
        pe.reference_date = pe.reference_date or nowdate()

    pe.insert(ignore_permissions=True)
    pe.submit()

    _notify("queue_update", {
        "department": "front_desk",
        "message": f"Payment received for {invoice_name}",
        "encounter": None,
    })

    # Nurse Station's Admitted Patients tab shows each admission's own
    # outstanding balance (get_admitted_patients() in
    # healthcare/page/nurse_station/nurse_station.py) but only refreshes
    # it on page load/its own actions - a payment collected here on the
    # Inpatient tab would otherwise sit stale on any Nurse Station
    # already open. That page already listens for this exact
    # department="nurse" queue_update event (on_page_load in
    # nurse_station.js calls loadAll(), which includes
    # loadAdmittedPatients(), on every one), so reusing it is what makes
    # the balance there update live - no polling needed. Gated on this
    # actually being an inpatient invoice (carrying a line referencing
    # Inpatient Record Item/Inpatient Occupancy - see
    # INPATIENT_REFERENCE_DOCTYPES above) so a Lab/Pharmacy/Rehab/Other
    # payment doesn't needlessly nudge every open Nurse Station.
    if frappe.db.exists(
        "Sales Invoice Item",
        {"parent": invoice_name, "reference_dt": ["in", INPATIENT_REFERENCE_DOCTYPES]},
    ):
        _notify("queue_update", {
            "department": "nurse",
            "message": f"Payment received for {invoice_name}",
        })

    return {"status": "Success", "name": pe.name}


@frappe.whitelist()
def create_invoice_and_payment_from_order(order_name, mode_of_payment, remarks=None,
                                           reference_no=None, reference_date=None):
    """Pharmacy flow: Sales Order -> Sales Invoice -> Payment Entry -> Delivery Note."""
    so = frappe.get_doc("Sales Order", order_name)

    # 1. Sales Invoice from the order
    si = make_sales_invoice(order_name)

    # make_sales_invoice() only maps the standard mapper fields - custom
    # fields like custom_department don't cross over automatically, so the
    # resulting invoice would fall into "Other Invoices" on the Cashier
    # Portal instead of Pharmacy. Carry them over explicitly.
    si.custom_department = so.get("custom_department")
    si.custom_invoice_from = so.get("custom_invoice_from")

    si.insert(ignore_permissions=True)
    si.submit()

    # 2. Payment Entry against the new invoice
    pe = get_payment_entry("Sales Invoice", si.name)
    pe.mode_of_payment = mode_of_payment
    pe.paid_amount = si.outstanding_amount
    pe.received_amount = si.outstanding_amount

    if remarks:
        pe.remarks = remarks
    if reference_no:
        pe.reference_no = reference_no
    if reference_date:
        pe.reference_date = reference_date
    else:
        pe.reference_no = pe.reference_no or si.name
        pe.reference_date = pe.reference_date or nowdate()

    pe.insert(ignore_permissions=True)
    pe.submit()

    # 3. Delivery Note so stock moves out against the order
    dn = make_delivery_note(order_name)
    dn.insert(ignore_permissions=True)
    dn.submit()

    _notify("queue_update", {
        "department": "front_desk",
        "message": f"Pharmacy order {order_name} paid and dispatched",
        "encounter": None,
    })

    return {
        "status": "Success",
        "invoice_name": si.name,
        "payment_name": pe.name,
        "delivery_note_name": dn.name,
    }


@frappe.whitelist()
def get_print_content(doctype, docname):
    html = frappe.get_print(doctype, docname, print_format=None)
    return {"html": html}


@frappe.whitelist()
def get_daily_transactions(cashier, transaction_date):
    payments = frappe.get_all(
        "Payment Entry",
        filters={
            "owner": cashier,
            "posting_date": getdate(transaction_date),
            "docstatus": 1,
        },
        fields=[
            "name", "posting_date", "party", "party_name", "mode_of_payment",
            "reference_no", "paid_amount", "docstatus", "owner",
        ],
        order_by="creation asc",
    )

    for p in payments:
        refs = frappe.get_all(
            "Payment Entry Reference",
            filters={"parent": p["name"]},
            fields=["reference_name"],
        )
        p["invoices"] = ", ".join(r["reference_name"] for r in refs) if refs else ""
        # posting_time isn't on Payment Entry by default; use creation time instead
        creation = frappe.db.get_value("Payment Entry", p["name"], "creation")
        p["posting_time"] = creation.strftime("%I:%M %p") if creation else ""

    total_amount = sum(flt(p["paid_amount"]) for p in payments)

    return {
        "transactions": payments,
        "total_count": len(payments),
        "total_amount": total_amount,
    }


@frappe.whitelist()
def get_daily_transactions_print(cashier, transaction_date, transactions=None):
    import json
    if isinstance(transactions, str):
        transactions = json.loads(transactions)

    cashier_name = frappe.db.get_value("User", cashier, "full_name") or cashier
    total = sum(flt(t.get("paid_amount")) for t in (transactions or []))

    rows = "".join(f"""
        <tr>
            <td>{i + 1}</td>
            <td>{t.get('name')}</td>
            <td>{t.get('posting_time', '')}</td>
            <td>{t.get('party_name') or t.get('party')}</td>
            <td>{t.get('invoices', '')}</td>
            <td>{t.get('mode_of_payment', '')}</td>
            <td>{t.get('reference_no') or '-'}</td>
            <td style="text-align:right">{frappe.utils.fmt_money(t.get('paid_amount'), currency=frappe.defaults.get_global_default('currency'))}</td>
        </tr>
    """ for i, t in enumerate(transactions or []))

    html = f"""
        <html>
        <head>
            <title>Daily Transactions - {transaction_date}</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ border: 1px solid #ccc; padding: 6px 8px; font-size: 12px; }}
                th {{ background: #f0f0f0; text-align: left; }}
                .total-row td {{ font-weight: bold; }}
            </style>
        </head>
        <body>
            <h2>Daily Transactions Report</h2>
            <p><strong>Cashier:</strong> {cashier_name}<br>
               <strong>Date:</strong> {transaction_date}</p>
            <table>
                <thead>
                    <tr>
                        <th>#</th><th>Payment ID</th><th>Time</th><th>Party</th>
                        <th>Invoices</th><th>Method</th><th>Ref No</th><th>Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                    <tr class="total-row">
                        <td colspan="7" style="text-align:right">GRAND TOTAL:</td>
                        <td style="text-align:right">{frappe.utils.fmt_money(total, currency=frappe.defaults.get_global_default('currency'))}</td>
                    </tr>
                </tbody>
            </table>
        </body>
        </html>
    """

    return {"html": html}
