// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["Admission Order"] = {
	add_fields: ["status"],
	get_indicator: function (doc) {
		const status_colors = {
			Pending: "orange",
			Accepted: "green",
			Rejected: "red",
			Cancelled: "grey",
		};
		return [__(doc.status), status_colors[doc.status] || "grey", "status,=," + doc.status];
	},
};
