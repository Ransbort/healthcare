import json
from pathlib import Path

import frappe


def workspace_installer():
	app_name = "healthcare"
	workspace_dir = Path(frappe.get_app_path(app_name)) / app_name / "workspace_sidebar"

	for workspace_file in workspace_dir.rglob("*.json"):
		_reinstall_workspace_from_file(workspace_file)


def workspace_remover():
	app_name = "healthcare"
	workspace_dir = Path(frappe.get_app_path(app_name)) / app_name / "workspace_sidebar"

	for workspace_file in workspace_dir.rglob("*.json"):
		workspace_data = _load_workspace_data(workspace_file)
		if not workspace_data:
			continue
		workspace_name = workspace_data.get("name") or workspace_data.get("label")
		if workspace_name:
			_remove_workspace(workspace_name, workspace_data.get("doctype", "Workspace Sidebar"))


def _reinstall_workspace_from_file(workspace_file: Path):
	workspace_data = _load_workspace_data(workspace_file)
	if not workspace_data:
		return

	workspace_name = workspace_data.get("name") or workspace_data.get("label")
	if not workspace_name:
		frappe.log_error(
			title="Workspace Migration Failed",
			message=f"Workspace in {workspace_file} has no name or label"
		)
		return

	doctype = workspace_data.get("doctype", "Workspace Sidebar")
	_remove_workspace(workspace_name, doctype)
	_install_workspace(workspace_data, workspace_name)


def _remove_workspace(workspace_name: str, doctype: str = "Workspace Sidebar"):
	if not frappe.db.exists(doctype, workspace_name):
		return
	try:
		frappe.delete_doc(doctype, workspace_name, force=True, ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title=f"Failed to Remove Workspace: {workspace_name}",
			message=frappe.get_traceback()
		)


def _install_workspace(workspace_data: dict, workspace_name: str):
	try:
		workspace_doc = frappe.get_doc(workspace_data)
		workspace_doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
	except Exception:
		frappe.log_error(
			title=f"Workspace Installation Failed: {workspace_name}",
			message=frappe.get_traceback()
		)


def _load_workspace_data(workspace_file: Path):
	if not workspace_file.exists():
		frappe.log_error(
			title="Workspace File Not Found",
			message=f"Expected workspace file at: {workspace_file}"
		)
		return None
	try:
		workspace_data = json.loads(workspace_file.read_text(encoding="utf-8"))
	except json.JSONDecodeError:
		frappe.log_error(
			title="Invalid Workspace JSON",
			message=f"Failed to parse: {workspace_file}\n\n{frappe.get_traceback()}"
		)
		return None

	# Accept either a single object ({...}) or a one-item array ([{...}])
	if isinstance(workspace_data, list):
		if not workspace_data:
			frappe.log_error(
				title="Invalid Workspace Structure",
				message=f"Workspace JSON array is empty: {workspace_file}"
			)
			return None
		workspace_data = workspace_data[0]
	elif not isinstance(workspace_data, dict):
		frappe.log_error(
			title="Invalid Workspace Structure",
			message=f"Workspace JSON must be an object or a non-empty array: {workspace_file}"
		)
		return None

	return workspace_data
