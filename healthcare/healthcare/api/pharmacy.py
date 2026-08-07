# Copyright (c) 2026, Ransbort and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _

# =============================================
# NOTIFICATION HELPER
# =============================================

def _notify(event, payload):
	"""Broadcast a realtime event to everyone listening in this site.
	Thin wrapper around frappe.publish_realtime so every caller in this
	module sends notifications the same way, without needing to import
	frappe.publish_realtime directly everywhere."""
	frappe.publish_realtime(event=event, message=payload)


def notify_new_medication_request(doc, method=None):
	"""Hooked on Medication Request on_submit. Pings Pharmacy POS
	listeners so a newly-prescribed medication shows up (with a sound)
	without the pharmacist needing to poll or manually reload.
	"""
	patient_label = doc.get("patient_name") or doc.get("patient") or "Unknown patient"

	_notify("queue_update", {
		"department": "pharmacy",
		"message": f"New prescription for {patient_label}",
		"medication_request": doc.name,
	})

# =============================================
# PHARMACY SETTINGS
# =============================================

@frappe.whitelist()
def get_pharmacy_settings():
	"""Return the currently configured Pharmacy Item Group so the
	Pharmacy POS front-end can display/edit it in its settings panel,
	and so get_pos_medications() below has a documented single source
	of truth to fall back on when no item_group is passed explicitly."""
	return {
		"item_group": frappe.db.get_single_value(
			"Healthcare Settings", "pharmacy_item_group"
		)
	}


@frappe.whitelist()
def set_pharmacy_item_group(item_group):
	"""Persist the Item Group used to populate the Pharmacy POS grid's
	walk-in/OTC section (see get_pos_medications()). Validates the
	Item Group actually exists before saving, since this value is used
	directly in a SQL WHERE clause downstream with no further checks."""
	if not frappe.db.exists("Item Group", item_group):
		frappe.throw(_("Item Group {0} does not exist").format(item_group))

	frappe.db.set_single_value(
		"Healthcare Settings", "pharmacy_item_group", item_group
	)
	frappe.db.commit()


# =============================================
# POS MEDICATIONS GRID
# =============================================

