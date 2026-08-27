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
	// in view. Sound + toast only for department 'doctor' (someone is
	// actually ready for consultation now) - 'nurse'/'laboratory' events
	// just mean a patient moved a step through the pipeline the Doctor
	// Queue tab now shows in full, so those refresh the table quietly
	// without interrupting the doctor for something that isn't theirs to
	// act on yet.
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
		if (!['doctor', 'nurse', 'laboratory'].includes(data.department)) return;
		if (data.department === 'doctor') {
			playNotification();
			frappe.show_alert({
				message: data.message,
				indicator: 'blue'
			}, 6);
		}
		loadAll();
	});

	// Admission Order accept/reject outcome, targeted (server-side, via
	// frappe.publish_realtime's user= param - see admission_order.py's
	// _notify_referring_practitioner()) at just the practitioner who
	// placed the order, not a department-wide broadcast. Only reaches
	// this doctor if they currently have Doctor Station open; either way
	// they also get a standard Notification Log (bell icon) entry, so
	// this is a bonus toast, not the only way they'd find out. No
	// loadAll() here - Doctor Station has no admission-order-related tab
	// of its own to refresh.
	frappe.realtime.on('admission_order_response', function(data) {
		playNotification();
		frappe.show_alert({
			message: data.message,
			indicator: 'blue'
		}, 6);
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

			.badge-registered { background: #e2e3e5; color: #383d41; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-active { background: #d4edda; color: #155724; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-disabled { background: #f8d7da; color: #842029; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }

			/* --- Pipeline stage badges (Doctor Queue tab) --- */
			.stage-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; white-space: nowrap; }
			.stage-frontdesk { background: #e2e3e5; color: #383d41; }
			.stage-nurse { background: #cfe2ff; color: #084298; }
			.stage-lab { background: #fff3cd; color: #856404; }
			.stage-doctor { background: #d4edda; color: #155724; }
			.stage-consultation { background: #e7d6fb; color: #5a2a8c; }

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

	// Formats a Patient Appointment "Time" field for display, e.g. "12:27pm".
	// These come back from the server in a couple of different raw shapes -
	// a proper zero-padded "HH:MM:SS[.ffffff]" most of the time, but
	// occasionally a Python timedelta's own str() instead ("0:03:14.657203",
	// no leading zero on a single-digit hour). Only the hour/minute matter
	// for display, and matching on \d+ rather than requiring two digits
	// handles both shapes the same way. Own copy in each of Front Desk /
	// Nurse Station / Doctor Station - same duplication this codebase
	// already uses for other small cross-page helpers, so all three read
	// the same "12:27pm" format without a shared module to keep in sync.
	function formatQueueTime(value) {
		if (!value) return '';
		const match = String(value).match(/^(\d+):(\d{2})/);
		if (!match) return value;
		let hours = parseInt(match[1], 10) % 24;
		const minutes = match[2];
		const period = hours >= 12 ? 'pm' : 'am';
		hours = hours % 12 || 12;
		return `${hours}:${minutes}${period}`;
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
		pendingLoads = 1;
		loadDoctorQueue();
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
				const rows = r.message || [];
				const hasLabRows = rows.some(function(row) { return row.queue_status === 'With Lab'; });

				if (!hasLabRows) {
					renderDoctorQueue(rows);
					markLoadDone();
					return;
				}

				// At least one patient's panel is still with the lab -
				// fetch per-test progress from sports_complex (this app
				// doesn't depend on it, so this is a separate call, not a
				// join - see get_doctor_queue()'s docstring) and merge it
				// in by appointment name before rendering. If the current
				// user can't reach that endpoint for some reason
				// (Healthcare Settings' front_desk_lab_roles gate), the
				// "With Lab" rows still render - just without a test
				// count.
				frappe.call({
					method: 'sports_complex.sports_complex.healthcare_integration.get_trial_lab_queue',
					args: { date: doc_date.get_value() },
					callback: function(labResult) {
						mergeLabProgress(rows, labResult.message || []);
						renderDoctorQueue(rows);
						markLoadDone();
					},
					error: function() {
						renderDoctorQueue(rows);
						markLoadDone();
					}
				});
			}
		});
	}

	function mergeLabProgress(rows, labRows) {
		const byAppointment = {};
		labRows.forEach(function(labRow) { byAppointment[labRow.name] = labRow; });
		rows.forEach(function(row) {
			const labRow = byAppointment[row.name];
			if (labRow) {
				row.lab_tests_completed = labRow.tests_completed;
				row.lab_tests_total = labRow.tests_total;
			}
		});
	}

	const STAGE_CLASS = {
		'Front Desk': 'stage-frontdesk',
		'With Nurse': 'stage-nurse',
		'With Lab': 'stage-lab',
		'With Doctor': 'stage-doctor',
		'In Consultation': 'stage-consultation'
	};

	function stageBadge(row) {
		const stage = row.stage || row.queue_status;
		const cls = STAGE_CLASS[stage] || 'stage-frontdesk';
		let label = __(stage);
		if (stage === 'With Lab' && row.lab_tests_total) {
			label += ` (${row.lab_tests_completed || 0}/${row.lab_tests_total})`;
		}
		return `<span class="stage-badge ${cls}">${label}</span>`;
	}

	function renderDoctorQueue(rows) {
		// The badge on the tab itself stays a glanceable "how many need me
		// right now" count - not the whole pipeline's size, which the
		// table body below shows in full.
		const readyCount = rows.filter(function(row) {
			return row.stage === 'With Doctor';
		}).length;
		page.main.find('#queue-count').text(readyCount);
		const container = page.main.find('#doctor-queue-container');
		if (!rows.length) {
			container.html(`<div class="empty-state"><i class="fa fa-stethoscope"></i><h4>${__('No patients checked in')}</h4><p>${__('Patients checked in at Front Desk will show up here, along with their progress through Nurse Station and the lab.')}</p></div>`);
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

			let actionCell;
			if (row.stage === 'With Doctor') {
				actionCell = `<button class="btn btn-xs btn-success btn-start-consult" data-name="${row.name}">${__('Start Consultation')}</button>`;
			} else if (row.stage === 'In Consultation') {
				actionCell = `<button class="btn btn-xs btn-primary btn-start-consult" data-name="${row.name}">${__('Continue')}</button>`;
			} else {
				actionCell = `<span class="text-muted">—</span>`;
			}

			body += `
				<tr>
					<td>${formatQueueTime(row.encounter_time)}</td>
					<td>${row.patient_name || ''}</td>
					<td>${row.practitioner_name || row.practitioner || ''}</td>
					<td>${row.appointment_type || ''}</td>
					<td>${stageBadge(row)}</td>
					<td><small>${vitalsSummary}</small></td>
					<td>${actionCell}</td>
				</tr>
			`;
		});
		container.html(`
			<table class="queue-table">
				<thead><tr><th>${__('Time')}</th><th>${__('Patient')}</th><th>${__('Practitioner')}</th><th>${__('Appointment Type')}</th><th>${__('Status')}</th><th>${__('Vitals')}</th><th></th></tr></thead>
				<tbody>${body}</tbody>
			</table>
		`);
		container.find('.btn-start-consult').on('click', function() {
			const name = $(this).data('name');
			frappe.call({
				method: 'healthcare.healthcare.page.doctor_station.doctor_station.start_consultation',
				args: { appointment: name },
				freeze: true,
				callback: function(r) {
					if (r.message && r.message.status === 'Success') {
						openEncounterDialog(r.message.encounter);
					}
				}
			});
		});
	}

	// =============================================
	// ENCOUNTER DIALOG (Start Consultation)
	// =============================================
	// start_consultation() above still creates/finds the Patient Encounter
	// exactly as before - the only thing that's changed is what happens
	// with the result. This has gone through three approaches now:
	//   1. A full browser navigation straight to the Encounter's own form
	//      (frappe.set_route()-based SPA navigation left the page
	//      half-rendered, so a real navigation was used instead).
	//   2. A small hand-built "quick capture" dialog (symptoms/diagnosis/
	//      a notes field only, posted to a custom save endpoint) - worked,
	//      but didn't give the doctor the rest of the form.
	//   3. A genuine frappe.ui.form.Form constructed directly inside the
	//      dialog's own body (`in_form: true`, the same flag core's own
	//      QuickEntryForm passes) - rendered nothing at all in practice
	//      (confirmed by testing: an empty dialog body, no Save button).
	//      Most likely cause: frm.refresh(name) expects the document
	//      already sitting in frappe.model.locals - on a routed Form page
	//      that's guaranteed by the router before refresh() ever runs,
	//      but nothing here was doing that equivalent fetch first. Rather
	//      than patch that one gap and stay exposed to whatever else a
	//      hand-built embedded frm needs that a normal page load provides
	//      for free (this app has already shipped one broken guess about
	//      Frappe internals this session - the "Labs" dashboard card's
	//      add_transactions() call - so a second unverified guess here
	//      isn't a good trade), this now uses approach 4 below instead.
	//   4. An <iframe> pointed at the exact same URL "Open Full Page"
	//      already uses. This is the one guaranteed-correct option
	//      available without live access to a running site to test
	//      against: same-origin, same route, same code path Desk always
	//      uses to render a Form page - real tabs (Details / Trial
	//      Medical Exam / Encounter Details / Notes), real dashboard
	//      cards (Orders / Inpatient / Notes, Tasks & Vitals / Medical
	//      Records), real Save/Submit, nothing reimplemented or
	//      guessed at here. The only real downside is weight (a second
	//      full Desk boot inside the iframe) and no in-dialog "Save"
	//      button of our own - the iframe's own toolbar already has one.
	function openEncounterDialog(encounterName) {
		const dialog = new frappe.ui.Dialog({
			title: __('Patient Encounter'),
			size: 'extra-large',
			secondary_action_label: __('Open in New Tab'),
			secondary_action: function() {
				window.open(frappe.utils.get_form_link('Patient Encounter', encounterName), '_blank');
			}
		});

		// This dialog's own footer bar (holding the "Open in New Tab"
		// button above) added nothing worth the vertical space once the
		// iframe below is doing all the real work - the secondary_action
		// wiring stays (still reachable via dialog.secondary_action if
		// ever needed), just the visible bar is trimmed.
		dialog.$wrapper.find('.modal-footer').hide();

		dialog.$wrapper.find('.modal-dialog').css('max-width', '95vw');
		const $body = dialog.$wrapper.find('.modal-body');
		$body.css({ padding: 0, height: '85vh', overflow: 'hidden' });
		$body.html(
			`<iframe src="${frappe.utils.get_form_link('Patient Encounter', encounterName)}" ` +
			`style="width: 100%; height: 100%; border: 0;" title="${frappe.utils.escape_html(__('Patient Encounter'))}"></iframe>`
		);

		// The iframe loads a full, independent Desk boot - same-origin, so
		// its own document is reachable once loaded - and that includes
		// Desk's persistent left workspace sidebar, confirmed (via
		// inspecting the actual rendered markup) to be
		// `.body-sidebar-container` - "expanded" is just the state class
		// Desk toggles on it when open, not a separate element. Hidden
		// here with injected CSS rather than by reimplementing the app
		// shell; the older guessed selectors are kept alongside it as
		// harmless fallbacks (CSS, unlike JS, never throws for an
		// unmatched selector) in case a different Desk view uses a
		// different wrapper.
		$body.find('iframe').on('load', function() {
			try {
				const idoc = this.contentDocument;
				if (!idoc) return;
				const style = idoc.createElement('style');
				style.textContent = `
					.body-sidebar-container,
					#sidebar, .desk-sidebar, .body-sidebar, #body-sidebar,
					.sidebar-section, .layout-side-section.desk-sidebar,
					.navbar, #navbar {
						display: none !important;
					}
					.content, .main-section, .page-container,
					.container-fluid, .col.layout-main-section-wrapper {
						margin-left: 0 !important;
						padding-left: 0 !important;
					}
				`;
				idoc.head.appendChild(style);
			} catch (e) {
				// Same-origin should make this reachable, but if a timing
				// or permission quirk ever throws here, the dialog still
				// works fine with the full Desk chrome just left visible.
				console.error('openEncounterDialog: could not trim iframe chrome', e);
			}
		});

		dialog.show();

		// Nothing here can know when the doctor is actually done inside
		// the iframe (same-origin, but its own Desk instance/router - not
		// worth reaching into) - refresh the queue whenever the dialog
		// closes instead, same as every other action on this page that
		// might have changed queue_status.
		dialog.onhide = function() {
			loadAll();
		};
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
