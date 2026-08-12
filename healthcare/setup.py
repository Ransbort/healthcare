# isort: skip_file
import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpnext.setup.utils import insert_record

from healthcare.healthcare.workspace_installer import (
	workspace_installer,
	workspace_remover,
)


data = {
	"desktop_icons": [
		"Patient",
		"Patient Appointment",
		"Patient Encounter",
		"Lab Test",
		"Healthcare",
		"Vital Signs",
		"Clinical Procedure",
		"Inpatient Record",
		"Accounts",
		"Buying",
		"Stock",
		"HR",
		"ToDo",
	],
	"default_portal_role": "Patient",
	"restricted_roles": [
		"Healthcare Administrator",
		"LabTest Approver",
		"Laboratory User",
		"Nursing User",
		"Physician",
		"Patient",
	],
	"custom_fields": {
		"Sales Invoice": [
			{
				"fieldname": "patient",
				"label": "Patient",
				"fieldtype": "Link",
				"options": "Patient",
				"insert_after": "naming_series",
			},
			{
				"fieldname": "patient_name",
				"label": "Patient Name",
				"fieldtype": "Data",
				"fetch_from": "patient.patient_name",
				"insert_after": "patient",
				"read_only": True,
			},
			{
				"fieldname": "ref_practitioner",
				"label": "Referring Practitioner",
				"fieldtype": "Link",
				"options": "Healthcare Practitioner",
				"insert_after": "customer",
			},
			{
				"fieldname": "service_unit",
				"label": "Service Unit",
				"fieldtype": "Link",
				"options": "Healthcare Service Unit",
				"insert_after": "customer_name",
			},
			{
				"fieldname": "total_insurance_coverage_amount",
				"label": "Total Insurance Coverage Amount",
				"fieldtype": "Currency",
				"insert_after": "total",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "patient_payable_amount",
				"label": "Patient Payable Amount",
				"fieldtype": "Currency",
				"insert_after": "total_insurance_coverage_amount",
				"read_only": True,
				"no_copy": True,
			},
		],
		"Sales Invoice Item": [
			{
				"fieldname": "reference_dt",
				"label": "Reference DocType",
				"fieldtype": "Link",
				"options": "DocType",
				"insert_after": "edit_references",
			},
			{
				"fieldname": "reference_dn",
				"label": "Reference Name",
				"fieldtype": "Dynamic Link",
				"options": "reference_dt",
				"insert_after": "reference_dt",
			},
			{
				"fieldname": "practitioner",
				"label": "Practitioner",
				"fieldtype": "Link",
				"options": "Healthcare Practitioner",
				"insert_after": "reference_dn",
				"read_only": True,
			},
			{
				"fieldname": "medical_department",
				"label": "Medical Department",
				"fieldtype": "Link",
				"options": "Medical Department",
				"insert_after": "delivered_qty",
				"read_only": True,
			},
			{
				"fieldname": "service_unit",
				"label": "Service Unit",
				"fieldtype": "Link",
				"options": "Healthcare Service Unit",
				"insert_after": "medical_department",
				"read_only": True,
			},
			{
				"fieldname": "healthcare_insurance_section",
				"fieldtype": "Section Break",
				"insert_after": "is_free_item",
			},
			{
				"fieldname": "coverage_rate",
				"label": "Insurance Coverage Approved Rate",
				"fieldtype": "Currency",
				"insert_after": "healthcare_insurance_section",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "coverage_qty",
				"label": "Insurance Coverage Approved Qty",
				"fieldtype": "Float",
				"insert_after": "coverage_rate",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "coverage_percentage",
				"label": "Insurance Coverage %",
				"fieldtype": "Percent",
				"insert_after": "coverage_qty",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "insurance_coverage_amount",
				"label": "Insurance Coverage Amount",
				"fieldtype": "Currency",
				"insert_after": "coverage_percentage",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "healthcare_insurance_col_break",
				"fieldtype": "Column Break",
				"insert_after": "insurance_coverage_amount",
			},
			{
				"fieldname": "patient_insurance_policy",
				"label": "Patient Insurance Policy Number",
				"fieldtype": "Data",
				"read_only": True,
				"insert_after": "healthcare_insurance_col_break",
			},
			{
				"fieldname": "insurance_coverage",
				"label": "Patient Insurance Coverage",
				"fieldtype": "Link",
				"read_only": True,
				"insert_after": "patient_insurance_policy",
				"options": "Patient Insurance Coverage",
				"no_copy": True,
			},
			{
				"fieldname": "insurance_payor",
				"label": "Insurance Payor",
				"fieldtype": "Link",
				"read_only": True,
				"insert_after": "insurance_coverage",
				"options": "Insurance Payor",
				"no_copy": True,
			},
		],
		"Stock Entry": [
			{
				"fieldname": "inpatient_medication_entry",
				"label": "Inpatient Medication Entry",
				"fieldtype": "Link",
				"options": "Inpatient Medication Entry",
				"insert_after": "credit_note",
				"read_only": True,
			}
		],
		"Stock Entry Detail": [
			{
				"fieldname": "patient",
				"label": "Patient",
				"fieldtype": "Link",
				"options": "Patient",
				"insert_after": "po_detail",
				"read_only": True,
			},
			{
				"fieldname": "inpatient_medication_entry_child",
				"label": "Inpatient Medication Entry Child",
				"fieldtype": "Data",
				"insert_after": "patient",
				"read_only": True,
			},
		],
		"Payment Entry": [
			{
				"fieldname": "treatment_counselling",
				"label": "Treatment Counselling",
				"fieldtype": "Link",
				"options": "Treatment Counselling",
				"insert_after": "payment_order",
				"read_only": True,
			},
		],
		"Payment Entry Reference": [
			{
				"fieldname": "insurance_claim",
				"label": "Insurance Claim",
				"fieldtype": "Link",
				"options": "Insurance Claim",
				"insert_after": "reference_name",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "insurance_claim_coverage",
				"label": "Insurance Claim Coverage",
				"fieldtype": "Link",
				"options": "Insurance Claim Coverage",
				"insert_after": "insurance_claim",
				"read_only": True,
				"no_copy": True,
			},
		],
		"Journal Entry": [
			{
				"fieldname": "insurance_coverage",
				"label": "For Insurance Coverage",
				"fieldtype": "Link",
				"options": "Patient Insurance Coverage",
				"insert_after": "due_date",
				"read_only": True,
				"no_copy": True,
			}
		],
	},
	"on_setup": "healthcare.setup.setup_healthcare",
}


def setup_healthcare():
	if frappe.db.exists("Medical Department", "Cardiology"):
		# already setup
		return

	if data.get("custom_fields"):
		create_custom_fields(data.get("custom_fields"), ignore_validate=True)

	from healthcare.regional.india.abdm.setup import setup as abdm_setup

	abdm_setup()

	create_custom_records()
	create_default_root_service_units()

	setup_domain()

	frappe.clear_cache()


def setup_domain():
	"""
	Setup custom fields, properties, roles etc.
	Add Healthcare to active domains in Domain Settings
	"""
	domain = frappe.get_doc("Domain", "Healthcare")
	domain.setup_domain()

	# update active domains
	if "Healthcare" not in frappe.get_active_domains():
		has_domain = frappe.get_doc(
			{
				"doctype": "Has Domain",
				"parent": "Domain Settings",
				"parentfield": "active_domains",
				"parenttype": "Domain Settings",
				"domain": "Healthcare",
			}
		)
		has_domain.save()


def before_uninstall():
	"""
	Remove Custom Fields, portal menu items, domain
	"""
	delete_custom_records()
	remove_portal_settings_menu_items()

	domain = frappe.get_doc("Domain", "Healthcare")
	domain.remove_domain()

	remove_from_active_domains()

	frappe.clear_cache()


def create_default_root_service_units():
	from healthcare.healthcare.utils import create_healthcare_service_unit_tree_root

	companies = frappe.get_all("Company")
	for company in companies:
		create_healthcare_service_unit_tree_root(company)


def create_custom_records():
	create_medical_departments()
	create_antibiotics()
	create_lab_test_uom()
	create_duration()
	create_dosage()
	create_dosage_form()
	create_healthcare_item_groups()
	create_sensitivity()
	create_triage_levels()
	create_vital_sign_observation_templates()
	create_view_vitals_client_script()
	setup_patient_history_settings()
	setup_service_request_masters()
	setup_order_status_codes()


def create_medical_departments():
	departments = [
		"Accident And Emergency Care",
		"Anaesthetics",
		"Biochemistry",
		"Cardiology",
		"Diabetology",
		"Dermatology",
		"Diagnostic Imaging",
		"ENT",
		"Gastroenterology",
		"General",
		"General Surgery",
		"Gynaecology",
		"Haematology",
		"Maternity",
		"Microbiology",
		"Nephrology",
		"Neurology",
		"Oncology",
		"Orthopaedics",
		"Pathology",
		"Physiotherapy",
		"Rheumatology",
		"Serology",
		"Urology",
	]
	for department in departments:
		mediacal_department = frappe.new_doc("Medical Department")
		mediacal_department.department = _(department)
		try:
			mediacal_department.save()
		except frappe.DuplicateEntryError:
			pass