@frappe.whitelist()
def get_pos_medications(item_group=None):
	"""
	Single optimized call for the Pharmacy POS grid.

	Two sources, unioned:
	1. Medication -> Medication Linked Item -> Item (prescription-linked drugs,
	   richest metadata straight from the Medication doctype)
	2. Item where item_group = <configured Pharmacy Item Group> and not
	   already covered by #1 (walk-in/OTC sales - no consultation or
	   prescription required). custom_is_medication distinguishes an actual
	   drug (paracetamol, amoxicillin) from a non-drug Pharmacy item (gloves,
	   syringes, cotton, bandages) so the frontend can style them differently.
	"""

	item_group = item_group or frappe.db.get_single_value(
		"Healthcare Settings", "pharmacy_item_group"
	)

	if not item_group:
		frappe.throw(_("Pharmacy Item Group is not configured. Please set it up first."))

	medications = frappe.db.sql(
		"""
		SELECT
			med.name AS medication_name,
			med.generic_name AS generic_name,
			med.strength AS strength,
			med.strength_uom AS strength_uom,
			med.medication_class AS medication_class,
			med.abbr AS abbr,
			med.dosage_form AS dosage_form,
			mli.item AS item_code,
			mli.stock_uom AS stock_uom,
			item.image AS image,
			item.standard_rate AS standard_rate,
			ip.price_list_rate AS price_list_rate,
			COALESCE(stock.total_qty, 0) AS stock_qty
		FROM `tabMedication` med
		INNER JOIN `tabMedication Linked Item` mli
			ON mli.parent = med.name
		INNER JOIN `tabItem` item
			ON item.name = mli.item
		LEFT JOIN `tabItem Price` ip
			ON ip.item_code = mli.item
			AND ip.price_list = med.price_list
		LEFT JOIN (
			SELECT item_code, SUM(actual_qty) AS total_qty
			FROM `tabBin`
			GROUP BY item_code
		) stock
			ON stock.item_code = mli.item
		WHERE med.disabled = 0
		ORDER BY med.generic_name ASC
		""",
		as_dict=True,
	)

	# de-dupe: a Medication can have more than one Medication Linked Item
	# row (e.g. different pack sizes of the same drug) - only the first
	# one encountered is surfaced to the POS grid as that medication's
	# purchasable entry.
	seen = set()
	result = []

	for med in medications:
		if med.medication_name in seen:
			continue
		seen.add(med.medication_name)

		rate = med.price_list_rate or med.standard_rate or 0

		result.append(
			{
				"medication_name": med.medication_name,
				"generic_name": med.generic_name,
				"strength": med.strength,
				"strength_uom": med.strength_uom,
				"medication_class": med.medication_class,
				"abbr": med.abbr,
				"item_code": med.item_code,
				"rate": rate,
				"stock_uom": med.stock_uom or "Nos",
				"stock_qty": med.stock_qty or 0,
				"dosage_form": med.dosage_form or "",
				"image": med.image or "",
				"is_medication": True,
			}
		)

	# Items already surfaced via the Medication table above must not be
	# listed a second time when we scan the raw Item Group below.
	linked_item_codes = {r["item_code"] for r in result if r["item_code"]}

	default_price_list = (
		frappe.db.get_single_value("Selling Settings", "selling_price_list")
		or "Standard Selling"
	)

	pharmacy_items = frappe.db.sql(
		"""
		SELECT
			item.item_code AS item_code,
			item.item_name AS item_name,
			item.stock_uom AS stock_uom,
			item.image AS image,
			item.standard_rate AS standard_rate,
			item.custom_is_medication AS is_medication,
			item.custom_medication_class AS medication_class,
			item.custom_strength AS strength,
			item.custom_strength_uom AS strength_uom,
			item.custom_dosage_form AS dosage_form,
			ip.price_list_rate AS price_list_rate,
			COALESCE(stock.total_qty, 0) AS stock_qty
		FROM `tabItem` item
		LEFT JOIN `tabItem Price` ip
			ON ip.item_code = item.item_code
			AND ip.price_list = %(price_list)s
			AND ip.selling = 1
		LEFT JOIN (
			SELECT item_code, SUM(actual_qty) AS total_qty
			FROM `tabBin`
			GROUP BY item_code
		) stock
			ON stock.item_code = item.item_code
		WHERE item.item_group = %(item_group)s
			AND item.disabled = 0
		ORDER BY item.item_name ASC
		""",
		{"price_list": default_price_list, "item_group": item_group},
		as_dict=True,
	)

	for item in pharmacy_items:
		if item.item_code in linked_item_codes:
			continue

		rate = item.price_list_rate or item.standard_rate or 0

		result.append(
			{
				"medication_name": None,
				"generic_name": item.item_name,
				"strength": item.strength,
				"strength_uom": item.strength_uom,
				"medication_class": item.medication_class,
				"abbr": None,
				"item_code": item.item_code,
				"rate": rate,
				"stock_uom": item.stock_uom or "Nos",
				"stock_qty": item.stock_qty or 0,
				"dosage_form": item.dosage_form or "",
				"image": item.image or "",
				"is_medication": bool(item.is_medication),
			}
		)

	return result


# =============================================
# BARCODE LOOKUP
# =============================================

@frappe.whitelist()
def get_item_by_barcode(barcode):
	"""
	Resolve a scanned barcode to an item_code.
	Used by process_barcode() in pharmacy_pos.js for the barcode-scanner
	keypress buffer. Returns the item_code string, or None if not found.
	"""

	if not barcode:
		return None

	barcode = barcode.strip()

	item_code = frappe.db.get_value("Item Barcode", {"barcode": barcode}, "parent")

	return item_code


# =============================================
# MEDICATION REQUEST BILLING UPDATES
# =============================================

