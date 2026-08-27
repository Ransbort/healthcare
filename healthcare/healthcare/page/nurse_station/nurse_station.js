frappe.pages['nurse-station'].on_page_load = function(wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Nurse Station',
		single_column: true
	});

	// =============================================
	// REALTIME SOUND NOTIFICATIONS
	// =============================================
	// Same pattern as Front Desk / Cashier Portal / Laboratory Portal - a
	// nurse working something else (charting, another patient) still
	// hears/sees a new arrival instead of having to keep this tab in view.
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
		if (data.department !== 'nurse') return;
		playNotification();
		frappe.show_alert({
			message: data.message,
			indicator: 'blue'
		}, 6);
		loadAll();
	});

	// =============================================
	// STYLES - same visual language as Laboratory Portal (toolbar with
	// icon badge, card-style search sections, tabs with badge counts) so
	// the two portals read as one system.
	// =============================================
	const style = `
		<style>
			.ns-wrapper { padding: 20px; max-width: 1400px; margin: 0 auto; }

			.sticky-header {
				position: sticky;
				top: 0;
				z-index: 100;
				background: var(--fg-color, white);
				padding-bottom: 16px;
				margin-bottom: 20px;
			}

			/* --- Toolbar: title + actions --- */
			.ns-toolbar {
				display: flex;
				justify-content: space-between;
				align-items: center;
				padding-bottom: 16px;
				margin-bottom: 16px;
				border-bottom: 1px solid #e9ecef;
			}

			.ns-toolbar-title {
				display: flex;
				align-items: center;
				gap: 12px;
			}

			.ns-toolbar-title .icon-badge {
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

			.ns-toolbar-title h4 {
				margin: 0;
				font-size: 1.2rem;
				font-weight: 700;
				color: #1a1a2e;
				line-height: 1.3;
			}

			.ns-toolbar-title .ns-toolbar-subtitle {
				font-size: 0.83rem;
				color: #868e96;
				margin-top: 1px;
			}

			.ns-toolbar-actions {
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
			.ns-wrapper .last-updated {
				display: flex;
				align-items: center;
				gap: 6px;
				font-size: 0.78rem;
				color: #adb5bd !important;
				padding: 4px 2px 0;
			}

			/* --- Search / filter card, shared by every tab --- */
			.ns-wrapper .search-section {
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
			.ns-wrapper .search-input-group label { color: #495057 !important; font-weight: 500; font-size: 0.83rem; }
			.search-input-group .form-control { border-radius: 8px; border: 1px solid #dee2e6; }

			#nurse-refresh-date-btn, #admitted-search-btn {
				border-radius: 8px;
				font-weight: 600;
				padding: 8px 18px;
			}

			#admitted-clear-btn {
				border-radius: 8px;
				font-weight: 600;
				padding: 8px 16px;
				background: transparent;
				border: 1px solid #dee2e6;
				color: #495057;
			}

			#admitted-clear-btn:hover { background: #f8f9fa; }

			.btn-clear-queue {
				border-radius: 8px;
				font-weight: 600;
				padding: 8px 16px;
				background: transparent;
				border: 1px solid #f1aeb5;
				color: #b02a37;
				display: flex;
				align-items: center;
				gap: 6px;
				font-size: 0.85rem;
				white-space: nowrap;
				transition: all 0.15s ease;
			}

			.btn-clear-queue:hover { background: #f8d7da; }

			/* --- Tabs --- */
			.tabs-section {
				display: flex;
				gap: 10px;
				margin-bottom: 16px;
				border-bottom: 2px solid #e0e0e0;
				align-items: center;
				overflow-x: auto;
				/* Setting overflow-x alone leaves overflow-y at its default
				   (visible), which the CSS overflow spec then silently
				   promotes to auto too - so a tab row that's even a pixel
				   taller than its own line height (badges/icons rounding
				   differently than the plain text baseline) picks up a
				   stray vertical scrollbar nobody asked for. Pinning
				   overflow-y explicitly keeps only the horizontal
				   scrolling this was meant to allow, for a tab row that
				   doesn't fit a narrow screen. */
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

			/* No fixed height/overflow here on purpose - Nurse Station's
			   lists are short enough to just flow with the page rather
			   than scroll in their own clipped box (unlike Laboratory
			   Portal's card grids, this was producing a stray inner
			   scrollbar even for a single row). */
			.scrollable-content {
				padding-right: 4px;
			}

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
			.badge-pending { background: #fff3cd; color: #856404; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-paid { background: #d1ecf1; color: #0c5460; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-nurse { background: #e0cffc; color: #4b2582; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-doctor { background: #cfe2ff; color: #084298; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-consult { background: #ffe5d0; color: #7a3e00; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-completed { background: #d4edda; color: #155724; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-admitted { background: #d1f2e0; color: #0f5e3c; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }

			.empty-state { text-align: center; padding: 60px 20px; color: #6c757d; }
			.empty-state i { font-size: 64px; margin-bottom: 20px; opacity: 0.3; }
			.empty-state h4 { font-size: 1.3rem; margin-bottom: 10px; color: #495057; }
			.empty-state p { font-size: 1rem; margin: 0; }

			@media (max-width: 768px) {
				.ns-wrapper { padding: 15px; }
				.ns-toolbar { flex-direction: column; align-items: flex-start; gap: 12px; }
				.ns-toolbar-actions { width: 100%; justify-content: flex-end; }
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
		<div class="ns-wrapper">
			<div class="sticky-header">
				<div class="ns-toolbar">
					<div class="ns-toolbar-title">
						<div class="icon-badge"><i class="fa fa-stethoscope"></i></div>
						<div>
							<h4>${__('Nurse Station')}</h4>
							<div class="ns-toolbar-subtitle">${__('Vitals, admission orders & inpatient lookup')}</div>
						</div>
					</div>
					<div class="ns-toolbar-actions">
						<button class="btn-icon" id="ns-refresh-btn" title="${__('Refresh')}">
							<i class="fa fa-refresh"></i>
						</button>
					</div>
				</div>

				<div class="last-updated">
					<i class="fa fa-clock-o"></i>
					<span id="last-updated-time">${__('Not loaded yet')}</span>
				</div>

				<div class="tabs-section">
					<button class="tab-btn active" data-tab="vitals">
						<i class="fa fa-heartbeat"></i> ${__('Vitals Queue')}
						<span class="badge badge-info" id="vitals-count">0</span>
					</button>
					<button class="tab-btn" data-tab="admissions">
						<i class="fa fa-bed"></i> ${__('Admission Orders')}
						<span class="badge badge-warning" id="admissions-count">0</span>
					</button>
					<button class="tab-btn" data-tab="admitted">
						<i class="fa fa-hospital-o"></i> ${__('Admitted Patients')}
						<span class="badge" id="admitted-count">0</span>
					</button>
				</div>
			</div>

			<!-- VITALS QUEUE TAB -->
			<div class="tab-content active" id="vitals-tab">
				<div class="search-section">
					<div class="search-input-group">
						<div data-fieldname="n_date"></div>
						<button class="btn btn-primary" id="nurse-refresh-date-btn">
							<i class="fa fa-filter"></i> ${__('Filter')}
						</button>
						<button class="btn btn-clear-queue" id="nurse-clear-all-btn">
							<i class="fa fa-trash"></i> ${__('Clear All')}
						</button>
					</div>
				</div>
				<div class="scrollable-content">
					<div class="queue-table-container" id="nurse-table-container"></div>
				</div>
			</div>

			<!-- ADMISSION ORDERS TAB -->
			<div class="tab-content" id="admissions-tab">
				<div class="scrollable-content">
					<div class="queue-table-container" id="admission-orders-container"></div>
				</div>
			</div>

			<!-- ADMITTED PATIENTS TAB -->
			<div class="tab-content" id="admitted-tab">
				<div class="search-section">
					<div class="search-input-group">
						<div data-fieldname="admitted_patient"></div>
						<button class="btn btn-primary" id="admitted-search-btn">
							<i class="fa fa-search"></i> ${__('Search')}
						</button>
						<button class="btn" id="admitted-clear-btn">${__('Clear')}</button>
					</div>
				</div>
				<div class="scrollable-content">
					<div class="queue-table-container" id="admitted-table-container"></div>
				</div>
			</div>
		</div>
	`;
	$(html).appendTo(page.main);

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

	function statusBadge(status) {
		const map = {
			'Registered': 'badge-registered',
			'Payment Pending': 'badge-pending',
			'Paid - Awaiting Vitals': 'badge-paid',
			'With Nurse': 'badge-nurse',
			'With Doctor': 'badge-doctor',
			'In Consultation': 'badge-consult',
			'Completed': 'badge-completed',
			'Admitted': 'badge-admitted'
		};
		return `<span class="${map[status] || 'badge-registered'}">${status || ''}</span>`;
	}

	// Tracks how many of the loads kicked off by loadAll() are still in
	// flight, so "Last updated" only refreshes once everything currently
	// on screen is current - same pattern Laboratory Portal uses.
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
		pendingLoads = 3;
		loadNurseQueue();
		loadPendingAdmissionOrders();
		loadAdmittedPatients();
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

	page.main.find('#ns-refresh-btn').on('click', function() {
		const $icon = $(this).find('i');
		$icon.addClass('fa-spin');
		loadAll();
		setTimeout(() => $icon.removeClass('fa-spin'), 600);
	});

	// =============================================
	// VITALS QUEUE
	// =============================================
	let n_date = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="n_date"]'),
		df: { fieldtype: 'Date', fieldname: 'n_date', label: 'Date', default: frappe.datetime.get_today() },
		render_input: true
	});
	n_date.refresh();
	n_date.set_value(frappe.datetime.get_today());

	page.main.find('#nurse-refresh-date-btn').on('click', function() { loadNurseQueue(); });

	page.main.find('#nurse-clear-all-btn').on('click', function() {
		frappe.confirm(
			__('Clear every patient still waiting on vitals from the nurse queue? Anyone already sent to the doctor is left alone - vitals already recorded are never deleted, this only resets queue position.'),
			function() {
				frappe.call({
					method: 'healthcare.healthcare.page.nurse_station.nurse_station.clear_nurse_queue',
					args: { date: n_date.get_value() },
					freeze: true,
					freeze_message: __('Clearing nurse queue...'),
					callback: function(r) {
						const cleared = (r.message && r.message.cleared) || [];
						frappe.show_alert({
							message: cleared.length ? __('Cleared {0} patient(s) from the nurse queue', [cleared.length]) : __('Nothing to clear'),
							indicator: cleared.length ? 'green' : 'blue'
						}, 4);
						loadNurseQueue();
					}
				});
			}
		);
	});

	function loadNurseQueue() {
		frappe.call({
			// Deliberately not a plain "With Nurse" filter - that would drop
			// a patient off this list the instant vitals are saved, or the
			// moment a doctor advances past "With Doctor". get_nurse_queue
			// keeps every appointment this station has touched today
			// visible (and editable) until the nurse explicitly clears it -
			// see its docstring in nurse_station.py.
			method: 'healthcare.healthcare.page.nurse_station.nurse_station.get_nurse_queue',
			args: { date: n_date.get_value() },
			callback: function(r) {
				renderNurseTable(r.message || []);
				markLoadDone();
			}
		});
	}

	function renderNurseTable(rows) {
		page.main.find('#vitals-count').text(rows.length);
		const container = page.main.find('#nurse-table-container');
		if (!rows.length) {
			container.html(`<div class="empty-state"><i class="fa fa-heartbeat"></i><h4>${__('Nurse queue is empty')}</h4><p>${__('Patients checked in and awaiting vitals will show up here.')}</p></div>`);
			return;
		}
		let body = '';
		rows.forEach(function(row) {
			// Anything other than "With Nurse" means vitals have already
			// been recorded for this appointment - it may have moved well
			// past "With Doctor" by now (In Consultation, Completed) since
			// this list no longer drops a row just because the doctor's
			// side of the pipeline advanced - see get_nurse_queue()'s
			// docstring. statusBadge() reflects whatever the real current
			// status is rather than collapsing everything to a generic
			// "Sent" label.
			const waiting = row.queue_status === 'With Nurse';
			const actionBtn = waiting
				? `<button class="btn btn-xs btn-primary btn-open-vitals" data-name="${row.name}" data-mode="record">${__('Record Vitals')}</button>`
				: `<button class="btn btn-xs btn-default btn-open-vitals" data-name="${row.name}" data-mode="edit">${__('Edit Vitals')}</button>`;
			body += `
				<tr class="nurse-row" data-name="${row.name}">
					<td>${formatQueueTime(row.encounter_time)}</td>
					<td>${row.patient_name || ''}</td>
					<td>${row.practitioner_name || row.practitioner || ''}</td>
					<td>${row.appointment_type || ''}</td>
					<td>${statusBadge(row.queue_status)}</td>
					<td>
						${actionBtn}
					</td>
				</tr>
			`;
		});
		container.html(`
			<table class="queue-table">
				<thead>
					<tr>
						<th>${__('Time')}</th>
						<th>${__('Patient')}</th>
						<th>${__('Practitioner')}</th>
						<th>${__('Appointment Type')}</th>
						<th>${__('Status')}</th>
						<th></th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		`);

		container.find('.btn-open-vitals').on('click', function() {
			const name = $(this).data('name');
			const mode = $(this).data('mode');
			const row = rows.find(r => r.name === name);
			openVitalsDialog(row, mode);
		});

		function openVitalsDialog(row, mode) {
			const isEdit = mode === 'edit';
			const dialog = new frappe.ui.Dialog({
				title: isEdit ? __('Edit Vitals') : __('Record Vitals'),
				size: 'large',
				fields: [
					{ fieldtype: 'Section Break', label: __('Vitals') },
					{ fieldtype: 'Float', fieldname: 'temp', label: __('Temperature (°C)'), default: isEdit ? row.vitals_temperature : undefined },
					{ fieldtype: 'Column Break' },
					{ fieldtype: 'Data', fieldname: 'bp', label: __('Blood Pressure'), placeholder: '120/80', default: isEdit ? row.vitals_blood_pressure : undefined },
					{ fieldtype: 'Column Break' },
					{ fieldtype: 'Int', fieldname: 'pulse', label: __('Pulse (bpm)'), default: isEdit ? row.vitals_pulse : undefined },

					{ fieldtype: 'Section Break' },
					{ fieldtype: 'Float', fieldname: 'weight', label: __('Weight (kg)'), default: isEdit ? row.vitals_weight : undefined },
					{ fieldtype: 'Column Break' },
					{ fieldtype: 'Float', fieldname: 'height', label: __('Height (cm)'), default: isEdit ? row.vitals_height : undefined },
					{ fieldtype: 'Column Break' },
					// Read-only: this is a live client-side preview only, purely
					// so the nurse can see it while entering weight/height. The
					// value actually saved is always recomputed server-side in
					// save_vitals()/update_vitals() -> _calculate_bmi(), never
					// trusted from here.
					{ fieldtype: 'Float', fieldname: 'bmi', label: __('BMI'), precision: 2, read_only: 1, description: __('Auto-calculated from weight & height'), default: isEdit ? row.vitals_bmi : undefined },

					{ fieldtype: 'Section Break' },
					{ fieldtype: 'Data', fieldname: 'resp', label: __('Respiratory Rate'), default: isEdit ? row.vitals_respiratory_rate : undefined },
					{ fieldtype: 'Column Break' },
					{ fieldtype: 'Select', fieldname: 'tongue', label: __('Tongue'), options: '\nCoated\nVery Coated\nNormal\nFurry\nCuts', default: isEdit ? row.vitals_tongue : undefined },
					{ fieldtype: 'Column Break' },
					{ fieldtype: 'Select', fieldname: 'abdomen', label: __('Abdomen'), options: '\nNormal\nBloated\nFull\nFluid\nConstipated', default: isEdit ? row.vitals_abdomen : undefined },

					{ fieldtype: 'Section Break' },
					{ fieldtype: 'Int', fieldname: 'spo2', label: __('SpO2 (%)'), default: isEdit ? row.vitals_spo2 : undefined },
					{ fieldtype: 'Column Break' },
					{ fieldtype: 'Float', fieldname: 'fbs', label: __('FBS (mg/dL)'), description: __('Fasting Blood Sugar'), default: isEdit ? row.vitals_fbs : undefined },
					{ fieldtype: 'Column Break' },
					{ fieldtype: 'Float', fieldname: 'rbs', label: __('RBS (mg/dL)'), description: __('Random Blood Sugar'), default: isEdit ? row.vitals_rbs : undefined },

					{ fieldtype: 'Section Break' },
					{ fieldtype: 'Select', fieldname: 'reflexes', label: __('Reflexes'), options: '\nNormal\nHyper\nVery Hyper\nOne Sided', default: isEdit ? row.vitals_reflexes : undefined },
					{ fieldtype: 'Column Break' },
					// Display-only - the actual value saved is always the
					// nurse who *originally* recorded it (save_vitals() stamps
					// it server-side once, and update_vitals() deliberately
					// never overwrites it - see its docstring). Never trust/
					// send this from the client either way.
					{ fieldtype: 'Data', fieldname: 'recorded_by_display', label: __('Vitals Recorded By'), read_only: 1, default: frappe.session.user_fullname || frappe.session.user },

					{ fieldtype: 'Section Break' },
					{ fieldtype: 'Small Text', fieldname: 'notes', label: __('Notes'), default: isEdit ? row.vitals_notes : undefined },
				],
				primary_action_label: isEdit ? __('Update Vitals') : __('Save Vitals & Send to Doctor'),
				primary_action: function(values) {
					frappe.call({
						method: isEdit
							? 'healthcare.healthcare.page.nurse_station.nurse_station.update_vitals'
							: 'healthcare.healthcare.page.nurse_station.nurse_station.save_vitals',
						args: {
							appointment: row.name,
							temperature: values.temp,
							blood_pressure: values.bp,
							pulse: values.pulse,
							weight: values.weight,
							height: values.height,
							respiratory_rate: values.resp,
							tongue: values.tongue,
							abdomen: values.abdomen,
							reflexes: values.reflexes,
							spo2: values.spo2,
							fbs: values.fbs,
							rbs: values.rbs,
							notes: values.notes
						},
						freeze: true,
						freeze_message: isEdit ? __('Updating vitals...') : __('Saving vitals...'),
						callback: function(r) {
							if (r.message && r.message.status === 'Success') {
								dialog.hide();
								frappe.show_alert({ message: isEdit ? __('Vitals updated') : __('Vitals saved, sent to doctor'), indicator: 'green' }, 5);
								loadNurseQueue();
							}
						}
					});
				}
			});

			function recalcBmiPreview() {
				const w = parseFloat(dialog.get_value('weight'));
				const h = parseFloat(dialog.get_value('height'));
				if (w > 0 && h > 0) {
					const heightM = h / 100;
					dialog.set_value('bmi', Math.round((w / (heightM * heightM)) * 100) / 100);
				} else {
					dialog.set_value('bmi', '');
				}
			}
			const weightField = dialog.fields_dict.weight;
			const heightField = dialog.fields_dict.height;
			if (weightField && weightField.$input) weightField.$input.on('change input', recalcBmiPreview);
			if (heightField && heightField.$input) heightField.$input.on('change input', recalcBmiPreview);

			dialog.show();
		}
	}

	// =============================================
	// ADMISSION ORDERS
	// =============================================
	// Accept/Reject call admission_order.py's own whitelisted methods
	// directly - same ones the Admission Order form's own Accept/Reject
	// buttons use - rather than duplicating that logic here. Those already
	// enforce their own Nursing User role check server-side, independent
	// of this page's own access gate.
	function loadPendingAdmissionOrders() {
		frappe.call({
			method: 'healthcare.healthcare.page.nurse_station.nurse_station.get_pending_admission_orders',
			callback: function(r) {
				renderAdmissionOrders(r.message || []);
				markLoadDone();
			}
		});
	}

	function renderAdmissionOrders(orders) {
		page.main.find('#admissions-count').text(orders.length);
		const container = page.main.find('#admission-orders-container');

		if (!orders.length) {
			container.html(`<div class="empty-state"><i class="fa fa-bed"></i><h4>${__('No pending admission orders')}</h4><p>${__('Orders placed from a Patient Encounter will show up here for Accept/Reject.')}</p></div>`);
			return;
		}

		let body = '';
		orders.forEach(function(order) {
			body += `
				<tr class="admission-order-row" data-name="${order.name}">
					<td>${order.patient_name || ''}</td>
					<td>${order.medical_department || ''}</td>
					<td>${order.primary_practitioner_name || order.primary_practitioner || ''}</td>
					<td>${order.admission_ordered_for || ''}</td>
					<td>${order.admission_service_unit_type || ''}</td>
					<td>${order.expected_length_of_stay || order.expected_length_of_stay === 0 ? order.expected_length_of_stay : ''}</td>
					<td>
						<button class="btn btn-xs btn-success btn-accept-admission" data-name="${order.name}">${__('Accept')}</button>
						<button class="btn btn-xs btn-default btn-reject-admission" data-name="${order.name}">${__('Reject')}</button>
					</td>
				</tr>
			`;
		});
		container.html(`
			<table class="queue-table">
				<thead>
					<tr>
						<th>${__('Patient')}</th>
						<th>${__('Department')}</th>
						<th>${__('Practitioner')}</th>
						<th>${__('Ordered For')}</th>
						<th>${__('Service Unit')}</th>
						<th title="${__('Expected Length of Stay')}">${__('ELoS')}</th>
						<th></th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		`);

		container.find('.btn-accept-admission').on('click', function() {
			const name = $(this).data('name');
			frappe.confirm(
				__('Accept this admission order and create the Inpatient Record?'),
				function() {
					frappe.call({
						method: 'healthcare.healthcare.doctype.admission_order.admission_order.accept_admission_order',
						args: { admission_order: name },
						freeze: true,
						freeze_message: __('Accepting admission order...'),
						callback: function(r) {
							if (!r.exc) {
								frappe.show_alert({ message: __('Admission accepted'), indicator: 'green' }, 5);
								loadPendingAdmissionOrders();
								loadAdmittedPatients();
							}
						}
					});
				}
			);
		});

		container.find('.btn-reject-admission').on('click', function() {
			const name = $(this).data('name');
			frappe.prompt(
				[
					{
						fieldname: 'reason',
						label: __('Reason for Rejection'),
						fieldtype: 'Small Text',
						reqd: 1
					}
				],
				function(data) {
					frappe.call({
						method: 'healthcare.healthcare.doctype.admission_order.admission_order.reject_admission_order',
						args: { admission_order: name, reason: data.reason },
						freeze: true,
						freeze_message: __('Rejecting admission order...'),
						callback: function(r) {
							if (!r.exc) {
								frappe.show_alert({ message: __('Admission order rejected'), indicator: 'orange' }, 5);
								loadPendingAdmissionOrders();
							}
						}
					});
				},
				__('Reject Admission Order'),
				__('Reject')
			);
		});
	}

	// =============================================
	// ADMITTED PATIENTS
	// =============================================
	// "Search for patients that have been admitted" - a Patient Link
	// field, same autocomplete-and-select UX Laboratory Portal's own
	// patient search already uses, scoped to Inpatient Record.status ==
	// "Admitted" (see get_admitted_patients()'s docstring). Blank search
	// lists everyone currently admitted.
	let admitted_patient_field = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="admitted_patient"]'),
		df: {
			fieldtype: 'Link',
			fieldname: 'admitted_patient',
			options: 'Patient',
			label: __('Patient (Optional)'),
			placeholder: __('Search admitted patients'),
			onchange: function() { loadAdmittedPatients(); }
		},
		render_input: true
	});
	admitted_patient_field.refresh();

	page.main.find('#admitted-search-btn').on('click', function() { loadAdmittedPatients(); });

	page.main.find('#admitted-clear-btn').on('click', function() {
		admitted_patient_field.set_value('');
		loadAdmittedPatients();
	});

	function loadAdmittedPatients() {
		frappe.call({
			method: 'healthcare.healthcare.page.nurse_station.nurse_station.get_admitted_patients',
			args: { patient: admitted_patient_field.get_value() || null },
			callback: function(r) {
				renderAdmittedPatients(r.message || []);
				markLoadDone();
			}
		});
	}

	function renderAdmittedPatients(records) {
		page.main.find('#admitted-count').text(records.length);
		const container = page.main.find('#admitted-table-container');

		if (!records.length) {
			const searched = !!admitted_patient_field.get_value();
			container.html(`<div class="empty-state"><i class="fa fa-hospital-o"></i><h4>${searched ? __('No admitted record found for this patient') : __('No patients currently admitted')}</h4><p>${__('Patients accepted from an admission order will show up here while status is Admitted.')}</p></div>`);
			return;
		}

		let body = '';
		records.forEach(function(record) {
			body += `
				<tr class="admitted-row" data-name="${record.name}">
					<td>${record.patient_name || ''}</td>
					<td>${record.medical_department || ''}</td>
					<td>${record.primary_practitioner_name || record.primary_practitioner || ''}</td>
					<td>${record.admission_service_unit_type || ''}</td>
					<td>${frappe.datetime.str_to_user(record.admitted_datetime) || ''}</td>
					<td>${record.expected_discharge || ''}</td>
					<td>
						<button class="btn btn-xs btn-default btn-view-inpatient" data-name="${record.name}">${__('View')}</button>
					</td>
				</tr>
			`;
		});
		container.html(`
			<table class="queue-table">
				<thead>
					<tr>
						<th>${__('Patient')}</th>
						<th>${__('Department')}</th>
						<th>${__('Practitioner')}</th>
						<th>${__('Service Unit')}</th>
						<th>${__('Admitted')}</th>
						<th>${__('Expected Discharge')}</th>
						<th></th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		`);

		container.find('.btn-view-inpatient').on('click', function() {
			// Same SPA-navigation issue Start Consultation had (see
			// doctor_station.js/front_desk.js's start_consultation() click
			// handler for the full writeup) - frappe.set_route() alone
			// left the page half-rendered (generic footer, no field
			// layout/dashboard) until a manual refresh. A real browser
			// navigation sidesteps the SPA route/render pipeline entirely.
			window.location.href = frappe.utils.get_form_link('Inpatient Record', $(this).data('name'));
		});
	}

	loadAll();
};
