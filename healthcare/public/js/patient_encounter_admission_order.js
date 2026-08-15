// Nurse-acceptance step for inpatient admissions.
//
// This file is additive only - it is loaded alongside the standard
// healthcare/healthcare/doctype/patient_encounter/patient_encounter.js via
// hooks.py's doctype_js, and does not modify that file. Server side,
// hooks.py's override_whitelisted_methods redirects the "Order Admission"
// dialog's call (still defined in patient_encounter.js, untouched) to
// admission_order.create_admission_order, so it creates a pending
// Admission Order instead of the Inpatient Record. This script only adds
// the UI around that: a headline while an order is pending, and a way to
// cancel it.
frappe.ui.form.on("Patient Encounter", {
	refresh: function (frm) {
		if (frm.doc.__islocal || frm.doc.docstatus !== 1) {
			return;
		}

		if (frm.doc.custom_pending_admission_order) {
			let admission_order = frm.doc.custom_pending_admission_order;
			let admission_order_link = `<a href="/app/admission-order/${admission_order}">${admission_order}</a>`;

			frm.dashboard.set_headline_alert(
				__("Admission order {0} is awaiting nurse acceptance.", [
					admission_order_link,
				]),
				"orange",
			);

			// patient_encounter.js's own refresh handler always adds
			// "Schedule Admission" while inpatient_status is unset - remove
			// it while an order is pending so a second one can't be ordered
			// (create_admission_order also guards against this server side).
			frm.remove_custom_button(__("Schedule Admission"));

			frm.add_custom_button(__("Cancel Admission Order"), function () {
				frappe.confirm(
					__("Cancel this pending admission order?"),
					function () {
						frappe.call({
							method: "frappe.client.cancel",
							args: {
								doctype: "Admission Order",
								name: admission_order,
							},
							freeze: true,
							callback: function (r) {
								if (!r.exc) {
									frm.reload_doc();
								}
							},
						});
					},
				);
			});
		}
	},
});