def create_antibiotics():
	abt = [
		"Amoxicillin",
		"Ampicillin",
		"Bacampicillin",
		"Carbenicillin",
		"Cloxacillin",
		"Dicloxacillin",
		"Flucloxacillin",
		"Mezlocillin",
		"Nafcillin",
		"Oxacillin",
		"Penicillin G",
		"Penicillin V",
		"Piperacillin",
		"Pivampicillin",
		"Pivmecillinam",
		"Ticarcillin",
		"Cefacetrile (cephacetrile)",
		"Cefadroxil (cefadroxyl)",
		"Cefalexin (cephalexin)",
		"Cefaloglycin (cephaloglycin)",
		"Cefalonium (cephalonium)",
		"Cefaloridine (cephaloradine)",
		"Cefalotin (cephalothin)",
		"Cefapirin (cephapirin)",
		"Cefatrizine",
		"Cefazaflur",
		"Cefazedone",
		"Cefazolin (cephazolin)",
		"Cefradine (cephradine)",
		"Cefroxadine",
		"Ceftezole",
		"Cefaclor",
		"Cefamandole",
		"Cefmetazole",
		"Cefonicid",
		"Cefotetan",
		"Cefoxitin",
		"Cefprozil (cefproxil)",
		"Cefuroxime",
		"Cefuzonam",
		"Cefcapene",
		"Cefdaloxime",
		"Cefdinir",
		"Cefditoren",
		"Cefetamet",
		"Cefixime",
		"Cefmenoxime",
		"Cefodizime",
		"Cefotaxime",
		"Cefpimizole",
		"Cefpodoxime",
		"Cefteram",
		"Ceftibuten",
		"Ceftiofur",
		"Ceftiolene",
		"Ceftizoxime",
		"Ceftriaxone",
		"Cefoperazone",
		"Ceftazidime",
		"Cefclidine",
		"Cefepime",
		"Cefluprenam",
		"Cefoselis",
		"Cefozopran",
		"Cefpirome",
		"Cefquinome",
		"Ceftobiprole",
		"Ceftaroline",
		"Cefaclomezine",
		"Cefaloram",
		"Cefaparole",
		"Cefcanel",
		"Cefedrolor",
		"Cefempidone",
		"Cefetrizole",
		"Cefivitril",
		"Cefmatilen",
		"Cefmepidium",
		"Cefovecin",
		"Cefoxazole",
		"Cefrotil",
		"Cefsumide",
		"Cefuracetime",
		"Ceftioxide",
		"Ceftazidime/Avibactam",
		"Ceftolozane/Tazobactam",
		"Aztreonam",
		"Imipenem",
		"Imipenem/cilastatin",
		"Doripenem",
		"Meropenem",
		"Ertapenem",
		"Azithromycin",
		"Erythromycin",
		"Clarithromycin",
		"Dirithromycin",
		"Roxithromycin",
		"Telithromycin",
		"Clindamycin",
		"Lincomycin",
		"Pristinamycin",
		"Quinupristin/dalfopristin",
		"Amikacin",
		"Gentamicin",
		"Kanamycin",
		"Neomycin",
		"Netilmicin",
		"Paromomycin",
		"Streptomycin",
		"Tobramycin",
		"Flumequine",
		"Nalidixic acid",
		"Oxolinic acid",
		"Piromidic acid",
		"Pipemidic acid",
		"Rosoxacin",
		"Ciprofloxacin",
		"Enoxacin",
		"Lomefloxacin",
		"Nadifloxacin",
		"Norfloxacin",
		"Ofloxacin",
		"Pefloxacin",
		"Rufloxacin",
		"Balofloxacin",
		"Gatifloxacin",
		"Grepafloxacin",
		"Levofloxacin",
		"Moxifloxacin",
		"Pazufloxacin",
		"Sparfloxacin",
		"Temafloxacin",
		"Tosufloxacin",
		"Besifloxacin",
		"Clinafloxacin",
		"Gemifloxacin",
		"Sitafloxacin",
		"Trovafloxacin",
		"Prulifloxacin",
		"Sulfamethizole",
		"Sulfamethoxazole",
		"Sulfisoxazole",
		"Trimethoprim-Sulfamethoxazole",
		"Demeclocycline",
		"Doxycycline",
		"Minocycline",
		"Oxytetracycline",
		"Tetracycline",
		"Tigecycline",
		"Chloramphenicol",
		"Metronidazole",
		"Tinidazole",
		"Nitrofurantoin",
		"Vancomycin",
		"Teicoplanin",
		"Telavancin",
		"Linezolid",
		"Cycloserine 2",
		"Rifampin",
		"Rifabutin",
		"Rifapentine",
		"Rifalazil",
		"Bacitracin",
		"Polymyxin B",
		"Viomycin",
		"Capreomycin",
	]

	for a in abt:
		antibiotic = frappe.new_doc("Antibiotic")
		antibiotic.antibiotic_name = a
		try:
			antibiotic.save()
		except frappe.DuplicateEntryError:
			pass


def create_lab_test_uom():
	records = [
		{"doctype": "Lab Test UOM", "name": "umol/L", "lab_test_uom": "umol/L", "uom_description": None},
		{"doctype": "Lab Test UOM", "name": "mg/L", "lab_test_uom": "mg/L", "uom_description": None},
		{
			"doctype": "Lab Test UOM",
			"name": "mg / dl",
			"lab_test_uom": "mg / dl",
			"uom_description": None,
		},
		{
			"doctype": "Lab Test UOM",
			"name": "pg / ml",
			"lab_test_uom": "pg / ml",
			"uom_description": None,
		},
		{"doctype": "Lab Test UOM", "name": "U/ml", "lab_test_uom": "U/ml", "uom_description": None},
		{"doctype": "Lab Test UOM", "name": "/HPF", "lab_test_uom": "/HPF", "uom_description": None},
		{
			"doctype": "Lab Test UOM",
			"name": "Million Cells / cumm",
			"lab_test_uom": "Million Cells / cumm",
			"uom_description": None,
		},
		{
			"doctype": "Lab Test UOM",
			"name": "Lakhs Cells / cumm",
			"lab_test_uom": "Lakhs Cells / cumm",
			"uom_description": None,
		},
		{"doctype": "Lab Test UOM", "name": "U / L", "lab_test_uom": "U / L", "uom_description": None},
		{"doctype": "Lab Test UOM", "name": "g / L", "lab_test_uom": "g / L", "uom_description": None},
		{
			"doctype": "Lab Test UOM",
			"name": "IU / ml",
			"lab_test_uom": "IU / ml",
			"uom_description": None,
		},
		{"doctype": "Lab Test UOM", "name": "gm %", "lab_test_uom": "gm %", "uom_description": None},
		{
			"doctype": "Lab Test UOM",
			"name": "Microgram",
			"lab_test_uom": "Microgram",
			"uom_description": None,
		},
		{"doctype": "Lab Test UOM", "name": "Micron", "lab_test_uom": "Micron", "uom_description": None},
		{
			"doctype": "Lab Test UOM",
			"name": "Cells / cumm",
			"lab_test_uom": "Cells / cumm",
			"uom_description": None,
		},
		{"doctype": "Lab Test UOM", "name": "%", "lab_test_uom": "%", "uom_description": None},
		{
			"doctype": "Lab Test UOM",
			"name": "mm / dl",
			"lab_test_uom": "mm / dl",
			"uom_description": None,
		},
		{
			"doctype": "Lab Test UOM",
			"name": "mm / hr",
			"lab_test_uom": "mm / hr",
			"uom_description": None,
		},
		{
			"doctype": "Lab Test UOM",
			"name": "ulU / ml",
			"lab_test_uom": "ulU / ml",
			"uom_description": None,
		},
		{
			"doctype": "Lab Test UOM",
			"name": "ng / ml",
			"lab_test_uom": "ng / ml",
			"uom_description": None,
		},
		{
			"doctype": "Lab Test UOM",
			"name": "ng / dl",
			"lab_test_uom": "ng / dl",
			"uom_description": None,
		},
		{
			"doctype": "Lab Test UOM",
			"name": "ug / dl",
			"lab_test_uom": "ug / dl",
			"uom_description": None,
		},
	]

	insert_record(records)


