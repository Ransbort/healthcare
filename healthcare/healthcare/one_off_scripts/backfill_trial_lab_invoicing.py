"""One-time backfill: repair Lab Test rows stuck between Requested and
Pending in the Laboratory Portal because of the trial-lab-panel bundling
bug fixed in sports_complex's create_trial_lab_panel() and
healthcare/healthcare/page/lab_portal/lab_portal.py.

BACKGROUND
----------
create_trial_lab_panel() creates one Lab Test per row in a trial's
required-lab panel, pointing each one's custom_invoice at the SAME Sales
Invoice that paid for the trial appointment's consultation fee
(Patient Appointment.consultation_invoice) - the trial's one check-in
payment is meant to cover vitals + this panel + the doctor visit as a
single bundled fee, so nothing about the panel should ever raise a
second bill.

That only works when consultation_invoice is actually set. When a
Trialist appointment's consulting charge resolved to $0/unset at
check-in, Front Desk never raised a consultation invoice at all (see
front_desk.py's _finalize_checkin()), so consultation_invoice stayed
blank - and every Lab Test in that trial's panel got created with
custom_invoice blank too, looking exactly like an ordinary un-invoiced
lab request. It would sit in Laboratory Portal's Requested Labs tab, and
clicking Accept & Invoice on it would try to raise a brand new Sales
Invoice for a fee that was never actually meant to be charged - which
then crashed with a raw "already invoiced" error if the standard
Lab Test.invoiced flag was already set by some other means.

The fix (already applied to create_trial_lab_panel()/lab_portal.py)
marks a genuinely-free trial panel test invoiced=1 directly at creation,
with no invoice to link - Laboratory Portal now routes on that flag too,
so it lands in Pending Labs like a bundled paid one, just with nothing
owed ("Free" instead of "Paid"/"Unpaid"). That fix only applies to Lab
Tests created *after* it shipped. This script repairs the ones created
before it, split into two groups:

1. DEFINITELY SAFE TO FIX (applied automatically, unless dry_run=True):

   a) A trial Lab Test (sc_trial_appointment set) with custom_invoice
      blank, not yet invoiced, whose Patient Appointment now HAS a
      consultation_invoice - the bundling should have linked to it
      already. Backfills custom_invoice from the appointment directly -
      exactly what create_trial_lab_panel() would have done had the
      invoice existed at panel-creation time. No new invoice, just
      linking to the one that already exists and already covers it.

   b) A trial Lab Test with custom_invoice blank, not yet invoiced,
      whose Patient Appointment's consultation_invoice is ALSO blank -
      genuinely free, matching the policy the fix above now applies
      going forward. Marked invoiced=1 directly, nothing to link.

   c) Any direct-sourced Lab Test (trial or not) already marked
      invoiced=1 with custom_invoice blank, where a real SUBMITTED Sales
      Invoice actually exists referencing it (Sales Invoice Item with
      reference_dt="Lab Test", reference_dn=<this test>, docstatus=1) -
      the invoice exists, custom_invoice just never got linked to it
      (e.g. an earlier Accept & Invoice attempt crashed after the
      invoice submitted but before this app's own custom_invoice
      db_set() ran). Backfills custom_invoice from that invoice.

2. AMBIGUOUS - NEVER AUTO-FIXED, ONLY REPORTED:

   A direct-sourced, NON-trial Lab Test (sc_trial_appointment blank)
   already marked invoiced=1 with custom_invoice blank, where no
   submitted Sales Invoice referencing it can be found at all. Unlike a
   trial panel test, an ordinary direct request is never meant to be
   free - see lab_portal.create_lab_request()'s own docstring ("a direct
   request IS its own acceptance - so it's invoiced immediately"). This
   shouldn't be reachable in the first place; if it turns up, silently
   marking it "already handled" risks hiding a genuine billing gap, so
   it's only ever listed by name for manual review.

USAGE
-----
From the bench directory, dry run first (writes nothing, just reports):

    bench --site <sitename> execute \\
        healthcare.healthcare.one_off_scripts.backfill_trial_lab_invoicing.execute

Then apply the safe fixes:

    bench --site <sitename> execute \\
        healthcare.healthcare.one_off_scripts.backfill_trial_lab_invoicing.execute \\
        --kwargs "{'dry_run': False}"

Safe to run more than once - idempotent, only touches rows that still
match one of the safe conditions above.
"""

import frappe


