frappe.pages['doctor-station'].on_page_load = function(wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Doctor Station',
		single_column: true
	});

	// =============================================
	// REALTIME SOUND NOTIFICATIONS
	// =============================================
	// Same pattern as Front Desk / Nurse Station / Laboratory Portal - a
	// doctor working something else (an open Encounter, another patient)
	// still hears/sees a new arrival instead of having to keep this tab
	// in view. Fires whenever Nurse Station finishes vitals and sends a
	// patient on (see nurse_station.py's save_vitals()) or an app layered
	// on top of Healthcare routes one here directly - department 'doctor'
	// for the Doctor Queue, 'laboratory' for the Lab tab (fired by
	// sports_complex's route_trial_after_vitals() the moment a trial
	// panel's created, and by lab_portal.py whenever any new lab request
	// comes in - a harmless bonus refresh there, not required for the
	// trial flow itself).
	const notificationSound = new Audio('/assets/healthcare/sounds/notify.mp3');

	let audioUnlocked = false;
	function unlockAudio() {
		if (audioUnlocked) return;
		notificationSound.play().then(() => {
			notificationSound.pause();
			notificationSound.currentTime = 0;
			audioUnlocked = true;
		}).catch(() => {});
	}
	document.addEventListener('click', unlockAudio, { once: true });
	document.addEventListener('keydown', unlockAudio, { once: true });

	function playNotification() {
		try {
			notificationSound.currentTime = 0;
			notificationSound.play().catch(() => {});
		} catch (e) {
			console.warn('Notification sound error:', e);
		}
	}

	frappe.realtime.on('queue_update', function(data) {
		if (data.department !== 'doctor' && data.department !== 'laboratory') return;
		playNotification();
		frappe.show_alert({
			message: data.message,
			indicator: 'blue'
		}, 6);
		loadAll();
	});

	// =============================================
	// STYLES - same visual language as Laboratory Portal / Nurse Station
	// (toolbar with icon badge, card-style search sections, tabs with
	// badge counts) so every portal reads as one system.
	// =============================================
	const style = `
		<style>
			.ds-wrapper { padding: 20px; max-width: 1400px; margin: 0 auto; }

			.sticky-header {
				position: sticky;
				top: 0;
				z-index: 100;
				background: var(--fg-color, white);
				padding-bottom: 16px;
				margin-bottom: 20px;
			}

			/* --- Toolbar: title + actions --- */
			.ds-toolbar {
				display: flex;
				justify-content: space-between;
				align-items: center;
				padding-bottom: 16px;
				margin-bottom: 16px;
				border-bottom: 1px solid #e9ecef;
			}

			.ds-toolbar-title {
				display: flex;
				align-items: center;
				gap: 12px;
			}

			.ds-toolbar-title .icon-badge {
				width: 40px;
				height: 40px;
				border-radius: 10px;
				background: #f0f1fe;
				color: var(--primary-color);
				display: flex;
				align-items: center;
				justify-content: center;
				font-size: 17px;
				flex-shrink: 0;
			}

			.ds-toolbar-title h4 {
				margin: 0;
				font-size: 1.2rem;
				font-weight: 700;
				color: #1a1a2e;
				line-height: 1.3;
			}

			.ds-toolbar-title .ds-toolbar-subtitle {
				font-size: 0.83rem;
				color: #868e96;
				margin-top: 1px;
			}

			.ds-toolbar-actions {
				display: flex;
				align-items: center;
				gap: 10px;
			}

			.btn-icon {
				width: 38px;
				height: 38px;
				border-radius: 8px;
				border: 1px solid #dee2e6;
				background: white;
				color: #495057;
				display: flex;
				align-items: center;
				justify-content: center;
				cursor: pointer;
				transition: all 0.15s ease;
				font-size: 0.95rem;
			}

			.btn-icon:hover {
				background: #f8f9fa;
				border-color: var(--primary-color);
				color: var(--primary-color);
			}

			/* --- Last updated --- */
			.ds-wrapper .last-updated {
				display: flex;
				align-items: center;
				gap: 6px;
				font-size: 0.78rem;
				color: #adb5bd !important;
				padding: 4px 2px 0;
			}

			/* --- Search / filter card, shared by every tab --- */
			.ds-wrapper .search-section {
				background: #ffffff !important;
				background-image: none !important;
				border: 1px solid #e9ecef;
				border-radius: 12px;
				padding: 16px 20px;
				margin-bottom: 16px;
				box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
			}

			.search-input-group {
				display: flex;
				flex-wrap: wrap;
				gap: 14px;
				align-items: end;
			}

			.search-input-group .frappe-control { flex: 1; min-width: 200px; }
			.search-input-group .form-group { margin-bottom: 0; }
			.ds-wrapper .search-input-group label { color: #495057 !important; font-weight: 500; font-size: 0.83rem; }
			.search-input-group .form-control { border-radius: 8px; border: 1px solid #dee2e6; }

			#doctor-refresh-date-btn, #patient-search-btn {
				border-radius: 8px;
				font-weight: 600;
				padding: 8px 18px;
			}

			#patient-search-clear-btn {
				border-radius: 8px;
				font-weight: 600;
				padding: 8px 16px;
				background: transparent;
				border: 1px solid #dee2e6;
				color: #495057;
			}

			#patient-search-clear-btn:hover { background: #f8f9fa; }

			/* --- Tabs --- */
			.tabs-section {
				display: flex;
				gap: 10px;
				margin-bottom: 16px;
				border-bottom: 2px solid #e0e0e0;
				align-items: center;
				overflow-x: auto;
				/* overflow-x alone leaves overflow-y at its default
				   (visible), which the CSS overflow spec then silently
				   promotes to auto too - so a tab row even a pixel taller
				   than its own line height (badge/icon rounding vs. the
				   plain text baseline) picks up a stray vertical
				   scrollbar. Pinning overflow-y explicitly keeps only the
				   horizontal scroll this was meant to allow, for a tab row
				   that doesn't fit a narrow screen - same fix as Nurse
				   Station's own .tabs-section. */
				overflow-y: hidden;
			}

			.tab-btn {
				padding: 12px 20px;
				background: transparent;
				border: none;
				border-bottom: 3px solid transparent;
				color: #6c757d;
				font-weight: 600;
				font-size: 0.95rem;
				cursor: pointer;
				transition: all 0.2s ease;
				position: relative;
				bottom: -2px;
				white-space: nowrap;
			}

			.tab-btn:hover { color: var(--primary-color); }
			.tab-btn.active { color: var(--primary-color); border-bottom-color: var(--primary-color); }
			.tab-btn .badge { margin-left: 8px; font-size: 0.78rem; padding: 3px 8px; }

			.tab-content { display: none; }
			.tab-content.active { display: block; }

			.scrollable-content { padding-right: 4px; }

			/* --- Tables --- */
			.queue-table { width: 100%; border-collapse: collapse; }
			.queue-table-container {
				background: white; border-radius: 8px; overflow: hidden;
				box-shadow: 0 2px 8px rgba(0,0,0,0.08);
			}
			.queue-table thead { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
			.queue-table th { padding: 12px; text-align: left; font-weight: 600; font-size: 0.9rem; }
			.queue-table td { padding: 12px; font-size: 0.9rem; border-bottom: 1px solid #e9ecef; }
			.queue-table tbody tr:hover { background: #f8f9fa; }

			.lab-pill { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; margin: 1px 3px 1px 0; }
			.lab-pill-done { background: #d4edda; color: #155724; }
			.lab-pill-pending { background: #fff3cd; color: #856404; }

			.badge-registered { background: #e2e3e5; color: #383d41; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-active { background: #d4edda; color: #155724; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-disabled { background: #f8d7da; color: #842029; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }

			.empty-state { text-align: center; padding: 60px 20px; color: #6c757d; }
			.empty-state i { font-size: 64px; margin-bottom: 20px; opacity: 0.3; }
			.empty-state h4 { font-size: 1.3rem; margin-bottom: 10px; color: #495057; }
			.empty-state p { font-size: 1rem; margin: 0; }

			@media (max-width: 768px) {
				.ds-wrapper { padding: 15px; }
				.ds-toolbar { flex-direction: column; align-items: flex-start; gap: 12px; }
				.ds-toolbar-actions { width: 100%; justify-content: flex-end; }
				.search-input-group { flex-direction: column; align-items: stretch; }
				.search-input-group .frappe-control { min-width: 0; }
			}
		</style>
	`;
	$(style).appendTo(page.main);

	// =============================================
	// MARKUP
	// =============================================
	let html = `
		<div class="ds-wrapper">
			<div class="sticky-header">
				<div class="ds-toolbar">
					<div class="ds-toolbar-title">
						<div class="icon-badge"><i class="fa fa-user-md"></i></div>
						<div>
							<h4>${__('Doctor Station')}</h4>
							<div class="ds-toolbar-subtitle">${__('Consultation queue & patient lookup')}</div>
						</div>
					</div>
					<div class="ds-toolbar-actions">
						<button class="btn-icon" id="ds-refresh-btn" title="${__('Refresh')}">
							<i class="fa fa-refresh"></i>
						</button>
					</div>
				</div>

				<div class="last-updated">
					<i class="fa fa-clock-o"></i>
					<span id="last-updated-time">${__('Not loaded yet')}</span>
				</div>

				<div class="tabs-section">
					<button class="tab-btn active" data-tab="queue">
						<i class="fa fa-stethoscope"></i> ${__('Doctor Queue')}
						<span class="badge badge-info" id="queue-count">0</span>
					</button>
					<button class="tab-btn" data-tab="lab">
						<i class="fa fa-flask"></i> ${__('Lab')}
						<span class="badge badge-warning" id="lab-count">0</span>
					</button>
					<button class="tab-btn" data-tab="search">
						<i class="fa fa-search"></i> ${__('Patient Search')}
						<span class="badge" id="search-count">0</span>
					</button>
				</div>
			</div>

			<!-- DOCTOR QUEUE TAB -->
			<div class="tab-content active" id="queue-tab">
				<div class="search-section">
					<div class="search-input-group">
						<div data-fieldname="doc_date"></div>
						<button class="btn btn-primary" id="doctor-refresh-date-btn">
							<i class="fa fa-filter"></i> ${__('Filter')}
						</button>
					</div>
				</div>
				<div class="scrollable-content">
					<div class="queue-table-container" id="doctor-queue-container"></div>
				</div>
			</div>

			<!-- LAB TAB -->
			<!-- Trial-candidate patients parked at queue_status "With Lab" -
			     see sports_complex's route_trial_after_vitals()/
			     create_trial_lab_panel(). Data and actions here come
			     straight from sports_complex.healthcare_integration's own
			     whitelisted methods (get_trial_lab_queue()/
			     send_trial_to_doctor()), not from doctor_station.py - this
			     tab moved over from Front Desk's old Lab tab as-is, no
			     backend changes needed on the Healthcare app's side. -->
			<div class="tab-content" id="lab-tab">
				<div class="search-section">
					<div class="search-input-group">
						<div data-fieldname="lab_date"></div>
						<button class="btn btn-primary" id="lab-refresh-date-btn">
							<i class="fa fa-filter"></i> ${__('Filter')}
						</button>
					</div>
				</div>
				<div class="scrollable-content">
					<div class="queue-table-container" id="lab-queue-container"></div>
				</div>
			</div>

			<!-- PATIENT SEARCH TAB -->
			<div class="tab-content" id="search-tab">
				<div class="search-section">
					<div class="search-input-group">
						<div data-fieldname="patient_search"></div>
						<button class="btn btn-primary" id="patient-search-btn">
							<i class="fa fa-search"></i> ${__('Search')}
						</button>
						<button class="btn" id="patient-search-clear-btn">${__('Clear')}</button>
					</div>
				</div>
				<div class="scrollable-content">
					<div class="queue-table-container" id="patient-search-container"></div>
				</div>
			</div>
		</div>
	`;
	$(html).appendTo(page.main);

	function statusBadge(status) {
		const map = {
			'Active': 'badge-active',
			'Disabled': 'badge-disabled'
		};
		return `<span class="${map[status] || 'badge-registered'}">${status || ''}</span>`;
	}

	// Tracks how many of the loads kicked off by loadAll() are still in
	// flight, so "Last updated" only refreshes once everything currently
	// on screen is current - same pattern Nurse Station / Laboratory
	// Portal use.
	let pendingLoads = 0;
	function markLoadDone() {
		pendingLoads = Math.max(0, pendingLoads - 1);
		if (pendingLoads === 0) {
			const now = new Date();
			const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
			page.main.find('#last-updated-time').text(`${__('Updated at')} ${timeStr}`);
		}
	}

	function loadAll() {
		pendingLoads = 2;
		loadDoctorQueue();
		loadLabQueue();
		// Patient Search deliberately doesn't auto-load on a blank term
		// (see search_patients()'s docstring) - only re-run it here if
		// there's already a search in progress, so a refresh keeps
		// whatever the doctor was just looking at current too.
		if (patient_search_field.get_value()) {
			pendingLoads += 1;
			loadPatientSearch();
		}
	}

	// =============================================
	// TAB SWITCHING
	// =============================================
	page.main.find('.tab-btn').on('click', function() {
		const tab = $(this).data('tab');
		page.main.find('.tab-btn').removeClass('active');
		$(this).addClass('active');
		page.main.find('.tab-content').removeClass('active');
		page.main.find(`#${tab}-tab`).addClass('active');
	});

	page.main.find('#ds-refresh-btn').on('click', function() {
		const $icon = $(this).find('i');
		$icon.addClass('fa-spin');
		loadAll();
		setTimeout(() => $icon.removeClass('fa-spin'), 600);
	});

	// =============================================
	// DOCTOR QUEUE
	// =============================================
	let doc_date = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="doc_date"]'),
		df: { fieldtype: 'Date', fieldname: 'doc_date', label: 'Date', default: frappe.datetime.get_today() },
		render_input: true
	});
	doc_date.refresh();
	doc_date.set_value(frappe.datetime.get_today());

	page.main.find('#doctor-refresh-date-btn').on('click', function() { loadDoctorQueue(); });

	function loadDoctorQueue() {
		frappe.call({
			method: 'healthcare.healthcare.page.doctor_station.doctor_station.get_doctor_queue',
			args: { date: doc_date.get_value() },
			callback: function(r) {
				renderDoctorQueue(r.message || []);
				markLoadDone();
			}
		});
	}

	function renderDoctorQueue(rows) {
		page.main.find('#queue-count').text(rows.length);
		const container = page.main.find('#doctor-queue-container');
		if (!rows.length) {
			container.html(`<div class="empty-state"><i class="fa fa-stethoscope"></i><h4>${__('No patients waiting')}</h4><p>${__('Patients sent on from Nurse Station will show up here.')}</p></div>`);
			return;
		}
		let body = '';
		rows.forEach(function(row) {
			const vitalsSummary = [
				row.vitals_temperature ? `${row.vitals_temperature}°C` : null,
				row.vitals_blood_pressure || null,
				row.vitals_pulse ? `${row.vitals_pulse} bpm` : null,
				row.vitals_bmi ? `BMI ${row.vitals_bmi}` : null,
				row.vitals_spo2 ? `SpO2 ${row.vitals_spo2}%` : null,
				row.vitals_fbs ? `FBS ${row.vitals_fbs}` : null,
				row.vitals_rbs ? `RBS ${row.vitals_rbs}` : null
			].filter(Boolean).join(' · ') || __('No vitals recorded');
			body += `
				<tr>
					<td>${row.encounter_time || ''}</td>
					<td>${row.patient_name || ''}</td>
					<td>${row.practitioner_name || row.practitioner || ''}</td>
					<td>${row.appointment_type || ''}</td>
					<td><small>${vitalsSummary}</small></td>
					<td><button class="btn btn-xs btn-success btn-start-consult" data-name="${row.name}">${__('Start Consultation')}</button></td>
				</tr>
			`;
		});
		container.html(`
			<table class="queue-table">
				<thead><tr><th>${__('Time')}</th><th>${__('Patient')}</th><th>${__('Practitioner')}</th><th>${__('Appointment Type')}</th><th>${__('Vitals')}</th><th></th></tr></thead>
				<tbody>${body}</tbody>
			</table>
		`);
		container.find('.btn-start-consult').on('click', function() {
			const name = $(this).data('name');
			frappe.call({
				method: 'healthcare.healthcare.page.doctor_station.doctor_station.start_consultation',
				args: { appointment: name },
				callback: function(r) {
					if (r.message && r.message.status === 'Success') {
						const encounterName = r.message.encounter;
						// Creates the Patient Encounter (if one doesn't already
						// exist for this appointment) and opens it.
						//
						// Two SPA-navigation attempts here (loading the
						// doctype's metadata via frappe.model.with_doctype()
						// first, then separately trying set_route().then()
						// + clear_doc()/reload_doc()) both still left the
						// page half-rendered until a manual refresh - the
						// generic footer (Comments/Activity) shows, but the
						// doctype's own field layout/dashboard doesn't.
						// Both rely on set_route()'s returned promise lining
						// up with cur_frm actually pointing at the new doc
						// by the time it resolves, and that assumption isn't
						// holding here. A real browser navigation sidesteps
						// the whole SPA route/render pipeline - it's the
						// exact same code path a manual refresh takes, so
						// there's no internal timing to get wrong.
						window.location.href = frappe.utils.get_form_link('Patient Encounter', encounterName);
					}
				}
			});
		});
	}

	// =============================================
	// LAB (moved over from Front Desk's old Lab tab as-is - see the
	// markup comment above for why there's no doctor_station.py
	// involvement here)
	// =============================================
	let lab_date = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="lab_date"]'),
		df: { fieldtype: 'Date', fieldname: 'lab_date', label: 'Date', default: frappe.datetime.get_today() },
		render_input: true
	});
	lab_date.refresh();
	lab_date.set_value(frappe.datetime.get_today());

	page.main.find('#lab-refresh-date-btn').on('click', function() { loadLabQueue(); });

	function loadLabQueue() {
		frappe.call({
			method: 'sports_complex.sports_complex.healthcare_integration.get_trial_lab_queue',
			args: { date: lab_date.get_value() },
			callback: function(r) {
				renderLabQueue(r.message || []);
				markLoadDone();
			}
		});
	}

	function renderLabQueue(rows) {
		page.main.find('#lab-count').text(rows.length);
		const container = page.main.find('#lab-queue-container');
		if (!rows.length) {
			container.html(`<div class="empty-state"><i class="fa fa-flask"></i><h4>${__('No trialists waiting on labs')}</h4></div>`);
			return;
		}
		let body = '';
		rows.forEach(function(row) {
			const testPills = (row.tests || []).map(function(t) {
				const cls = t.status === 'Completed' ? 'lab-pill-done' : 'lab-pill-pending';
				return `<span class="lab-pill ${cls}">${frappe.utils.escape_html(t.template)}: ${frappe.utils.escape_html(t.status)}</span>`;
			}).join(' ');
			const ready = !!row.ready_for_doctor;
			const btnClass = ready ? 'btn-success' : 'btn-warning';
			const btnLabel = ready ? __('Send to Doctor') : __('Send to Doctor (Override)');
			body += `
				<tr>
					<td>${row.encounter_time || ''}</td>
					<td>${row.patient_name || ''}</td>
					<td>${row.practitioner_name || row.practitioner || ''}</td>
					<td><small>${testPills || __('No tests configured')}</small></td>
					<td>${row.tests_completed || 0}/${row.tests_total || 0}</td>
					<td><button class="btn btn-xs ${btnClass} btn-send-doctor" data-name="${row.name}" data-ready="${ready ? '1' : '0'}">${btnLabel}</button></td>
				</tr>
			`;
		});
		container.html(`
			<table class="queue-table">
				<thead><tr><th>${__('Time')}</th><th>${__('Patient')}</th><th>${__('Practitioner')}</th><th>${__('Required Tests')}</th><th>${__('Progress')}</th><th></th></tr></thead>
				<tbody>${body}</tbody>
			</table>
		`);

		container.find('.btn-send-doctor').on('click', function() {
			const name = $(this).data('name');
			const ready = $(this).data('ready') === 1 || $(this).data('ready') === '1';

			if (ready) {
				sendTrialToDoctor(name, null);
				return;
			}

			// Not every required test is Completed yet - this only
			// succeeds server-side for a user with lab override
			// permission (front_desk_lab_override_roles in Healthcare
			// Settings); everyone else gets a clear permission error back
			// from the call below. A reason is always required.
			const dialog = new frappe.ui.Dialog({
				title: __('Send to Doctor Before Labs Are Complete'),
				fields: [
					{
						fieldtype: 'Small Text',
						fieldname: 'reason',
						label: __('Reason'),
						reqd: 1,
						description: __('Recorded as a comment on the appointment.')
					}
				],
				primary_action_label: __('Send Anyway'),
				primary_action: function(values) {
					dialog.hide();
					sendTrialToDoctor(name, values.reason);
				}
			});
			dialog.show();
		});
	}

	function sendTrialToDoctor(appointment, overrideReason) {
		frappe.call({
			method: 'sports_complex.sports_complex.healthcare_integration.send_trial_to_doctor',
			args: { appointment: appointment, override_reason: overrideReason },
			freeze: true,
			freeze_message: __('Sending to doctor...'),
			callback: function(r) {
				if (r.message && r.message.status === 'Success') {
					frappe.show_alert({ message: __('Sent to doctor'), indicator: 'green' }, 5);
					loadLabQueue();
				}
			}
		});
	}

	// =============================================
	// PATIENT SEARCH
	// =============================================
	// Search across every patient in the system (not just today's queue,
	// or this doctor's own appointments) - by name, Patient ID, or mobile
	// number. A blank term deliberately returns nothing rather than the
	// full Patient list - see search_patients()'s docstring - so the tab
	// starts with a hint rather than an empty table.
	let patient_search_field = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="patient_search"]'),
		df: {
			fieldtype: 'Data',
			fieldname: 'patient_search',
			label: __('Search'),
			placeholder: __('Name, Patient ID, or mobile number')
		},
		render_input: true
	});
	patient_search_field.refresh();

	page.main.find('#patient-search-btn').on('click', function() { loadPatientSearch(); });
	patient_search_field.$input.on('keydown', function(e) {
		if (e.key === 'Enter') loadPatientSearch();
	});

	page.main.find('#patient-search-clear-btn').on('click', function() {
		patient_search_field.set_value('');
		renderPatientSearch([], { cleared: true });
	});

	function loadPatientSearch() {
		frappe.call({
			method: 'healthcare.healthcare.page.doctor_station.doctor_station.search_patients',
			args: { search_text: patient_search_field.get_value() },
			callback: function(r) {
				renderPatientSearch(r.message || []);
				markLoadDone();
			}
		});
	}

	function renderPatientSearch(records, opts) {
		opts = opts || {};
		page.main.find('#search-count').text(records.length);
		const container = page.main.find('#patient-search-container');

		if (!records.length) {
			const searched = !opts.cleared && !!patient_search_field.get_value();
			container.html(`
				<div class="empty-state">
					<i class="fa fa-search"></i>
					<h4>${searched ? __('No patients found') : __('Search for a patient')}</h4>
					<p>${searched ? __('Try a different name, Patient ID, or mobile number.') : __('Enter a name, Patient ID, or mobile number above to look up any patient in the system.')}</p>
				</div>
			`);
			return;
		}

		let body = '';
		records.forEach(function(record) {
			body += `
				<tr class="patient-row" data-name="${record.name}">
					<td>${record.name || ''}</td>
					<td>${record.patient_name || ''}</td>
					<td>${record.sex || ''}</td>
					<td>${record.dob ? frappe.datetime.str_to_user(record.dob) : ''}</td>
					<td>${record.mobile || ''}</td>
					<td>${record.blood_group || ''}</td>
					<td>${statusBadge(record.status)}</td>
					<td>
						<button class="btn btn-xs btn-default btn-view-patient" data-name="${record.name}">${__('View')}</button>
					</td>
				</tr>
			`;
		});
		container.html(`
			<table class="queue-table">
				<thead>
					<tr>
						<th>${__('Patient ID')}</th>
						<th>${__('Name')}</th>
						<th>${__('Sex')}</th>
						<th>${__('DOB')}</th>
						<th>${__('Mobile')}</th>
						<th>${__('Blood Group')}</th>
						<th>${__('Status')}</th>
						<th></th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		`);

		container.find('.btn-view-patient').on('click', function() {
			// Same SPA-navigation issue Start Consultation had (frappe.
			// set_route() alone leaves the page half-rendered until a
			// manual refresh - see the click handler on start_consultation()
			// above for the full writeup) - a real browser navigation
			// sidesteps the SPA route/render pipeline entirely.
			window.location.href = frappe.utils.get_form_link('Patient', $(this).data('name'));
		});
	}

	renderPatientSearch([]);
	loadAll();
};

//# sourceURL=doctor_station.js