def create_duration():
	records = [
		{"doctype": "Prescription Duration", "name": "3 Month", "number": "3", "period": "Month"},
		{"doctype": "Prescription Duration", "name": "2 Month", "number": "2", "period": "Month"},
		{"doctype": "Prescription Duration", "name": "1 Month", "number": "1", "period": "Month"},
		{"doctype": "Prescription Duration", "name": "12 Hour", "number": "12", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "11 Hour", "number": "11", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "10 Hour", "number": "10", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "9 Hour", "number": "9", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "8 Hour", "number": "8", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "7 Hour", "number": "7", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "6 Hour", "number": "6", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "5 Hour", "number": "5", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "4 Hour", "number": "4", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "3 Hour", "number": "3", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "2 Hour", "number": "2", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "1 Hour", "number": "1", "period": "Hour"},
		{"doctype": "Prescription Duration", "name": "5 Week", "number": "5", "period": "Week"},
		{"doctype": "Prescription Duration", "name": "4 Week", "number": "4", "period": "Week"},
		{"doctype": "Prescription Duration", "name": "3 Week", "number": "3", "period": "Week"},
		{"doctype": "Prescription Duration", "name": "2 Week", "number": "2", "period": "Week"},
		{"doctype": "Prescription Duration", "name": "1 Week", "number": "1", "period": "Week"},
		{"doctype": "Prescription Duration", "name": "6 Day", "number": "6", "period": "Day"},
		{"doctype": "Prescription Duration", "name": "5 Day", "number": "5", "period": "Day"},
		{"doctype": "Prescription Duration", "name": "4 Day", "number": "4", "period": "Day"},
		{"doctype": "Prescription Duration", "name": "3 Day", "number": "3", "period": "Day"},
		{"doctype": "Prescription Duration", "name": "2 Day", "number": "2", "period": "Day"},
		{"doctype": "Prescription Duration", "name": "1 Day", "number": "1", "period": "Day"},
	]
	insert_record(records)


def create_dosage():
	records = [
		{
			"doctype": "Prescription Dosage",
			"name": "1-1-1-1",
			"dosage": "1-1-1-1",
			"dosage_strength": [
				{"strength": "1.0", "strength_time": "9:00:00"},
				{"strength": "1.0", "strength_time": "13:00:00"},
				{"strength": "1.0", "strength_time": "17:00:00"},
				{"strength": "1.0", "strength_time": "21:00:00"},
			],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "0-0-1",
			"dosage": "0-0-1",
			"dosage_strength": [{"strength": "1.0", "strength_time": "21:00:00"}],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "1-0-0",
			"dosage": "1-0-0",
			"dosage_strength": [{"strength": "1.0", "strength_time": "9:00:00"}],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "0-1-0",
			"dosage": "0-1-0",
			"dosage_strength": [{"strength": "1.0", "strength_time": "14:00:00"}],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "1-1-1",
			"dosage": "1-1-1",
			"dosage_strength": [
				{"strength": "1.0", "strength_time": "9:00:00"},
				{"strength": "1.0", "strength_time": "14:00:00"},
				{"strength": "1.0", "strength_time": "21:00:00"},
			],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "1-0-1",
			"dosage": "1-0-1",
			"dosage_strength": [
				{"strength": "1.0", "strength_time": "9:00:00"},
				{"strength": "1.0", "strength_time": "21:00:00"},
			],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "Once Bedtime",
			"dosage": "Once Bedtime",
			"dosage_strength": [{"strength": "1.0", "strength_time": "21:00:00"}],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "5 times a day",
			"dosage": "5 times a day",
			"dosage_strength": [
				{"strength": "1.0", "strength_time": "5:00:00"},
				{"strength": "1.0", "strength_time": "9:00:00"},
				{"strength": "1.0", "strength_time": "13:00:00"},
				{"strength": "1.0", "strength_time": "17:00:00"},
				{"strength": "1.0", "strength_time": "21:00:00"},
			],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "QID",
			"dosage": "QID",
			"dosage_strength": [
				{"strength": "1.0", "strength_time": "9:00:00"},
				{"strength": "1.0", "strength_time": "13:00:00"},
				{"strength": "1.0", "strength_time": "17:00:00"},
				{"strength": "1.0", "strength_time": "21:00:00"},
			],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "TID",
			"dosage": "TID",
			"dosage_strength": [
				{"strength": "1.0", "strength_time": "9:00:00"},
				{"strength": "1.0", "strength_time": "14:00:00"},
				{"strength": "1.0", "strength_time": "21:00:00"},
			],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "BID",
			"dosage": "BID",
			"dosage_strength": [
				{"strength": "1.0", "strength_time": "9:00:00"},
				{"strength": "1.0", "strength_time": "21:00:00"},
			],
		},
		{
			"doctype": "Prescription Dosage",
			"name": "Once Daily",
			"dosage": "Once Daily",
			"dosage_strength": [{"strength": "1.0", "strength_time": "9:00:00"}],
		},
	]
	insert_record(records)


def create_dosage_form():
	records = [
		{
			"doctype": "Dosage Form",
			"dosage_form": "Tablet",
		},
		{
			"doctype": "Dosage Form",
			"dosage_form": "Syrup",
		},
		{
			"doctype": "Dosage Form",
			"dosage_form": "Injection",
		},
		{
			"doctype": "Dosage Form",
			"dosage_form": "Capsule",
		},
		{
			"doctype": "Dosage Form",
			"dosage_form": "Cream",
		},
	]
	insert_record(records)


def create_healthcare_item_groups():
	item_group = {
		"doctype": "Item Group",
		"item_group_name": _("All Item Groups"),
		"is_group": 1,
		"parent_item_group": "",
	}
	if not frappe.db.exists(item_group["doctype"], item_group["item_group_name"]):
		insert_record([item_group])

	records = get_item_group_records()
	insert_record(records)


def get_item_group_records():
	return [
		{
			"doctype": "Item Group",
			"item_group_name": _("Laboratory"),
			"name": _("Laboratory"),
			"is_group": 0,
			"parent_item_group": _("All Item Groups"),
		},
		{
			"doctype": "Item Group",
			"item_group_name": _("Drug"),
			"name": _("Drug"),
			"is_group": 0,
			"parent_item_group": _("All Item Groups"),
		},
	]


def create_triage_levels():
	levels = [
		{
			"triage_level": "Emergency",
			"code": "RED",
			"color": "#e24c4c",
			"priority": 1,
			"target_reassessment_mins": 0,
		},
		{
			"triage_level": "Urgent",
			"code": "YELLOW",
			"color": "#ecad4b",
			"priority": 2,
			"target_reassessment_mins": 30,
		},
		{
			"triage_level": "Non-urgent",
			"code": "GREEN",
			"color": "#4caf50",
			"priority": 3,
			"target_reassessment_mins": 120,
		},
	]
	records = [{"doctype": "Triage Level", **level} for level in levels]
	insert_record(records)


def create_vital_sign_observation_templates():
	vitals = [
		(_("Pulse"), "PR"),
		(_("Respiratory Rate"), "RR"),
		(_("Temperature"), "TEMP"),
		(_("BP Systolic"), "BPS"),
		(_("BP Diastolic"), "BPD"),
		(_("SpO2"), "SPO2"),
	]
	records = [
		{
			"doctype": "Observation Template",
			"observation": observation,
			"abbr": abbr,
			"observation_category": "Vital Signs",
			"permitted_data_type": "Quantity",
		}
		for observation, abbr in vitals
	]
	insert_record(records)


def create_view_vitals_client_script():
	"""Add a 'View Vitals' button to the View dropdown on Patient Encounter,
	next to the existing 'Patient History' button."""
	if frappe.db.exists("Client Script", "Patient Encounter View Vitals"):
		return

	script = """frappe.ui.form.on("Patient Encounter", {
	refresh(frm) {
		frm.add_custom_button(
			__("View Vitals"),
			function () {
				if (frm.doc.patient) {
					frappe.set_route("List", "Vital Signs", {
						patient: frm.doc.patient,
						encounter: frm.doc.name,
					});
				} else {
					frappe.msgprint(__("Please select Patient"));
				}
			},
			__("View"),
		);
	},
});
"""

	frappe.get_doc(
		{
			"doctype": "Client Script",
			"name": "Patient Encounter View Vitals",
			"dt": "Patient Encounter",
			"view": "Form",
			"script": script,
			"enabled": 1,
		}
	).insert(ignore_permissions=True)


def create_sensitivity():
	records = [
		{"doctype": "Sensitivity", "sensitivity": _("Low Sensitivity")},
		{"doctype": "Sensitivity", "sensitivity": _("High Sensitivity")},
		{"doctype": "Sensitivity", "sensitivity": _("Moderate Sensitivity")},
		{"doctype": "Sensitivity", "sensitivity": _("Susceptible")},
		{"doctype": "Sensitivity", "sensitivity": _("Resistant")},
		{"doctype": "Sensitivity", "sensitivity": _("Intermediate")},
	]
	insert_record(records)


def setup_patient_history_settings():
	import json

	settings = frappe.get_single("Patient History Settings")
	configuration = get_patient_history_config()
	for dt, config in configuration.items():
		settings.append(
			"standard_doctypes",
			{"document_type": dt, "date_fieldname": config[0], "selected_fields": json.dumps(config[1])},
		)
	settings.save()