def execute(dry_run=True):
	linked_from_appointment = _fix_trial_tests_with_appointment_invoice(dry_run)
	marked_free = _fix_trial_tests_genuinely_free(dry_run)
	linked_from_existing_invoice = _fix_any_test_with_findable_invoice(dry_run)
	ambiguous = _report_ambiguous_non_trial_tests(
		already_fixed={*linked_from_existing_invoice}
	)

	print("")
	print("=" * 72)
	print("Trial lab invoicing backfill - %s" % ("DRY RUN, nothing written" if dry_run else "APPLIED"))
	print("=" * 72)

	print("\n[1a] Fixed - linked to appointment's existing consultation invoice: %d" % len(linked_from_appointment))
	for name in linked_from_appointment:
		print("  - %s" % name)

	print("\n[1b] Fixed - genuinely free (no consultation invoice), marked invoiced: %d" % len(marked_free))
	for name in marked_free:
		print("  - %s" % name)

	print("\n[1c] Fixed - linked to a findable existing Sales Invoice: %d" % len(linked_from_existing_invoice))
	for name in linked_from_existing_invoice:
		print("  - %s" % name)

	print("\n[2] NOT auto-fixed - non-trial, invoiced=1, no invoice findable.")
	print("    Review by hand: %d" % len(ambiguous))
	for name in ambiguous:
		print("  - %s" % name)

	print("")
	if dry_run:
		total_safe = len(linked_from_appointment) + len(marked_free) + len(linked_from_existing_invoice)
		print("This was a dry run - nothing was written. Re-run with")
		print("dry_run=False to apply the %d safe fixes above." % total_safe)
	else:
		frappe.db.commit()
		print("Committed.")

	return {
		"linked_from_appointment": linked_from_appointment,
		"marked_free": marked_free,
		"linked_from_existing_invoice": linked_from_existing_invoice,
		"ambiguous_needs_review": ambiguous,
	}


def _stuck_trial_tests():
	"""Trial Lab Tests (sc_trial_appointment set) that are direct-sourced,
	not yet Completed, custom_invoice blank, and not yet invoiced -
	exactly the rows the original bug could have left behind."""
	return frappe.get_all(
		"Lab Test",
		filters={
			"prescription": ["in", ["", None]],
			"sc_trial_appointment": ["is", "set"],
			"custom_invoice": ["in", ["", None]],
			"invoiced": ["in", [0, None]],
			"status": ["!=", "Completed"],
		},
		fields=["name", "sc_trial_appointment"],
	)


def _fix_trial_tests_with_appointment_invoice(dry_run):
	fixed = []
	for row in _stuck_trial_tests():
		consultation_invoice = frappe.db.get_value(
			"Patient Appointment", row.sc_trial_appointment, "consultation_invoice"
		)
		if not consultation_invoice:
			continue
		fixed.append(row.name)
		if not dry_run:
			frappe.db.set_value("Lab Test", row.name, "custom_invoice", consultation_invoice, update_modified=False)
	return fixed


def _fix_trial_tests_genuinely_free(dry_run):
	fixed = []
	for row in _stuck_trial_tests():
		consultation_invoice = frappe.db.get_value(
			"Patient Appointment", row.sc_trial_appointment, "consultation_invoice"
		)
		if consultation_invoice:
			# Handled by _fix_trial_tests_with_appointment_invoice() instead.
			continue
		fixed.append(row.name)
		if not dry_run:
			frappe.db.set_value("Lab Test", row.name, "invoiced", 1, update_modified=False)
	return fixed


def _fix_any_test_with_findable_invoice(dry_run):
	"""Any direct-sourced Lab Test (trial or not) already invoiced=1 with
	custom_invoice blank, where a real submitted Sales Invoice actually
	references it - link it rather than leaving it unlinked."""
	rows = frappe.get_all(
		"Lab Test",
		filters={
			"prescription": ["in", ["", None]],
			"custom_invoice": ["in", ["", None]],
			"invoiced": 1,
		},
		fields=["name"],
	)

	fixed = []
	for row in rows:
		invoice = frappe.db.get_value(
			"Sales Invoice Item",
			{"reference_dt": "Lab Test", "reference_dn": row.name, "docstatus": 1},
			"parent",
		)
		if not invoice:
			continue
		fixed.append(row.name)
		if not dry_run:
			frappe.db.set_value("Lab Test", row.name, "custom_invoice", invoice, update_modified=False)
	return fixed


def _report_ambiguous_non_trial_tests(already_fixed):
	"""Direct-sourced, NON-trial Lab Tests still invoiced=1 with
	custom_invoice blank and no findable invoice after the fixes above -
	genuinely unexpected, left for manual review."""
	rows = frappe.get_all(
		"Lab Test",
		filters={
			"prescription": ["in", ["", None]],
			"sc_trial_appointment": ["in", ["", None]],
			"custom_invoice": ["in", ["", None]],
			"invoiced": 1,
		},
		fields=["name"],
	)
	return [row.name for row in rows if row.name not in already_fixed]