@frappe.whitelist()
def update_medication_requests(updates, allow_oversell=False):
	"""
	Bump qty_invoiced on each Medication Request after a Sales Order is
	created + submitted from the POS. Called from process_checkout() after
	frappe.client.submit succeeds, so a failure here must never roll back
	the already-submitted Sales Order -- errors are raised back to the
	frontend, which shows a non-blocking warning (see checkout try/catch).

	Args:
		updates: JSON string or list of {"name": <Medication Request name>, "qty": <int>}
		allow_oversell: if truthy, skip the "don't exceed remaining qty" guard
			(matches Healthcare Settings.allow_oversell_medication)

	IMPORTANT: each successful update is committed immediately (frappe.db.commit())
	inside the loop, rather than only at the end of the whitelisted call. If one
	Medication Request in the batch fails and we later call frappe.throw() to
	surface the aggregated errors, that throw raises an exception - and Frappe
	rolls back the *entire* request's uncommitted transaction on an unhandled
	exception. Without committing per-item, a single bad item at the end of a
	multi-item cart would silently wipe out the qty_invoiced/billing_status
	updates already applied to every other (successfully updated) Medication
	Request earlier in the same loop - even though their Sales Order had
	already been created and stock had already moved. Those medications would
	then still show billing_status = Pending/Partly Invoiced and get pulled
	back into the cart the next time "Load Prescriptions" runs for that
	patient, effectively double-counting an already-sold item.
	"""

	if isinstance(updates, str):
		updates = json.loads(updates)

	if isinstance(allow_oversell, str):
		allow_oversell = allow_oversell.lower() in ("1", "true", "yes")

	if not updates:
		return

	updated = []
	errors = []

	for update in updates:
		med_req_name = update.get("name")
		qty = frappe.utils.flt(update.get("qty"))

		# Skip malformed rows silently rather than failing the whole
		# batch over a missing name or a non-positive quantity.
		if not med_req_name or qty <= 0:
			continue

		try:
			med_req = frappe.get_doc("Medication Request", med_req_name)

			total_dispensable = (
				med_req.total_dispensable_quantity or med_req.quantity or 0
			)
			already_invoiced = med_req.qty_invoiced or 0
			remaining = total_dispensable - already_invoiced

			if not allow_oversell and qty > remaining:
				errors.append(
					_(
						"Medication Request {0}: tried to invoice {1}, only {2} remaining"
					).format(med_req_name, qty, remaining)
				)
				continue

			new_qty_invoiced = already_invoiced + qty
			med_req.db_set("qty_invoiced", new_qty_invoiced, update_modified=True)

			# Keep billing_status in sync with the new invoiced quantity
			if new_qty_invoiced >= total_dispensable:
				med_req.db_set("billing_status", "Fully Invoiced", update_modified=True)
			elif new_qty_invoiced > 0:
				med_req.db_set(
					"billing_status", "Partly Invoiced", update_modified=True
				)

			# Commit NOW, per-item. This is the fix: without this, a later
			# item's failure + the frappe.throw() below would roll back this
			# (and every other already-succeeded) update in the same request,
			# even though the underlying Sales Order/stock movement already
			# happened and can't be undone. Committing per-item makes each
			# Medication Request's billing state durable independent of what
			# happens to the rest of the batch.
			frappe.db.commit()

			updated.append(med_req_name)

		except Exception:
			# Only this item's partial writes (if any) get rolled back -
			# nothing committed by prior iterations is affected.
			frappe.db.rollback()
			frappe.log_error(
				title="Pharmacy POS: update_medication_requests failed",
				message=frappe.get_traceback(),
			)
			errors.append(_("Medication Request {0}: {1}").format(med_req_name, "update failed"))

	if errors:
		# Surface partial failures to the caller; JS catches this and shows
		# a non-blocking orange warning without rolling back the Sales Order.
		# Safe to throw here now - every successful update above has already
		# been committed independently, so this exception can only affect
		# whatever wasn't committed yet (i.e. nothing, since we commit inline).
		frappe.throw(
			_("Some Medication Requests could not be fully updated:<br>{0}").format(
				"<br>".join(errors)
			)
		)

	return {"updated": updated}
