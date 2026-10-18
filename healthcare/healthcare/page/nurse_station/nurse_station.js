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
			.ns-wrapper {
				height: calc(100vh - 60px);
				display: flex;
				flex-direction: column;
				overflow: hidden;
				box-sizing: border-box;
				padding: 20px;
				max-width: 1400px;
				margin: 0 auto;
				width: 100%;
			}

			.sticky-header {
				flex-shrink: 0;
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

			.ns-icon {
				display: inline-block;
				font-style: normal;
			}

			/* Stand-in for Font Awesome's fa-spin - that icon font isn't
			   loading in this environment (same reason every fa fa-* icon
			   on this page was swapped for a plain emoji/Unicode
			   character below). One full turn, not infinite - the refresh
			   click handler removes this class again after 600ms. */
			@keyframes ns-icon-spin {
				from { transform: rotate(0deg); }
				to { transform: rotate(360deg); }
			}

			.ns-icon.ns-spin {
				animation: ns-icon-spin 0.6s linear;
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
				flex-shrink: 0;
				/* .queue-table thead below is position:sticky with its own
				   z-index:10 (so it stays on top of scrolling rows) - without
				   a raised z-index of its own here, this card and the sticky
				   thead end up compared directly in the shared stacking
				   context, and the Patient Link field's awesomplete dropdown
				   (an absolutely-positioned child with no z-index, so treated
				   as 0) loses to it and renders half-hidden under the results
				   table. position:relative + a z-index above 10 gives this
				   whole card - dropdown included - its own stacking context
				   that paints above the table regardless of the table's own
				   internal z-index. */
				position: relative;
				z-index: 20;
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
				
			}

			#admitted-clear-btn {
				border-radius: 8px;
				font-weight: 600;
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

			.tab-content { display: none; flex: 1; min-height: 0; overflow: hidden; }
			.tab-content.active { display: flex; flex-direction: column; }

			/* .ns-wrapper is now a fixed-height flex column (see its own
			   comment) instead of flowing/scrolling with the page, so this
			   needs its own bounded scroll region again - unlike the old
			   max-height-based attempt this note used to describe, sizing
			   via flex (rather than a guessed max-height) doesn't leave a
			   stray scrollbar when a list is short enough to fit without
			   one. */
			/* This is also the element the sticky table header below sticks
			   within - it has to be the actual overflow:auto scroller
			   itself (not a plain wrapper around one, and not
			   .queue-table-container either), since a sticky element
			   sticks relative to its nearest ancestor with
			   overflow != visible; putting rounded-corner clipping on a
			   container between the two (as .queue-table-container used
			   to have) breaks it - see doctor_station.js's version of this
			   same fix for the full writeup. Corner-rounding lives here
			   instead. */
			.scrollable-content {
				flex: 1;
				min-height: 0;
				overflow-y: auto;
				overflow-x: hidden;
				border-radius: 8px;
				padding-right: 4px;
			}

			/* --- Tables --- */
			.queue-table { width: 100%; border-collapse: collapse; }
			.queue-table-container {
				background: white;
				box-shadow: 0 2px 8px rgba(0,0,0,0.08);
			}
			.queue-table thead {
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
				color: white;
				position: sticky;
				top: 0;
				z-index: 10;
			}
			.queue-table thead th:first-child { border-top-left-radius: 8px; }
			.queue-table thead th:last-child { border-top-right-radius: 8px; }
			.queue-table th { padding: 12px; text-align: left; font-weight: 600; font-size: 0.9rem; }
			.queue-table td { padding: 12px; font-size: 0.9rem; border-bottom: 1px solid #e9ecef; }
			.queue-table tbody tr:hover { background: #f8f9fa; }

			/* Every status badge below is a single-line pill - without this,
			   a long label (Admission Scheduled/Discharge Scheduled) wraps
			   onto a second line inside the Admitted Patients table's
			   narrow Status column and looks broken. */
			[class^="badge-"] { white-space: nowrap; }

			.badge-registered { background: #e2e3e5; color: #383d41; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-pending { background: #fff3cd; color: #856404; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-paid { background: #d1ecf1; color: #0c5460; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-nurse { background: #e0cffc; color: #4b2582; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-doctor { background: #cfe2ff; color: #084298; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-consult { background: #ffe5d0; color: #7a3e00; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-completed { background: #d4edda; color: #155724; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-admitted { background: #d1f2e0; color: #0f5e3c; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-discharge-scheduled { background: #ffe8cc; color: #8a4b00; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-admission-scheduled { background: #dbe4ff; color: #2c4b9e; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
			.badge-owes-balance { background: #f8d7da; color: #842029; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }

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
						<div class="icon-badge">🩺</div>
						<div>
							<h4>${__('Nurse Station')}</h4>
							<div class="ns-toolbar-subtitle">${__('Vitals, admission orders & inpatient lookup')}</div>
						</div>
					</div>
					<div class="ns-toolbar-actions">
						<button class="btn-icon" id="ns-refresh-btn" title="${__('Refresh')}">
							<i class="ns-icon">🔄</i>
						</button>
					</div>
				</div>

				<div class="last-updated">
					🕐
					<span id="last-updated-time">${__('Not loaded yet')}</span>
				</div>

				<div class="tabs-section">
					<button class="tab-btn active" data-tab="vitals">
						💓 ${__('Vitals Queue')}
						<span class="badge badge-info" id="vitals-count">0</span>
					</button>
					<button class="tab-btn" data-tab="admissions">
						🛏️ ${__('Admission Orders')}
						<span class="badge badge-warning" id="admissions-count">0</span>
					</button>
					<button class="tab-btn" data-tab="admitted">
						🏥 ${__('Admitted Patients')}
						<span class="badge" id="admitted-count">0</span>
					</button>
				</div>
			</div>

			<!-- VITALS QUEUE TAB -->
			<div class="tab-content active" id="vitals-tab">
				<div class="search-section">
					<div class="search-input-group">
						<div data-fieldname="n_date" style="flex: 0 0 200px;"></div>
						<div data-fieldname="n_to_date" style="flex: 0 0 200px;"></div>
						<div data-fieldname="n_queue_search" style="flex: 0 0 220px;"></div>
						<button class="btn btn-primary" id="nurse-refresh-date-btn" style="flex-shrink: 0;">
							🔽 ${__('Filter')}
						</button>
						<button class="btn btn-clear-queue" id="nurse-clear-all-btn" style="flex-shrink: 0;">
							🗑️ ${__('Clear All')}
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
							🔍 ${__('Search')}
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
			'Admitted': 'badge-admitted',
			'Discharge Scheduled': 'badge-discharge-scheduled',
			'Admission Scheduled': 'badge-admission-scheduled'
		};
		// Admission Scheduled/Discharge Scheduled are the two long enough
		// to wrap onto a second line inside the Admitted Patients table's
		// narrow Status column (see the badge CSS's own nowrap fix below,
		// which helps but still leaves a wide badge) - abbreviated here,
		// with the full status kept as a hover title so nothing's lost.
		const abbreviations = {
			'Admission Scheduled': 'AS',
			'Discharge Scheduled': 'DS'
		};
		const label = abbreviations[status] || status || '';
		return `<span class="${map[status] || 'badge-registered'}" title="${frappe.utils.escape_html(status || '')}">${label}</span>`;
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
		// .ns-spin (defined above), not Font Awesome's fa-spin - see the
		// note by .ns-icon's CSS for why.
		$icon.addClass('ns-spin');
		loadAll();
		setTimeout(() => $icon.removeClass('ns-spin'), 600);
	});

	// =============================================
	// VITALS QUEUE
	// =============================================
	let n_date = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="n_date"]'),
		df: { fieldtype: 'Date', fieldname: 'n_date', label: 'From Date', default: frappe.datetime.get_today() },
		render_input: true
	});
	n_date.refresh();
	n_date.set_value(frappe.datetime.get_today());

	// Optional - leaving this blank keeps the single-day filter behavior;
	// filling it in switches get_nurse_queue() to a date range. Clear All
	// deliberately keeps using n_date alone (see clear_nurse_queue() call
	// below) - clearing a whole range at once isn't offered here.
	let n_to_date = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="n_to_date"]'),
		df: { fieldtype: 'Date', fieldname: 'n_to_date', label: 'To Date (optional)', placeholder: __('Leave blank to filter a single day') },
		render_input: true
	});
	n_to_date.refresh();

	// Live filter over whatever's already loaded for the day/range - the
	// queue is already a small, already-fetched list, so this is a
	// client-side re-render rather than a round trip. Same pattern as
	// Doctor Station's Doctor Queue search.
	let n_queue_search = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="n_queue_search"]'),
		df: {
			fieldtype: 'Data',
			fieldname: 'n_queue_search',
			label: 'Search',
			placeholder: __('Search patient or practitioner')
		},
		render_input: true
	});
	n_queue_search.refresh();

	let currentNurseRows = [];
	let nurseQueueSearchTerm = '';

	function applyNurseQueueSearch(rows) {
		const term = nurseQueueSearchTerm.trim().toLowerCase();
		if (!term) return rows;
		return rows.filter(function(row) {
			return [row.patient_name, row.patient, row.practitioner_name, row.practitioner, row.appointment_type]
				.some(function(value) { return (value || '').toLowerCase().includes(term); });
		});
	}

	n_queue_search.$input.on('input', frappe.utils.debounce(function() {
		nurseQueueSearchTerm = n_queue_search.get_value();
		renderNurseTable(applyNurseQueueSearch(currentNurseRows));
	}, 200));

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
		const fromDate = n_date.get_value();
		const toDate = n_to_date.get_value();

		if (toDate && fromDate && toDate < fromDate) {
			frappe.show_alert({ message: __('"To Date" cannot be before "From Date"'), indicator: 'orange' }, 6);
			return;
		}

		frappe.call({
			// Deliberately not a plain "With Nurse" filter - that would drop
			// a patient off this list the instant vitals are saved, or the
			// moment a doctor advances past "With Doctor". get_nurse_queue
			// keeps every appointment this station has touched today
			// visible (and editable) until the nurse explicitly clears it -
			// see its docstring in nurse_station.py.
			method: 'healthcare.healthcare.page.nurse_station.nurse_station.get_nurse_queue',
			args: { date: fromDate, to_date: toDate || null },
			callback: function(r) {
				currentNurseRows = r.message || [];
				renderNurseTable(applyNurseQueueSearch(currentNurseRows));
				markLoadDone();
			}
		});
	}

	function renderNurseTable(rows) {
		// Total loaded queue size, not scoped down by whatever's currently
		// typed into the search box - that only affects the table below.
		page.main.find('#vitals-count').text(currentNurseRows.length);
		const container = page.main.find('#nurse-table-container');
		if (!rows.length) {
			const searched = !!nurseQueueSearchTerm.trim();
			container.html(`<div class="empty-state"><i class="fa fa-heartbeat"></i><h4>${searched ? __('No matching patients') : __('Nurse queue is empty')}</h4><p>${searched ? __('Try a different name.') : __('Patients checked in and awaiting vitals will show up here.')}</p></div>`);
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
			// Only once the doctor has actually started consultation (see
			// _attach_linked_encounter() in nurse_station.py) - nothing to
			// view read-only before that. Kept as a separate button rather
			// than folded into actionBtn above so a nurse can still open
			// the encounter for context even while the vitals action is
			// disabled/not relevant (e.g. queue_status already past With
			// Nurse and Edit Vitals is what's showing instead).
			const viewEncounterBtn = row.encounter
				? `<button class="btn btn-xs btn-default btn-view-encounter" data-encounter="${row.encounter}">${__('View Encounter')}</button>`
				: '';
			body += `
				<tr class="nurse-row" data-name="${row.name}">
					<td>${formatQueueTime(row.encounter_time)}</td>
					<td>${row.patient_name || ''}</td>
					<td>${row.practitioner_name || row.practitioner || ''}</td>
					<td>${row.appointment_type || ''}</td>
					<td>${statusBadge(row.queue_status)}</td>
					<td>
						${actionBtn}
						${viewEncounterBtn}
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

		container.find('.btn-view-encounter').on('click', function(e) {
			e.stopPropagation();
			openEncounterDialog($(this).data('encounter'));
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
	// ENCOUNTER VIEW (read-only)
	// =============================================
	// Same iframe-embed technique as Doctor Station's own openEncounterDialog
	// (doctor_station.js) - an <iframe> pointed at the exact same URL "Open
	// Full Page" uses, same-origin, same route and code path Desk always
	// renders a Form through, nothing reimplemented or guessed at. The
	// difference here is deliberate: this is read-only, not "start
	// consultation", and that's enforced where it actually matters - the
	// server side, via Patient Encounter's own permission list (Nursing
	// User now has read/print/export/share but no write/create/submit/
	// delete - see patient_encounter.json) - rather than by hiding buttons
	// in this dialog, which a nurse could just route around by opening the
	// same link in a new tab anyway. Frappe's own Form renders read-only by
	// itself for a user with no write permission, so nothing extra is done
	// here to force that - same reasoning doctor_station.js's own comment
	// trail already went through for the sidebar-hiding CSS below: prefer
	// the guaranteed-correct primitive (real permissions) over reimplementing
	// something Frappe already does natively.
	function openEncounterDialog(encounterName) {
		const dialog = new frappe.ui.Dialog({
			title: __('Patient Encounter (Read Only)'),
			size: 'extra-large',
			secondary_action_label: __('Open in New Tab'),
			secondary_action: function() {
				window.open(frappe.utils.get_form_link('Patient Encounter', encounterName), '_blank');
			}
		});

		dialog.$wrapper.find('.modal-footer').hide();
		dialog.$wrapper.find('.modal-dialog').css('max-width', '95vw');
		const $body = dialog.$wrapper.find('.modal-body');
		$body.css({ padding: 0, height: '85vh', overflow: 'hidden' });
		$body.html(
			`<iframe src="${frappe.utils.get_form_link('Patient Encounter', encounterName)}" ` +
			`style="width: 100%; height: 100%; border: 0;" title="${frappe.utils.escape_html(__('Patient Encounter'))}"></iframe>`
		);

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
				console.error('openEncounterDialog: could not trim iframe chrome', e);
			}
		});

		dialog.show();
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
	// patient search already uses, scoped to Inpatient Record.status in
	// ("Admitted", "Discharge Scheduled") (see get_admitted_patients()'s
	// docstring). Blank search lists everyone currently admitted or
	// mid-discharge. Schedule Discharge/Discharge call the same core
	// inpatient_record.py functions the full Inpatient Record form's own
	// buttons use (schedule_discharge() module function, discharge()/
	// add_service_unit_rent_to_billable_items() doc methods via
	// run_doc_method) rather than duplicating that logic here - same
	// reasoning as Admission Orders' Accept/Reject above, and it means the
	// "Incomplete Services" block (see inpatient_record.py's
	// validate_incomplete_service_requests()) shows up automatically on
	// Discharge with no extra handling needed.
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
			container.html(`<div class="empty-state"><i class="fa fa-hospital-o"></i><h4>${searched ? __('No admitted record found for this patient') : __('No patients currently admitted')}</h4><p>${__('Patients accepted from an admission order show up here as soon as they\'re Admission Scheduled - assign them a bed here to admit them, then carry them through to discharge.')}</p></div>`);
			return;
		}

		let body = '';
		records.forEach(function(record) {
			const owes = flt(record.outstanding_amount) > 0;
			// Every action here is an icon-only button with a hover title
			// instead of a labeled pill - five buttons' worth of text
			// (View/Create Invoice/Schedule Discharge/Discharge/Payment
			// Pending) made this column badly cramped once Create Invoice
			// and the Balance column were added; the full label is still
			// there for anyone who hovers, just not taking up row width.
			let actions = `<button class="btn btn-xs btn-default btn-view-inpatient" data-name="${record.name}" title="${__('View')}">${frappe.utils.icon('eye', 'xs')}</button>`;
			// Shared by both the Admitted and Discharge Scheduled branches
			// below - disabled once has_invoice is set (an invoice already
			// exists for this admission, paid or not - see
			// get_admitted_patients()'s own comment on that flag) so a
			// nurse can't fire this twice and double-bill the same charges.
			const create_invoice_button = record.has_invoice
				? `<button class="btn btn-xs btn-default" disabled title="${__('Already invoiced for this admission')}">${frappe.utils.icon('file-text', 'xs')}</button>`
				: `<button class="btn btn-xs btn-info btn-create-invoice" data-name="${record.name}" data-patient-label="${frappe.utils.escape_html(record.patient_name || record.patient || '')}" title="${__('Create Invoice')}">${frappe.utils.icon('file-text', 'xs')}</button>`;
			if (record.status === 'Admission Scheduled') {
				actions += ` <button class="btn btn-xs btn-primary btn-admit-patient" data-name="${record.name}" title="${__('Admit')}">${frappe.utils.icon('user-check', 'xs')}</button>`;
			} else if (record.status === 'Admitted') {
				actions += ` ${create_invoice_button}`;
				actions += ` <button class="btn btn-xs btn-warning btn-schedule-discharge" data-name="${record.name}" data-patient="${record.patient}" title="${__('Schedule Discharge')}">${frappe.utils.icon('calendar', 'xs')}</button>`;
			} else if (record.status === 'Discharge Scheduled') {
				actions += ` ${create_invoice_button}`;
				if (owes) {
					// Same balance inpatient_record.py's validate_invoice_payment()
					// enforces server-side on Discharge - shown here up front
					// (disabled button, no click handler bound below) so a nurse
					// sees "still owes money" instead of clicking Discharge and
					// getting that block back as an error.
					actions += ` <button class="btn btn-xs btn-default" disabled title="${__('Settle the outstanding balance before this patient can be discharged')}">${frappe.utils.icon('clock', 'xs')}</button>`;
				} else {
					actions += ` <button class="btn btn-xs btn-danger btn-discharge-patient" data-name="${record.name}" title="${__('Discharge')}">${frappe.utils.icon('log-out', 'xs')}</button>`;
				}
			}
			const balance_cell = owes
				? `<span class="badge-owes-balance" style="cursor:pointer" title="${__('View Invoice')}" data-invoice="${record.outstanding_invoice}">${__('Owes')} ${format_currency(record.outstanding_amount, record.outstanding_currency)}</span>`
				: '';
			body += `
				<tr class="admitted-row" data-name="${record.name}">
					<td>${record.patient_name || ''}</td>
					<td>${statusBadge(record.status)}</td>
					<td>${record.medical_department || ''}</td>
					<td>${record.primary_practitioner_name || record.primary_practitioner || ''}</td>
					<td>${record.admission_service_unit_type || ''}</td>
					<td>${frappe.datetime.str_to_user(record.admitted_datetime) || ''}</td>
					<td>${record.expected_discharge || ''}</td>
					<td class="balance-cell">${balance_cell}</td>
					<td>${actions}</td>
				</tr>
			`;
		});
		container.html(`
			<table class="queue-table">
				<thead>
					<tr>
						<th>${__('Patient')}</th>
						<th>${__('Status')}</th>
						<th>${__('Department')}</th>
						<th>${__('Practitioner')}</th>
						<th>${__('Service Unit')}</th>
						<th>${__('Admitted')}</th>
						<th>${__('Expected Discharge')}</th>
						<th>${__('Balance')}</th>
						<th></th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		`);

		container.find('.balance-cell [data-invoice]').on('click', function() {
			window.open(frappe.utils.get_form_link('Sales Invoice', $(this).data('invoice')), '_blank');
		});

		container.find('.btn-view-inpatient').on('click', function() {
			openInpatientRecordDialog($(this).data('name'));
		});

		container.find('.btn-admit-patient').on('click', function() {
			const record = records.find((r) => r.name === $(this).data('name'));
			if (record) openAdmitPatientDialog(record);
		});

		// Mirrors inpatient_record.js's own create_inpatient_invoice(frm) -
		// same create_sales_invoice doc method, same confirm-then-freeze
		// flow - just reached via run_doc_method against the plain record
		// dict this page already has, instead of a loaded frm.doc. Lets a
		// nurse bill an admission's outstanding charges (ward stay, the
		// encounter, any labs/procedures) without leaving Nurse Station.
		container.find('.btn-create-invoice').on('click', function() {
			const inpatient_record = $(this).data('name');
			const patient_label = $(this).data('patient-label') || inpatient_record;
			frappe.confirm(
				__('Create a Sales Invoice for every outstanding healthcare charge for {0}?', [patient_label]),
				function() {
					frappe.call({
						method: 'run_doc_method',
						args: { dt: 'Inpatient Record', dn: inpatient_record, method: 'create_sales_invoice' },
						freeze: true,
						freeze_message: __('Gathering unbilled healthcare services...'),
						callback: function(r) {
							if (!r.exc && r.message) {
								frappe.show_alert({
									message: __('Sales Invoice {0} created for {1} ({2})', [
										r.message.invoice,
										patient_label,
										format_currency(r.message.grand_total, r.message.currency)
									]),
									indicator: 'green'
								}, 7);
								loadAdmittedPatients();
							}
						}
					});
				}
			);
		});

		container.find('.btn-schedule-discharge').on('click', function() {
			openScheduleDischargeDialog($(this).data('name'), $(this).data('patient'));
		});

		container.find('.btn-discharge-patient').on('click', function() {
			const inpatient_record = $(this).data('name');
			frappe.confirm(
				__('Discharge this patient? This is the final step - it will fail with a list of what\'s still open if any orders on this admission haven\'t been carried out yet.'),
				function() {
					frappe.call({
						method: 'run_doc_method',
						args: { dt: 'Inpatient Record', dn: inpatient_record, method: 'discharge' },
						freeze: true,
						freeze_message: __('Processing Inpatient Discharge'),
						callback: function(r) {
							if (!r.exc) {
								frappe.show_alert({ message: __('Patient discharged'), indicator: 'green' }, 5);
								loadAdmittedPatients();
							}
						}
					});
				}
			);
		});
	}

	// Same approach as Doctor Station's openEncounterDialog() - see that
	// function's own comment for the full history of what was tried
	// first and why: an <iframe> pointed at the record's own form URL
	// (the same one "Open in New Tab" uses), because it's the only
	// guaranteed-correct way to get the real form - real tabs (Details /
	// Admission Order / Inpatient Billables / Discharge Details /
	// Connections), real dashboard, real Save/Discharge/Create buttons -
	// inside a popup, without reimplementing or guessing at any of
	// Frappe's own form-rendering internals.
	function openInpatientRecordDialog(inpatientRecordName) {
		const dialog = new frappe.ui.Dialog({
			title: __('Inpatient Record'),
			size: 'extra-large',
			secondary_action_label: __('Open in New Tab'),
			secondary_action: function() {
				window.open(frappe.utils.get_form_link('Inpatient Record', inpatientRecordName), '_blank');
			}
		});

		// Same trim as Doctor Station's dialog - the iframe is doing all
		// the real work, so this dialog's own footer bar just eats space.
		dialog.$wrapper.find('.modal-footer').hide();

		dialog.$wrapper.find('.modal-dialog').css('max-width', '95vw');
		const $body = dialog.$wrapper.find('.modal-body');
		$body.css({ padding: 0, height: '85vh', overflow: 'hidden' });
		$body.html(
			`<iframe src="${frappe.utils.get_form_link('Inpatient Record', inpatientRecordName)}" ` +
			`style="width: 100%; height: 100%; border: 0;" title="${frappe.utils.escape_html(__('Inpatient Record'))}"></iframe>`
		);

		// Same same-origin chrome-trimming as Doctor Station's dialog -
		// hides the iframe's own Desk sidebar/navbar so it reads as
		// in-dialog content rather than a second app shell nested inside
		// this one. See that function's own comment for why this is CSS
		// (harmless if a selector doesn't match) rather than anything
		// that could throw.
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
				console.error('openInpatientRecordDialog: could not trim iframe chrome', e);
			}
		});

		dialog.show();

		// Nothing here can know when the nurse is actually done inside the
		// iframe (same-origin, but its own Desk instance/router) - refresh
		// the list whenever the dialog closes instead, same rationale as
		// Doctor Station's dialog.onhide.
		dialog.onhide = function() {
			loadAdmittedPatients();
		};
	}

	// Mirrors inpatient_record.js's own admit_patient_dialog(frm) field-
	// for-field - same Service Unit Type/Service Unit/Currency/Price
	// List/Admission Datetime/Expected Discharge fields and the same
	// get_query filters - just reached via run_doc_method's generic
	// doc-method RPC (see this file's own note on that pattern above
	// Admission Orders' Accept/Reject) against the plain record dict
	// get_admitted_patients() returned, rather than a loaded frm.doc.
	// This is what turns an "Admission Scheduled" record (created the
	// moment an Admission Order is accepted, before any bed is assigned -
	// see get_admitted_patients()'s own docstring) into "Admitted".
	function openAdmitPatientDialog(record) {
		let dialog = new frappe.ui.Dialog({
			title: __('Admit Patient - {0}', [record.patient_name || record.patient]),
			width: 100,
			fields: [
				{
					fieldtype: 'Link',
					label: __('Service Unit Type'),
					fieldname: 'service_unit_type',
					options: 'Healthcare Service Unit Type',
					default: record.admission_service_unit_type,
					get_query: function() {
						return { filters: { inpatient_occupancy: 1, allow_appointments: 0 } };
					}
				},
				{
					fieldtype: 'Link',
					label: __('Service Unit'),
					fieldname: 'service_unit',
					options: 'Healthcare Service Unit',
					reqd: 1,
					get_query: function() {
						return {
							filters: {
								is_group: 0,
								company: record.company,
								service_unit_type: dialog.get_value('service_unit_type'),
								occupancy_status: 'Vacant'
							}
						};
					}
				},
				{ fieldtype: 'Section Break' },
				{ fieldtype: 'Link', label: __('Currency'), fieldname: 'currency', options: 'Currency', reqd: 1 },
				{ fieldtype: 'Column Break' },
				{
					fieldtype: 'Link',
					label: __('Price List'),
					fieldname: 'price_list',
					options: 'Price List',
					reqd: 1,
					get_query: function() {
						return { filters: [['Price List', 'currency', '=', dialog.get_value('currency')]] };
					}
				},
				{ fieldtype: 'Section Break' },
				{
					fieldtype: 'Datetime',
					label: __('Admission Datetime'),
					fieldname: 'check_in',
					reqd: 1,
					default: frappe.datetime.now_datetime()
				},
				{
					fieldtype: 'Date',
					label: __('Expected Discharge'),
					fieldname: 'expected_discharge',
					default: record.expected_length_of_stay
						? frappe.datetime.add_days(frappe.datetime.now_datetime(), record.expected_length_of_stay)
						: ''
				}
			],
			primary_action_label: __('Admit'),
			primary_action: function() {
				const service_unit = dialog.get_value('service_unit');
				const check_in = dialog.get_value('check_in');
				if (!service_unit || !check_in) return;
				frappe.call({
					method: 'run_doc_method',
					args: {
						dt: 'Inpatient Record',
						dn: record.name,
						method: 'admit',
						args: {
							service_unit: service_unit,
							check_in: check_in,
							expected_discharge: dialog.get_value('expected_discharge') || null,
							currency: dialog.get_value('currency'),
							price_list: dialog.get_value('price_list')
						}
					},
					freeze: true,
					freeze_message: __('Processing Patient Admission'),
					callback: function(r) {
						if (!r.exc) {
							dialog.hide();
							frappe.show_alert({ message: __('Patient admitted'), indicator: 'green' }, 5);
							loadAdmittedPatients();
						}
					}
				});
			}
		});

		frappe.db.get_value('Patient', record.patient, ['default_currency', 'default_price_list']).then((r) => {
			const values = r.message || {};
			dialog.set_value('currency', values.default_currency);
			dialog.set_value('price_list', values.default_price_list);
		});

		dialog.show();
	}

	// Mirrors inpatient_record.js's own schedule_discharge(frm) dialog
	// field-for-field, and the same schedule -> generate billables sequence
	// its "Schedule Discharge" button runs via frappe.run_serially - so a
	// discharge scheduled from here looks identical to one scheduled from
	// the full Inpatient Record form.
	function openScheduleDischargeDialog(inpatient_record, patient) {
		const dialog = new frappe.ui.Dialog({
			title: __('Schedule Discharge'),
			fields: [
				{
					fieldtype: 'Link',
					label: __('Discharge Practitioner'),
					fieldname: 'discharge_practitioner',
					options: 'Healthcare Practitioner'
				},
				{
					fieldtype: 'Datetime',
					label: __('Discharge Ordered DateTime'),
					fieldname: 'discharge_ordered_datetime',
					default: frappe.datetime.now_datetime()
				},
				{
					fieldtype: 'Date',
					label: __('Followup Date'),
					fieldname: 'followup_date'
				},
				{ fieldtype: 'Column Break' },
				{
					fieldtype: 'Small Text',
					label: __('Discharge Instructions'),
					fieldname: 'discharge_instructions'
				},
				{ fieldtype: 'Section Break', label: __('Discharge Summary') },
				{
					fieldtype: 'Long Text',
					label: __('Discharge Note'),
					fieldname: 'discharge_note'
				}
			],
			primary_action_label: __('Order Discharge'),
			primary_action: function() {
				const discharge_order = {
					patient: patient,
					discharge_practitioner: dialog.get_value('discharge_practitioner'),
					discharge_ordered_datetime: dialog.get_value('discharge_ordered_datetime'),
					followup_date: dialog.get_value('followup_date'),
					discharge_instructions: dialog.get_value('discharge_instructions'),
					discharge_note: dialog.get_value('discharge_note')
				};
				frappe.call({
					method: 'healthcare.healthcare.doctype.inpatient_record.inpatient_record.schedule_discharge',
					args: { discharge_order: discharge_order },
					freeze: true,
					freeze_message: __('Scheduling Inpatient Discharge'),
					callback: function(r) {
						if (r.exc) {
							return;
						}
						dialog.hide();
						frappe.call({
							method: 'run_doc_method',
							args: {
								dt: 'Inpatient Record',
								dn: inpatient_record,
								method: 'add_service_unit_rent_to_billable_items'
							},
							callback: function() {
								frappe.show_alert({ message: __('Discharge scheduled'), indicator: 'green' }, 5);
								loadAdmittedPatients();
							}
						});
					}
				});
			}
		});
		dialog.show();
		dialog.$wrapper.find('.modal-dialog').css('width', '800px');
	}

	loadAll();
};
