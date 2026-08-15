// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Admission Order", {
	refresh: function (frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.status !== "Pending") {
			return;
		}

		if (frappe.user_roles.includes("Nursing User")) {
			frm.add_custom_button(__("Accept"), function () {
				frappe.confirm(
					__("Accept this admission order and create the Inpatient Record?"),
					function () {
						frappe.call({
							method:
								"healthcare.healthcare.doctype.admission_order.admission_order.accept_admission_order",
							args: { admission_order: frm.doc.name },
							freeze: true,
							freeze_message: __("Accepting Admission Order"),
							callback: function (r) {
								if (!r.exc) {
									frappe.show_alert({
										message: __("Admission accepted"),
										indicator: "green",
									});
									frm.reload_doc();
								}
							},
						});
					},
				);
			}).addClass("btn-primary");

			frm.add_custom_button(__("Reject"), function () {
				frappe.prompt(
					[
						{
							fieldname: "reason",
							label: __("Reason for Rejection"),
							fieldtype: "Small Text",
							reqd: 1,
						},
					],
					function (data) {
						frappe.call({
							method:
								"healthcare.healthcare.doctype.admission_order.admission_order.reject_admission_order",
							args: {
								admission_order: frm.doc.name,
								reason: data.reason,
							},
							freeze: true,
							freeze_message: __("Rejecting Admission Order"),
							callback: function (r) {
								if (!r.exc) {
									frm.reload_doc();
								}
							},
						});
					},
					__("Reject Admission Order"),
					__("Reject"),
				);
			});
		}
	},
});