def setup_service_request_masters():
	records = [
		{"doctype": "Patient Care Type", "patient_care_type": _("Preventive")},
		{"doctype": "Patient Care Type", "patient_care_type": _("Intervention")},
		{"doctype": "Patient Care Type", "patient_care_type": _("Diagnostic")},
		{
			"doctype": "Code System",
			"uri": "http://hl7.org/fhir/request-intent",
			"is_fhir_defined": 1,
			"code_system": _("Intent"),
			"description": _(
				"Codes indicating the degree of authority/intentionality associated with a request."
			),
			"oid": "2.16.840.1.113883.4.642.4.114",
			"experimental": 1,
			"immutable": 1,
			"custom": 0,
		},
		{
			"doctype": "Code System",
			"uri": "http://hl7.org/fhir/request-priority",
			"is_fhir_defined": 1,
			"code_system": _("Priority"),
			"description": _("Identifies the level of importance to be assigned to actioning the request."),
			"oid": "2.16.840.1.113883.4.642.4.116",
			"experimental": 1,
			"immutable": 1,
			"custom": 0,
		},
		{
			"doctype": "Code Value",
			"code_system": "Intent",
			"code_value": _("Order"),
			"definition": _(
				"The request represents a request/demand and authorization for action by the requestor."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-intent",
		},
		{
			"doctype": "Code Value",
			"code_system": "Intent",
			"code_value": _("Proposal"),
			"definition": _(
				"The request is a suggestion made by someone/something that does not have an intention to ensure it occurs and without providing an authorization to act."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-intent",
		},
		{
			"doctype": "Code Value",
			"code_system": "Intent",
			"code_value": _("Plan"),
			"definition": _(
				"The request represents an intention to ensure something occurs without providing an authorization for others to act."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-intent",
		},
		{
			"doctype": "Code Value",
			"code_system": "Intent",
			"code_value": _("Directive"),
			"definition": _(
				"The request represents a legally binding instruction authored by a Patient or RelatedPerson."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-intent",
		},
		{
			"doctype": "Code Value",
			"code_system": "Intent",
			"code_value": _("Original Order"),
			"definition": _("The request represents an original authorization for action."),
			"official_url": "http://hl7.org/fhir/ValueSet/request-intent",
		},
		{
			"doctype": "Code Value",
			"code_system": "Intent",
			"code_value": _("Reflex Order"),
			"definition": _(
				"The request represents an automatically generated supplemental authorization for action based on a parent authorization together with initial results of the action taken against that parent authorization."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-intent",
		},
		{
			"doctype": "Code Value",
			"code_system": "Intent",
			"code_value": _("Filler Order"),
			"definition": _(
				"The request represents the view of an authorization instantiated by a fulfilling system representing the details of the fulfiller's intention to act upon a submitted order."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-intent",
		},
		{
			"doctype": "Code Value",
			"code_system": "Intent",
			"code_value": _("Instance Order"),
			"definition": _(
				"An order created in fulfillment of a broader order that represents the authorization for a single activity occurrence. E.g. The administration of a single dose of a drug."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-intent",
		},
		{
			"doctype": "Code Value",
			"code_system": "Intent",
			"code_value": _("Option"),
			"definition": _(
				"The request represents a component or option for a RequestOrchestration that establishes timing, conditionality and/or other constraints among a set of requests."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-intent",
		},
		{
			"doctype": "Code Value",
			"code_system": "Priority",
			"code_value": _("Routine"),
			"definition": _("The request has normal priority."),
			"official_url": "http://hl7.org/fhir/ValueSet/request-priority",
		},
		{
			"doctype": "Code Value",
			"code_system": "Priority",
			"code_value": _("Urgent"),
			"definition": _("The request should be actioned promptly - higher priority than routine."),
			"official_url": "http://hl7.org/fhir/ValueSet/request-priority",
		},
		{
			"doctype": "Code Value",
			"code_system": "Priority",
			"code_value": _("ASAP"),
			"definition": _(
				"The request should be actioned as soon as possible - higher priority than urgent."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-priority",
		},
		{
			"doctype": "Code Value",
			"code_system": "Priority",
			"code_value": _("STAT"),
			"definition": _(
				"The request should be actioned immediately - highest possible priority. E.g. an emergency."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-priority",
		},
	]
	insert_record(records)


def get_patient_history_config():
	return {
		"Patient Encounter": (
			"encounter_date",
			[
				{"label": "Healthcare Practitioner", "fieldname": "practitioner", "fieldtype": "Link"},
				{"label": "Symptoms", "fieldname": "symptoms", "fieldtype": "Table Multiselect"},
				{"label": "Diagnosis", "fieldname": "diagnosis", "fieldtype": "Table Multiselect"},
				{"label": "Drug Prescription", "fieldname": "drug_prescription", "fieldtype": "Table"},
				{"label": "Lab Tests", "fieldname": "lab_test_prescription", "fieldtype": "Table"},
				{"label": "Clinical Procedures", "fieldname": "procedure_prescription", "fieldtype": "Table"},
				{"label": "Therapies", "fieldname": "therapies", "fieldtype": "Table"},
				{"label": "Review Details", "fieldname": "encounter_comment", "fieldtype": "Small Text"},
			],
		),
		"Clinical Procedure": (
			"start_date",
			[
				{"label": "Procedure Template", "fieldname": "procedure_template", "fieldtype": "Link"},
				{"label": "Healthcare Practitioner", "fieldname": "practitioner", "fieldtype": "Link"},
				{"label": "Notes", "fieldname": "notes", "fieldtype": "Small Text"},
				{
					"label": "Service Unit",
					"fieldname": "service_unit",
					"fieldtype": "Healthcare Service Unit",
				},
				{"label": "Start Time", "fieldname": "start_time", "fieldtype": "Time"},
				{"label": "Sample", "fieldname": "sample", "fieldtype": "Link"},
			],
		),
		"Lab Test": (
			"result_date",
			[
				{"label": "Test Template", "fieldname": "template", "fieldtype": "Link"},
				{"label": "Healthcare Practitioner", "fieldname": "practitioner", "fieldtype": "Link"},
				{"label": "Test Name", "fieldname": "lab_test_name", "fieldtype": "Data"},
				{"label": "Lab Technician Name", "fieldname": "employee_name", "fieldtype": "Data"},
				{"label": "Sample ID", "fieldname": "sample", "fieldtype": "Link"},
				{"label": "Normal Test Result", "fieldname": "normal_test_items", "fieldtype": "Table"},
				{
					"label": "Descriptive Test Result",
					"fieldname": "descriptive_test_items",
					"fieldtype": "Table",
				},
				{"label": "Organism Test Result", "fieldname": "organism_test_items", "fieldtype": "Table"},
				{
					"label": "Sensitivity Test Result",
					"fieldname": "sensitivity_test_items",
					"fieldtype": "Table",
				},
				{"label": "Comments", "fieldname": "lab_test_comment", "fieldtype": "Table"},
			],
		),
		"Therapy Session": (
			"start_date",
			[
				{"label": "Therapy Type", "fieldname": "therapy_type", "fieldtype": "Link"},
				{"label": "Healthcare Practitioner", "fieldname": "practitioner", "fieldtype": "Link"},
				{"label": "Therapy Plan", "fieldname": "therapy_plan", "fieldtype": "Link"},
				{"label": "Duration", "fieldname": "duration", "fieldtype": "Int"},
				{"label": "Location", "fieldname": "location", "fieldtype": "Link"},
				{"label": "Healthcare Service Unit", "fieldname": "service_unit", "fieldtype": "Link"},
				{"label": "Start Time", "fieldname": "start_time", "fieldtype": "Time"},
				{"label": "Exercises", "fieldname": "exercises", "fieldtype": "Table"},
				{"label": "Total Counts Targeted", "fieldname": "total_counts_targeted", "fieldtype": "Int"},
				{
					"label": "Total Counts Completed",
					"fieldname": "total_counts_completed",
					"fieldtype": "Int",
				},
			],
		),
		"Vital Signs": (
			"signs_date",
			[
				{"label": "Body Temperature", "fieldname": "temperature", "fieldtype": "Data"},
				{"label": "Heart Rate / Pulse", "fieldname": "pulse", "fieldtype": "Data"},
				{"label": "Respiratory rate", "fieldname": "respiratory_rate", "fieldtype": "Data"},
				{"label": "Tongue", "fieldname": "tongue", "fieldtype": "Select"},
				{"label": "Abdomen", "fieldname": "abdomen", "fieldtype": "Select"},
				{"label": "Reflexes", "fieldname": "reflexes", "fieldtype": "Select"},
				{"label": "Blood Pressure", "fieldname": "bp", "fieldtype": "Data"},
				{"label": "Notes", "fieldname": "vital_signs_note", "fieldtype": "Small Text"},
				{"label": "Height (In Meter)", "fieldname": "height", "fieldtype": "Float"},
				{"label": "Weight (In Kilogram)", "fieldname": "weight", "fieldtype": "Float"},
				{"label": "BMI", "fieldname": "bmi", "fieldtype": "Float"},
			],
		),
		"Inpatient Medication Order": (
			"start_date",
			[
				{"label": "Healthcare Practitioner", "fieldname": "practitioner", "fieldtype": "Link"},
				{"label": "Start Date", "fieldname": "start_date", "fieldtype": "Date"},
				{"label": "End Date", "fieldname": "end_date", "fieldtype": "Date"},
				{"label": "Medication Orders", "fieldname": "medication_orders", "fieldtype": "Table"},
				{"label": "Total Orders", "fieldname": "total_orders", "fieldtype": "Float"},
			],
		),
		"Observation": (
			"posting_date",
			[
				{"label": "Observation Template", "fieldname": "observation_template", "fieldtype": "Link"},
				{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date"},
				{"label": "Status", "fieldname": "status", "fieldtype": "Select"},
				{"label": "Time of Result", "fieldname": "time_of_result", "fieldtype": "Datetime"},
			],
		),
		"Discharge Summary": (
			"posting_date",
			[
				{
					"label": "Chief Complaint",
					"fieldname": "chief_complaint",
					"fieldtype": "Table MultiSelect",
				},
				{"label": "Current Issues", "fieldname": "current_issues", "fieldtype": "Text Editor"},
				{"label": "Diagnosis", "fieldname": "diagnosis", "fieldtype": "Table MultiSelect"},
				{"label": "Diet Adviced", "fieldname": "diet_adviced", "fieldtype": "Text Editor"},
				{"label": "Instructions", "fieldname": "instructions", "fieldtype": "Text Editor"},
				{
					"label": "Healthcare Practitioner (Primary)",
					"fieldname": "primary_practitioner",
					"fieldtype": "Link",
				},
				{
					"label": "Healthcare Practitioner (Secondary)",
					"fieldname": "secondary_practitioner",
					"fieldtype": "Link",
				},
				{
					"label": "Advice on Discharge",
					"fieldname": "advice_on_discharge",
					"fieldtype": "Text Editor",
				},
				{
					"label": "Physical Examination",
					"fieldname": "physical_examination",
					"fieldtype": "Text Editor",
				},
				{"label": "Review Date", "fieldname": "review_date", "fieldtype": "Date"},
				{
					"label": "Discharging Practitioner",
					"fieldname": "discharge_practitioner",
					"fieldtype": "Link",
				},
				{"label": "Followup Date", "fieldname": "followup_date", "fieldtype": "Date"},
			],
		),
	}


def setup_code_sysem_for_version():
	records = [
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://hl7.org/fhir/ValueSet/version-algorithm",
			"code_system": _("FHIRVersion"),
			"description": _(
				"""Indicates the mechanism used to compare versions to determine which is more current."""
			),
			"oid": "2.16.840.1.113883.4.642.3.3103",
			"experimental": 1,
			"immutable": 1,
			"custom": 0,
		},
		{
			"doctype": "Code Value",
			"code_system": _("FHIRVersion"),
			"code_value": "5.0.0",
			"display": _("5.0.0"),
		},
	]
	insert_record(records)


def setup_non_fhir_code_systems():
	"""A subset of external code systems as published in the FHIR R5 documentation
	https://www.hl7.org/fhir/terminologies-systems.html#external

	For a full set of external code systems, see
	https://terminology.hl7.org/external_terminologies.html
	"""
	code_systems = [
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://snomed.info/sct",
			"code_system": _("SNOMED CT"),
			"description": _(
				"""Using SNOMED CT with HL7 Standards. https://terminology.hl7.org/SNOMEDCT.html
				See also the SNOMED CT Usage Summary (link below) which summarizes the use of SNOMED CT in the base FHIR Specification.
				https://www.hl7.org/fhir/snomedct-usage.html"""
			),
			"oid": "2.16.840.1.113883.6.96",
			"experimental": 0,
			"immutable": 0,
			"custom": 0,
			"version": "5.0.0-FHIRVersion",
		},
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://www.nlm.nih.gov/research/umls/rxnorm",
			"code_system": _("RxNorm"),
			"description": _("Using RxNorm with HL7 Standards. https://terminology.hl7.org/RxNorm.html"),
			"oid": "2.16.840.1.113883.6.88",
			"experimental": 0,
			"immutable": 0,
			"custom": 0,
			"version": "5.0.0-FHIRVersion",
		},
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://loinc.org",
			"code_system": _("LOINC"),
			"description": _("Using LOINC with HL7 Standards. https://terminology.hl7.org/LOINC.html"),
			"oid": "2.16.840.1.113883.6.1",
			"experimental": 0,
			"immutable": 0,
			"custom": 0,
			"version": "5.0.0-FHIRVersion",
		},
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://unitsofmeasure.org",
			"code_system": _("pCLUCUMOCD"),
			"description": _("Using UCUM with HL7 Standards. https://terminology.hl7.org/UCUM.html"),
			"oid": "2.16.840.1.113883.6.8",
			"experimental": 0,
			"immutable": 0,
			"custom": 0,
			"version": "5.0.0-FHIRVersion",
		},
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://hl7.org/fhir/sid/icd-9-cm",
			"code_system": _("ICD-9-CM (clinical codes)"),
			"description": _("Using ICD-[x] with HL7 Standards. https://terminology.hl7.org/ICD.html"),
			"oid": "2.16.840.1.113883.6.103",
			"experimental": 0,
			"immutable": 0,
			"custom": 0,
			"version": "5.0.0-FHIRVersion",
		},
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://hl7.org/fhir/sid/icd-9-cm",
			"code_system": _("ICD-9-CM (procedure codes)"),
			"description": _("Using ICD-[x] with HL7 Standards. https://terminology.hl7.org/ICD.html"),
			"oid": "2.16.840.1.113883.6.104",
			"experimental": 0,
			"immutable": 0,
			"custom": 0,
			"version": "5.0.0-FHIRVersion",
		},
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://hl7.org/fhir/sid/icd-10-cm",
			"code_system": _("ICD-10-CM (United States)"),
			"description": _("Using ICD-[x] with HL7 Standards. https://terminology.hl7.org/ICD.html"),
			"oid": "2.16.840.1.113883.6.90",
			"experimental": 0,
			"immutable": 0,
			"custom": 0,
			"version": "5.0.0-FHIRVersion",
		},
	]
	insert_record(code_systems)


def setup_fhir_code_systems():
	code_systems = [
		{
			"doctype": "Code System",
			"is_fhir_defined": 1,
			"uri": "http://hl7.org/fhir/FHIR-version",
			"code_system": _("FHIRVersion"),
			"description": _("All published FHIR Versions."),
			"oid": "2.16.840.1.113883.4.642.4.1310",
			"experimental": 0,
			"immutable": 0,
			"custom": 0,
		},
		{
			"doctype": "Code System",
			"is_fhir_defined": 1,
			"uri": "http://hl7.org/fhir/publication-status",
			"code_system": _("PublicationStatus"),
			"description": _("The lifecycle status of an artifact."),
			"oid": "22.16.840.1.113883.4.642.3.3",
			"experimental": 0,
			"immutable": 1,
			"custom": 0,
		},
	]
	insert_record(code_systems)


def setup_diagnostic_module_codes():
	records = []

	records.extend(get_diagnostic_module_code_systems())
	records.extend(get_observation_category_codes())
	records.extend(get_observation_status_codes())

	# TODO: insert observation methods
	insert_record(records)


def get_diagnostic_module_code_systems():
	return [
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://terminology.hl7.org/CodeSystem/observation-category",
			"code_system": _("ObservationCategory"),
			"description": _("Observation Category codes."),
			"oid": "2.16.840.1.113883.4.642.1.1125",
			"experimental": 1,
			"immutable": 0,
			"custom": 0,
		},
		{
			"doctype": "Code System",
			"is_fhir_defined": 1,
			"uri": "http://hl7.org/fhir/observation-status",
			"code_system": _("ObservationStatus"),
			"description": _("Codes providing the status of an observation."),
			"version": "5.0.0-FHIRVersion",
			"oid": "2.16.840.1.113883.4.642.4.401",
			"experimental": 0,
			"immutable": 0,
			"complete": 1,
			"custom": 0,
		},
	]


def get_observation_category_codes():
	return [
		{
			"doctype": "Code Value",
			"code_system": _("Observation Category"),
			"code_value": "social-history",
			"display": _("Social History"),
			"definition": _(
				"Social History Observations define the patient's occupational, personal (e.g., lifestyle), social, familial, and environmental history and health risk factors that may impact the patient's health."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-category",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Category"),
			"code_value": "vital-signs",
			"display": _("Vital Signs"),
			"definition": _(
				"Clinical observations measure the body's basic functions such as blood pressure, heart rate, respiratory rate, height, weight, body mass index, head circumference, pulse oximetry, temperature, and body surface area."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-category",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Category"),
			"code_value": "imaging",
			"display": _("Imaging"),
			"definition": _(
				"Observations generated by imaging. The scope includes observations regarding plain x-ray, ultrasound, CT, MRI, angiography, echocardiography, and nuclear medicine."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-category",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Category"),
			"code_value": "laboratory",
			"display": _("Laboratory"),
			"definition": _(
				"The results of observations generated by laboratories. Laboratory results are typically generated by laboratories providing analytic services in areas such as chemistry, hematology, serology, histology, cytology, anatomic pathology (including digital pathology), microbiology, and/or virology. These observations are based on analysis of specimens obtained from the patient and submitted to the laboratory."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-category",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Category"),
			"code_value": "procedure",
			"display": _("Procedure"),
			"definition": _(
				"Observations generated by other procedures. This category includes observations resulting from interventional and non-interventional procedures excluding laboratory and imaging (e.g., cardiology catheterization, endoscopy, electrodiagnostics, etc.). Procedure results are typically generated by a clinician to provide more granular information about component observations made during a procedure. An example would be when a gastroenterologist reports the size of a polyp observed during a colonoscopy."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-category",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Category"),
			"code_value": "survey",
			"display": _("Survey"),
			"definition": _(
				"Assessment tool/survey instrument observations (e.g., Apgar Scores, Montreal Cognitive Assessment (MoCA))."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-category",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Category"),
			"code_value": "exam",
			"display": _("Exam"),
			"definition": _(
				"Observations generated by physical exam findings including direct observations made by a clinician and use of simple instruments and the result of simple maneuvers performed directly on the patient's body."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-category",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Category"),
			"code_value": "therapy",
			"display": _("Therapy"),
			"definition": _(
				"Observations generated by non-interventional treatment protocols (e.g. occupational, physical, radiation, nutritional and medication therapy)"
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-category",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Category"),
			"code_value": "activity",
			"display": _("Activity"),
			"definition": _(
				"Observations that measure or record any bodily activity that enhances or maintains physical fitness and overall health and wellness. Not under direct supervision of practitioner such as a physical therapist. (e.g., laps swum, steps, sleep data)"
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-category",
		},
	]


def get_observation_status_codes():
	# TODO: Add field for canonical mapping to Resource Status
	return [
		{
			"doctype": "Code Value",
			"code_system": _("Observation Status"),
			"code_value": "registered",
			"display": _("Registered"),
			"definition": _(
				"Observations that measure or record any bodily activity that enhances or maintains physical fitness and overall health and wellness. Not under direct supervision of practitioner such as a physical therapist. (e.g., laps swum, steps, sleep data.)"
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-status",
			"version": "6.0.0-cibuild",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Status"),
			"code_value": "preliminary",
			"display": _("Preliminary"),
			"definition": _(
				"This is an initial or interim observation: data may be incomplete or unverified."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-status",
			"version": "6.0.0-cibuild",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Status"),
			"code_value": "final",
			"display": _("Final"),
			"definition": _("The observation is complete and there are no further actions needed.)"),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-status",
			"version": "6.0.0-cibuild",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Status"),
			"code_value": "amended",
			"display": _("Amended"),
			"definition": _(
				"Subsequent to being Final, the observation has been modified subsequent. This includes updates/new information and corrections."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-status",
			"version": "6.0.0-cibuild",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Status"),
			"code_value": "corrected",
			"display": _("Corrected"),
			"definition": _(
				"Subsequent to being Final, the observation has been modified to correct an error in the test result."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-status",
			"version": "6.0.0-cibuild",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Status"),
			"code_value": "cancelled",
			"display": _("Cancelled"),
			"definition": _(
				"The observation is unavailable because the measurement was not started or not completed (also sometimes called 'aborted')."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-status",
			"version": "6.0.0-cibuild",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Status"),
			"code_value": "entered-in-error",
			"display": _("Entered in Error"),
			"definition": _(
				"The observation has been withdrawn following previous final release. This electronic record should never have existed, though it is possible that real-world decisions were based on it. (If real-world activity has occurred, the status should be 'cancelled' rather than 'entered-in-error'.)."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-status",
			"version": "6.0.0-cibuild",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Observation Status"),
			"code_value": "unknown",
			"display": _("Unknown"),
			"definition": _(
				"The authoring/source system does not know which of the status values currently applies for this observation. Note: This concept is not to be used for 'other' - one of the listed statuses is presumed to apply, but the authoring/source system does not know which."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/observation-status",
			"version": "6.0.0-cibuild",
		},
	]


def setup_order_status_codes():
	sr_code_systems = get_service_request_code_systems()
	insert_record(sr_code_systems)
	service_request_codes = get_service_request_codes()
	insert_record(service_request_codes)

	mr_code_systems = get_medication_request_code_systems()
	insert_record(mr_code_systems)
	medication_request_codes = get_medication_request_codes()
	insert_record(medication_request_codes)


def get_service_request_code_systems():
	return [
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://hl7.org/fhir/request-status",
			"code_system": _("Request Status"),
			"description": _("Request Status Codes."),
			"oid": "2.16.840.1.113883.4.642.4.112",
			"experimental": 1,
			"immutable": 0,
			"custom": 0,
		},
	]


def get_medication_request_code_systems():
	return [
		{
			"doctype": "Code System",
			"is_fhir_defined": 0,
			"uri": "http://hl7.org/fhir/CodeSystem/medicationrequest-status",
			"code_system": _("Medication Request Status"),
			"description": _("Medication Request Status Codes."),
			"oid": "2.16.840.1.113883.4.642.4.1377",
			"experimental": 1,
			"immutable": 0,
			"custom": 0,
		},
	]


def get_service_request_codes():
	return [
		{
			"doctype": "Code Value",
			"code_system": _("Request Status"),
			"code_value": "draft",
			"display": _("Draft"),
			"definition": _("The request has been created but is not yet complete or ready for action."),
			"official_url": "http://hl7.org/fhir/ValueSet/request-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Request Status"),
			"code_value": "active",
			"display": _("Active"),
			"definition": _("The request is in force and ready to be acted upon."),
			"official_url": "http://hl7.org/fhir/ValueSet/request-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Request Status"),
			"code_value": "on-hold",
			"display": _("On Hold"),
			"definition": _(
				"The request (and any implicit authorization to act) has been temporarily withdrawn but is expected to resume in the future."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Request Status"),
			"code_value": "revoked",
			"display": _("Revoked"),
			"definition": _(
				"The request (and any implicit authorization to act) has been terminated prior to the known full completion of the intended actions. No further activity should occur."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Request Status"),
			"code_value": "completed",
			"display": _("Completed"),
			"definition": _(
				"The activity described by the request has been fully performed. No further activity will occur."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Request Status"),
			"code_value": "entered-in-error",
			"display": _("Entered in Error"),
			"definition": _(
				"This request should never have existed and should be considered 'void'. (It is possible that real-world decisions were based on it. If real-world activity has occurred, the status should be 'revoked' rather than 'entered-in-error'.)."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Request Status"),
			"code_value": "unknown",
			"display": _("Unknown"),
			"definition": _(
				"The authoring/source system does not know which of the status values currently applies for this request. Note: This concept is not to be used for 'other' - one of the listed statuses is presumed to apply, but the authoring/source system does not know which."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/request-status",
		},
	]


def get_medication_request_codes():
	return [
		{
			"doctype": "Code Value",
			"code_system": _("Medication Request Status"),
			"code_value": "active",
			"display": _("Active"),
			"definition": _(
				"The request is 'actionable', but not all actions that are implied by it have occurred yet."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/medicationrequest-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Medication Request Status"),
			"code_value": "on-hold",
			"display": _("On Hold"),
			"definition": _(
				"Actions implied by the request are to be temporarily halted. The request might or might not be resumed. May also be called 'suspended'."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/medicationrequest-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Medication Request Status"),
			"code_value": "ended",
			"display": _("Ended"),
			"definition": _(
				"The request is no longer active and the subject should no longer be taking the medication."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/medicationrequest-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Medication Request Status"),
			"code_value": "stopped",
			"display": _("Stopped"),
			"definition": _(
				"Actions implied by the request are to be permanently halted, before all of the administrations occurred. This should not be used if the original order was entered in error"
			),
			"official_url": "http://hl7.org/fhir/ValueSet/medicationrequest-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Medication Request Status"),
			"code_value": "completed",
			"display": _("Completed"),
			"definition": _("All actions that are implied by the request have occurred."),
			"official_url": "http://hl7.org/fhir/ValueSet/medicationrequest-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Medication Request Status"),
			"code_value": "cancelled",
			"display": _("Cancelled"),
			"definition": _("The request has been withdrawn before any administrations have occurred"),
			"official_url": "http://hl7.org/fhir/ValueSet/medicationrequest-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Medication Request Status"),
			"code_value": "entered-in-error",
			"display": _("Entered in Error"),
			"definition": _(
				"The request was recorded against the wrong patient or for some reason should not have been recorded (e.g. wrong medication, wrong dose, etc.). Some of the actions that are implied by the medication request may have occurred. For example, the medication may have been dispensed and the patient may have taken some of the medication."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/medicationrequest-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Medication Request Status"),
			"code_value": "draft",
			"display": _("Draft"),
			"definition": _(
				"The request is not yet 'actionable', e.g. it is a work in progress, requires sign-off, verification or needs to be run through decision support process."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/medicationrequest-status",
		},
		{
			"doctype": "Code Value",
			"code_system": _("Medication Request Status"),
			"code_value": "unknown",
			"display": _("Unknown"),
			"definition": _(
				"The authoring/source system does not know which of the status values currently applies for this request. Note: This concept is not to be used for 'other' - one of the listed statuses is presumed to apply, but the authoring/source system does not know which."
			),
			"official_url": "http://hl7.org/fhir/ValueSet/medicationrequest-status",
		},
	]


def delete_custom_records():
	"""Delete custom records inserted by Health app"""
	records = get_item_group_records()
	for record in records:
		frappe.db.delete(record.get("doctype"), record.get("name"))

	frappe.db.set_single_value("Portal Settings", "default_role", "")


def remove_from_active_domains():
	"""Remove Healthcare from active domains in Domain Settings"""
	frappe.db.delete("Has Domain", {"domain": "Healthcare"})


def remove_portal_settings_menu_items():
	"""Remove menu items added in Portal Settings"""
	menu_items = frappe.get_hooks("standard_portal_menu_items", app_name="healthcare")
	for item in menu_items:
		frappe.db.delete("Portal Menu Item", item)


# ---- Merged content from setup (8).py should be integrated manually ----
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from healthcare.healthcare.workspace_installer import (
	workspace_installer,
	workspace_remover,
)


def setup():
	make_custom_fields()
	workspace_installer()


def uninstall():
	custom_fields = get_custom_fields()
	delete_custom_fields(custom_fields)
	workspace_remover()


def make_custom_fields(update=True):
	custom_fields = get_custom_fields()
	create_custom_fields(custom_fields, update=update)


def delete_custom_fields(custom_fields: dict):
	"""
	:param custom_fields: a dict like `{'Sales Order': [{fieldname: '', ...}]}`
	"""
	for doctype, fields in custom_fields.items():
		frappe.db.delete(
			"Custom Field",
			{
				"fieldname": ("in", [field["fieldname"] for field in fields]),
				"dt": doctype,
			},
		)
		frappe.clear_cache(doctype=doctype)


def get_custom_fields():
	return {
		# Pharmacy POS: tags the Sales Order as pharmacy-originated, links it
		# to the dispensing Patient, and links each line item back to the
		# Medication Request it was dispensed against.
		#
		# custom_department: used by the Cashier Portal
		# (page/cashier_portal/cashier_portal.py) to bucket a party's open
		# orders into Pharmacy/Laboratory/Rehabilitation/Other tabs -
		# without this field, _get_department_invoices()/_get_pharmacy_orders()
		# throw "Unknown column 'custom_department'".
		"Sales Order": [
			{
				"fieldname": "custom_invoice_from",
				"label": "Invoice From",
				"fieldtype": "Select",
				"insert_after": "customer",
				"options": "\nPharmacy\nSpa",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_patient",
				"label": "Patient",
				"fieldtype": "Link",
				"insert_after": "custom_invoice_from",
				"options": "Patient",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_department",
				"label": "Department",
				"fieldtype": "Select",
				"insert_after": "custom_patient",
				"options": "\nPharmacy\nLaboratory\nRehabilitation\nOther",
				"reqd": 0,
				"hidden": 0,
			},
		],
		"Sales Order Item": [
			{
				"fieldname": "custom_reference_doctype",
				"label": "Reference Document Type",
				"fieldtype": "Link",
				"insert_after": "item_name",
				"options": "DocType",
				"reqd": 0,
				"hidden": 1,
			},
			{
				"fieldname": "custom_reference_name",
				"label": "Reference Name",
				"fieldtype": "Dynamic Link",
				"insert_after": "custom_reference_doctype",
				"options": "custom_reference_doctype",
				"reqd": 0,
				"hidden": 1,
			},
		],
		# Spa Portal: tags Sales Invoices created from create_spa_invoice()
		# so get_spa_invoices() can filter to spa-originated invoices only.
		#
		# custom_department: same Cashier Portal bucketing as on Sales Order
		# above, applied to Sales Invoice (_get_department_invoices() reads
		# this field on both doctypes).
		"Sales Invoice": [
			{
				"fieldname": "custom_invoice_from",
				"label": "Invoice From",
				"fieldtype": "Select",
				"insert_after": "customer",
				"options": "\nPharmacy\nSpa",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_department",
				"label": "Department",
				"fieldtype": "Select",
				"insert_after": "custom_invoice_from",
				"options": "\nPharmacy\nLaboratory\nRehabilitation\nConsultation\nOther",
				"reqd": 0,
				"hidden": 0,
			},
		],
		# Lab Portal: priority on the requested test, and a link back to the
		# Lab Test doc created once accept_lab_request() accepts it.
		"Lab Prescription": [
			{
				"fieldname": "custom_priority",
				"label": "Priority",
				"fieldtype": "Select",
				"insert_after": "lab_test_comment",
				"options": "\nLow\nMedium\nHigh",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_lab_test",
				"label": "Lab Test",
				"fieldtype": "Link",
				"insert_after": "custom_priority",
				"options": "Lab Test",
				"reqd": 0,
				"hidden": 0,
			},
		],
		# Lab Portal: links a Lab Test back to the Sales Invoice created for
		# it in accept_lab_request(). lab_portal.py's get_pending_labs() and
		# accept_lab_request() both read/write this field directly -
		# without it, get_pending_labs() throws "Unknown column
		# 'lt.custom_invoice'" since Lab Test has no built-in Sales Invoice
		# link (only a boolean `invoiced` Check field).
		"Lab Test": [
			{
				"fieldname": "custom_invoice",
				"label": "Invoice",
				"fieldtype": "Link",
				"insert_after": "invoiced",
				"options": "Sales Invoice",
				"reqd": 0,
				"hidden": 0,
			},
		],
		# Rehab Portal: same custom_invoice pattern as Lab Test above -
		# Therapy Plan has no built-in Sales Invoice link either (confirmed
		# via DESCRIBE `tabTherapy Plan`: only `invoiced` Check exists, no
		# `invoice` field). rehab_portal.py's get_pending_therapies() and
		# accept_therapy_request() both read/write custom_invoice directly.
		"Therapy Plan": [
			{
				"fieldname": "custom_invoice",
				"label": "Invoice",
				"fieldtype": "Link",
				"insert_after": "invoiced",
				"options": "Sales Invoice",
				"reqd": 0,
				"hidden": 0,
			},
		],
		# Rehab Portal: same pattern as Lab Prescription, for therapies.
		"Therapy Plan Detail": [
			{
				"fieldname": "custom_priority",
				"label": "Priority",
				"fieldtype": "Select",
				"insert_after": "interval",
				"options": "\nLow\nMedium\nHigh",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_therapy_plan",
				"label": "Therapy Plan",
				"fieldtype": "Link",
				"insert_after": "custom_priority",
				"options": "Therapy Plan",
				"reqd": 0,
				"hidden": 0,
			},
		],
		# Front Desk: drives the walk-in patient journey (receptionist ->
		# nurse -> doctor). front_desk.py's create_consultation()/
		# get_queue()/send_to_nurse()/save_vitals()/start_consultation() all
		# read/write these fields directly - without them, get_queue()
		# throws "Unknown column 'queue_status'" (as seen when this was
		# tried as a standalone fixture instead of going through
		# make_custom_fields()).
		"Patient Appointment": [
			{
				"fieldname": "queue_status",
				"label": "Queue Status",
				"fieldtype": "Select",
				"insert_after": "status",
				"options": "Registered\nPayment Pending\nPaid - Awaiting Vitals\nWith Nurse\nWith Doctor\nIn Consultation\nCompleted\nCancelled",
				"default": "Registered",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "front_desk_section",
				"label": "Front Desk / Nurse Station",
				"fieldtype": "Section Break",
				"insert_after": "queue_status",
				"collapsible": 1,
			},
			{
				"fieldname": "consultation_invoice",
				"label": "Consultation Invoice",
				"fieldtype": "Link",
				"insert_after": "front_desk_section",
				"options": "Sales Invoice",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "checked_in_at",
				"label": "Checked In At",
				"fieldtype": "Datetime",
				"insert_after": "consultation_invoice",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "vitals_column_break",
				"label": "",
				"fieldtype": "Column Break",
				"insert_after": "checked_in_at",
			},
			{
				"fieldname": "vitals_temperature",
				"label": "Temperature (\u00b0C)",
				"fieldtype": "Float",
				"insert_after": "vitals_column_break",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "vitals_blood_pressure",
				"label": "Blood Pressure",
				"fieldtype": "Data",
				"insert_after": "vitals_temperature",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "vitals_pulse",
				"label": "Pulse (bpm)",
				"fieldtype": "Int",
				"insert_after": "vitals_blood_pressure",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "vitals_weight",
				"label": "Weight (kg)",
				"fieldtype": "Float",
				"insert_after": "vitals_pulse",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "vitals_height",
				"label": "Height (cm)",
				"fieldtype": "Float",
				"insert_after": "vitals_weight",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "vitals_notes",
				"label": "Nurse Notes",
				"fieldtype": "Small Text",
				"insert_after": "vitals_height",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "vitals_recorded_by",
				"label": "Vitals Recorded By",
				"fieldtype": "Link",
				"insert_after": "vitals_notes",
				"options": "User",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "vitals_recorded_on",
				"label": "Vitals Recorded On",
				"fieldtype": "Datetime",
				"insert_after": "vitals_recorded_by",
				"reqd": 0,
				"hidden": 0,
			},
		],
		# Front Desk: post-refactor, queue state lives on Patient Encounter
		# itself (not Patient Appointment) — see front_desk.py's
		# check_in_appointment()/get_queue()/send_to_nurse()/save_vitals()/
		# start_consultation()/on_patient_encounter_submit(), all of which
		# read/write these fields directly on Patient Encounter.
		"Patient Encounter": [
			{
				"fieldname": "queue_status",
				"label": "Queue Status",
				"fieldtype": "Select",
				"insert_after": "encounter_time",
				"options": "Registered\nPayment Pending\nPaid - Awaiting Vitals\nWith Nurse\nWith Doctor\nIn Consultation\nCompleted\nCancelled",
				"default": "Registered",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "front_desk_section",
				"label": "Front Desk / Nurse Station",
				"fieldtype": "Section Break",
				"insert_after": "queue_status",
				"collapsible": 1,
			},
			{
				"fieldname": "consultation_invoice",
				"label": "Consultation Invoice",
				"fieldtype": "Link",
				"insert_after": "front_desk_section",
				"options": "Sales Invoice",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "checked_in_at",
				"label": "Checked In At",
				"fieldtype": "Datetime",
				"insert_after": "consultation_invoice",
				"reqd": 0,
				"hidden": 0,
			},
		],
		# Front Desk / Nurse Station: the standard Healthcare "Vital Signs"
		# doctype covers temperature/pulse/bp_systolic/bp_diastolic/height/
		# weight/bmi/vital_signs_note out of the box, but has no fields for
		# SpO2, FBS (Fasting Blood Sugar), or RBS (Random Blood Sugar).
		# front_desk.py's save_vitals() sets these three directly on the
		# Vital Signs doc it creates for each nurse-station recording.
		"Vital Signs": [
			{
				"fieldname": "custom_spo2",
				"label": "SpO2 (%)",
				"fieldtype": "Int",
				"insert_after": "bp",
				"non_negative": 1,
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_fbs",
				"label": "FBS (mg/dL)",
				"fieldtype": "Float",
				"insert_after": "custom_spo2",
				"non_negative": 1,
				"description": "Fasting Blood Sugar.",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_rbs",
				"label": "RBS (mg/dL)",
				"fieldtype": "Float",
				"insert_after": "custom_fbs",
				"non_negative": 1,
				"description": "Random Blood Sugar.",
				"reqd": 0,
				"hidden": 0,
			},
		],
		# Pharmacy POS: lets any Item in the "Pharmacy" item_group appear on
		# the Pharmacy POS grid with the same rich display as a
		# prescription-linked Medication, even when no Medication /
		# Medication Linked Item record exists for it - covers walk-in/OTC
		# drug sales where a patient buys off the shelf without a
		# consultation. get_pos_medications() in pharmacy.py reads all five
		# fields directly when building the OTC branch of the POS item list.
		#
		# custom_is_medication distinguishes an actual drug (paracetamol,
		# amoxicillin) from a non-drug Pharmacy item (gloves, syringes,
		# cotton, bandages) so pharmacy_pos.js can swap the card icon
		# (💊 vs 📦) and class label (medication_class vs "OTC").
		"Item": [
			{
				"fieldname": "custom_is_medication",
				"label": "Is Medication",
				"fieldtype": "Check",
				"insert_after": "item_group",
				"default": "0",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_medication_class",
				"label": "Medication Class",
				"fieldtype": "Link",
				"insert_after": "custom_is_medication",
				"options": "Medication Class",
				"depends_on": "eval:doc.custom_is_medication",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_strength",
				"label": "Strength",
				"fieldtype": "Data",
				"insert_after": "custom_medication_class",
				"depends_on": "eval:doc.custom_is_medication",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_strength_uom",
				"label": "Strength UOM",
				"fieldtype": "Link",
				"insert_after": "custom_strength",
				"options": "UOM",
				"depends_on": "eval:doc.custom_is_medication",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "custom_dosage_form",
				"label": "Dosage Form",
				"fieldtype": "Link",
				"insert_after": "custom_strength_uom",
				"options": "Dosage Form",
				"depends_on": "eval:doc.custom_is_medication",
				"reqd": 0,
				"hidden": 0,
			},
		],
		# Pharmacy POS: lets an admin configure which Item Group the POS's
		# walk-in/OTC branch pulls from, instead of hardcoding "Pharmacy".
		# Read by pharmacy.py's get_pos_medications()/get_pharmacy_settings()
		# and written by set_pharmacy_item_group().
		# "Healthcare Settings": [
		# 	{
		# 		"fieldname": "pharmacy_item_group",
		# 		"label": "Pharmacy Item Group",
		# 		"fieldtype": "Link",
		# 		"options": "Item Group",
		# 		"insert_after": "allow_oversell_medication",
		# 		"description": "Item Group shown in Pharmacy POS for walk-in/OTC items.",
		# 		"reqd": 0,
		# 		"hidden": 0,
		# 	},
		# ],
		"Healthcare Settings": [
			{
				"fieldname": "pharmacy_item_group",
				"label": "Pharmacy Item Group",
				"fieldtype": "Link",
				"options": "Item Group",
				"insert_after": "allow_oversell_medication",
				"description": "Item Group shown in Pharmacy POS for walk-in/OTC items.",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "auto_generate_patient_uid",
				"label": "Auto-generate Patient UID",
				"fieldtype": "Check",
				"insert_after": "pharmacy_item_group",
				"description": "Automatically generate the Identification Number (UID) for new patients instead of requiring front desk / nursing staff to enter one manually.",
				"default": "0",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "patient_uid_naming_series",
				"label": "Patient UID Naming Series",
				"fieldtype": "Data",
				"insert_after": "auto_generate_patient_uid",
				"description": "Pattern used to auto-generate the UID, e.g. UID-.YYYY.-.#####. Only used when Auto-generate Patient UID is checked.",
				"depends_on": "eval:doc.auto_generate_patient_uid",
				"default": "UID-.#####",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "front_desk_access_section",
				"label": "Front Desk Tab Access",
				"fieldtype": "Section Break",
				"insert_after": "patient_uid_naming_series",
				"collapsible": 1,
				"description": (
					"Comma-separated Role lists controlling which Front Desk tabs "
					"each tab is restricted to. Leave a field blank to leave that "
					"tab open to anyone with Front Desk page access."
				),
			},
			{
				"fieldname": "front_desk_checkin_roles",
				"label": "Check-In Tab Roles",
				"fieldtype": "Small Text",
				"insert_after": "front_desk_access_section",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "front_desk_queue_roles",
				"label": "Queue Tab Roles",
				"fieldtype": "Small Text",
				"insert_after": "front_desk_checkin_roles",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "front_desk_access_column_break",
				"fieldtype": "Column Break",
				"insert_after": "front_desk_queue_roles",
			},
			{
				"fieldname": "front_desk_nurse_roles",
				"label": "Nurse Station Tab Roles",
				"fieldtype": "Small Text",
				"insert_after": "front_desk_access_column_break",
				"default": "Nursing User,Physician",
				"reqd": 0,
				"hidden": 0,
			},
			{
				"fieldname": "front_desk_doctor_roles",
				"label": "Doctor Queue Tab Roles",
				"fieldtype": "Small Text",
				"insert_after": "front_desk_nurse_roles",
				"default": "Physician",
				"reqd": 0,
				"hidden": 0,
			},
		],

	}