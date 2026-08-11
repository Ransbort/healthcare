frappe.pages['front-desk'].on_page_load = function(wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Front Desk',
		single_column: true
	});

	// =============================================
	// REALTIME SOUND NOTIFICATIONS
	// =============================================
	
	const notificationSound = new Audio(
		"/assets/healthcare/sounds/notify.mp3"
	);

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
		playNotification();
		frappe.show_alert({
			message: data.message,
			indicator: 'blue'
		}, 6);

		// Auto-refresh whichever tab is relevant and currently active,
		// so counts/rows update immediately without a manual refresh
		if (data.department === 'nurse' && page.main.find('#nurse-tab').hasClass('active')) {
			loadNurseQueue();
		}
		if (data.department === 'doctor' && page.main.find('#doctor-tab').hasClass('active')) {
			loadDoctorQueue();
		}
		if (page.main.find('#queue-tab').hasClass('active')) {
			loadQueue();
		}
	});

	const style = `
		<style>
			.fd-wrapper { padding: 20px; max-width: 1400px; margin: 0 auto; }

			.tabs-section {
				display: flex; gap: 10px; margin-bottom: 20px;
				border-bottom: 2px solid #e0e0e0; align-items: center; flex-wrap: wrap;
			}
			.tab-btn {
				padding: 12px 24px; background: transparent; border: none;
				border-bottom: 3px solid transparent; color: #6c757d; font-weight: 600;
				font-size: 1rem; cursor: pointer; transition: all 0.3s ease;
				position: relative; bottom: -2px;
			}
			.tab-btn:hover { color: var(--primary-color); }
			.tab-btn.active { color: var(--primary-color); border-bottom-color: var(--primary-color); }
			.tab-content { display: none; }
			.tab-content.active { display: block; }

			.fd-section {
				background: white; border: 1px solid #d1d8dd; border-radius: 12px;
				padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 20px;
				overflow: visible; position: relative;
			}
			.fd-section h5 { font-weight: 600; margin-bottom: 15px; color: #495057; }
			.fd-section .fd-hint { font-size: 0.85rem; color: #6c757d; margin: -10px 0 15px; }

			.toggle-group {
				display: flex; border: 1px solid #e0e0e0; border-radius: 8px;
				overflow: hidden; width: fit-content; margin-bottom: 15px;
			}
			.toggle-btn {
				padding: 10px 24px; background: #f8f9fa; border: none; color: #6c757d;
				font-weight: 600; font-size: 0.95rem; cursor: pointer; transition: all 0.3s ease;
			}
			.toggle-btn:hover { background: #e9ecef; }
			.toggle-btn.active { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }

			.form-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 15px; overflow: visible; padding:15px; }
			.form-grid .frappe-control, .form-grid .form-group { margin-bottom: 0; overflow: visible; position: relative; }
			.form-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; overflow: visible; }
			.form-grid-2 .frappe-control, .form-grid-2 .form-group { margin-bottom: 0; overflow: visible; position: relative; }

			/* Autocomplete dropdowns (Link fields) must render above sibling grid cells */
			.form-grid .awesomplete, .form-grid-2 .awesomplete { position: relative; }
			.form-grid .awesomplete > ul, .form-grid-2 .awesomplete > ul { z-index: 999 !important; }

			.filter-bar {
				display: flex; gap: 15px; margin-bottom: 20px; padding: 15px;
				background: #f8f9fa; border-radius: 8px; align-items: end;
			}
			.filter-bar .frappe-control, .filter-bar .form-group { margin-bottom: 0; flex: 1; }

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

			.empty-state { text-align: center; padding: 60px 20px; color: #6c757d; }
			.empty-state i { font-size: 64px; margin-bottom: 20px; opacity: 0.3; }
			.empty-state h4 { font-size: 1.3rem; margin-bottom: 10px; color: #495057; }

			.vitals-form { background: #f8f9fa; border-radius: 8px; padding: 15px; margin-top: 10px; display: none; }
			.vitals-form.open { display: block; }

			/* =============================================
			   PATIENT CONFIRMATION DIALOG
			   ============================================= */
			.pcd-wrap { margin: -8px -4px; }

			.pcd-header {
				display: flex; align-items: center; gap: 14px;
				padding: 18px 20px; border-radius: 10px; margin-bottom: 18px;
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;
			}
			.pcd-header .pcd-avatar {
				width: 46px; height: 46px; border-radius: 50%;
				background: rgba(255,255,255,0.2); display: flex; align-items: center;
				justify-content: center; font-size: 1.3rem; flex-shrink: 0;
			}
			.pcd-header .pcd-title { font-size: 1.05rem; font-weight: 700; line-height: 1.3; }
			.pcd-header .pcd-subtitle { font-size: 0.8rem; opacity: 0.85; margin-top: 2px; }

			.pcd-grid {
				display: grid; grid-template-columns: 1fr 1fr; gap: 0;
				border: 1px solid #e9ecef; border-radius: 10px; overflow: hidden;
				margin-bottom: 16px;
			}
			.pcd-field {
				padding: 12px 16px; border-bottom: 1px solid #e9ecef; border-right: 1px solid #e9ecef;
			}
			.pcd-field:nth-child(2n) { border-right: none; }
			.pcd-field:last-child, .pcd-field:nth-last-child(2):nth-child(2n+1) { border-bottom: none; }
			.pcd-field .pcd-label {
				font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em;
				color: #8a94a6; font-weight: 600; margin-bottom: 3px;
			}
			.pcd-field .pcd-value { font-size: 0.95rem; color: #2b2f38; font-weight: 500; word-break: break-word; }

			.pcd-fee-box {
				display: flex; align-items: center; justify-content: space-between; gap: 12px;
				padding: 14px 18px; border-radius: 10px; margin-bottom: 14px;
				background: #fff8ec; border: 1px solid #fbe3b6;
			}
			.pcd-fee-box.pcd-fee-free { background: #edf9f0; border-color: #bfe6c9; }
			.pcd-fee-box .pcd-fee-icon {
				width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0;
				background: #f6c453; color: #7a3e00; display: flex; align-items: center; justify-content: center;
			}
			.pcd-fee-box.pcd-fee-free .pcd-fee-icon { background: #7fcf94; color: #155724; }
			.pcd-fee-box .pcd-fee-text { font-size: 0.85rem; color: #7a3e00; line-height: 1.4; }
			.pcd-fee-box.pcd-fee-free .pcd-fee-text { color: #155724; }
			.pcd-fee-box .pcd-fee-amount { font-size: 1.25rem; font-weight: 700; color: #7a3e00; white-space: nowrap; }
			.pcd-fee-box.pcd-fee-free .pcd-fee-amount { color: #155724; }

			.pcd-note { font-size: 0.8rem; color: #8a94a6; line-height: 1.5; padding: 0 2px; }

			@media (max-width: 768px) {
				.fd-wrapper { padding: 15px; }
				.form-grid, .form-grid-2 { grid-template-columns: 1fr; }
				.tabs-section { overflow-x: auto; flex-wrap: nowrap; }
				.pcd-grid { grid-template-columns: 1fr; }
				.pcd-field:nth-child(2n) { border-right: none; }
				.pcd-field { border-right: none !important; }
				.pcd-fee-box { flex-direction: column; align-items: flex-start; }
			}
		</style>
	`;
	$(style).appendTo(page.main);

	let html = `
		<div class="fd-wrapper">
			<div class="tabs-section">
				<button class="tab-btn active" data-tab="checkin"><i class="fa fa-user-plus"></i> Check-In</button>
				<button class="tab-btn" data-tab="queue"><i class="fa fa-list"></i> Queue</button>
				<button class="tab-btn" data-tab="nurse"><i class="fa fa-stethoscope"></i> Nurse Station</button>
				<button class="tab-btn" data-tab="doctor"><i class="fa fa-user-md"></i> Doctor Queue</button>
			</div>

			<!-- CHECK-IN TAB -->
			<div class="tab-content active" id="checkin-tab">
				<div class="fd-section">
					<h5><i class="fa fa-id-card"></i> Patient</h5>
					<div class="toggle-group">
						<button class="toggle-btn active" data-mode="existing">Existing Patient</button>
						<button class="toggle-btn" data-mode="new">New Patient</button>
					</div>
					<div id="existing-patient-block">
						<div class="form-grid-2">
							<div data-fieldname="ci_patient"></div>
						</div>
					</div>
					<div id="new-patient-block" style="display:none;">
						<div class="form-grid">
							<div data-fieldname="np_first_name"></div>
							<div data-fieldname="np_last_name"></div>
							<div data-fieldname="np_mobile"></div>
						</div>
						<div class="form-grid">
							<div data-fieldname="np_gender"></div>
							<div data-fieldname="np_dob"></div>
							<div data-fieldname="np_uid"></div>
						</div>
						<button class="btn btn-sm btn-secondary" id="register-patient-btn">
							<i class="fa fa-plus"></i> Register Patient
						</button>
					</div>
					<div class="fd-hint" id="patient-fee-warning" style="display:none; color:#b45309; font-weight:600;"></div>
				</div>

				<div class="fd-section">
					<h5><i class="fa fa-sign-in"></i> Check-In</h5>
					<p class="fd-hint">
						${__('Pick a booked appointment to check it in, or leave it blank for a walk-in with no prior booking.')}
					</p>
					<div class="form-grid">
						<div data-fieldname="ci_appointment"></div>
						<div data-fieldname="ci_practitioner"></div>
						<div data-fieldname="ci_department"></div>
					</div>
					<div class="form-grid">
						<div data-fieldname="ci_appointment_type"></div>
						<div data-fieldname="ci_date"></div>
						<div data-fieldname="ci_time"></div>
					</div>
					<div class="form-grid">
						<div data-fieldname="ci_fee"></div>
					</div>
					<button class="btn btn-success btn-lg" id="create-consultation-btn">
						<i class="fa fa-check"></i> Check In &amp; Bill
					</button>
				</div>
			</div>

			<!-- QUEUE TAB -->
			<div class="tab-content" id="queue-tab">
				<div class="filter-bar">
					<div data-fieldname="q_date"></div>
					<button class="btn btn-primary" id="queue-filter-btn"><i class="fa fa-filter"></i> Filter</button>
					<button class="btn btn-default" id="queue-refresh-btn"><i class="fa fa-refresh"></i> Refresh</button>
					<button class="btn btn-success" id="bulk-send-nurse-btn" style="display:none;">
						<i class="fa fa-forward"></i> Send All to Nurse (<span id="bulk-send-nurse-count">0</span>)
					</button>
				</div>
				<div class="queue-table-container" id="queue-table-container"></div>
			</div>

			<!-- NURSE STATION TAB -->
			<div class="tab-content" id="nurse-tab">
				<div class="filter-bar">
					<div data-fieldname="n_date"></div>
					<button class="btn btn-primary" id="nurse-refresh-btn"><i class="fa fa-refresh"></i> Refresh</button>
				</div>
				<div class="queue-table-container" id="nurse-table-container"></div>
			</div>

			<!-- DOCTOR QUEUE TAB -->
			<div class="tab-content" id="doctor-tab">
				<div class="filter-bar">
					<div data-fieldname="d_date"></div>
					<button class="btn btn-primary" id="doctor-refresh-btn"><i class="fa fa-refresh"></i> Refresh</button>
				</div>
				<div class="queue-table-container" id="doctor-table-container"></div>
			</div>
		</div>
	`;
	$(html).appendTo(page.main);

	// The browser's local date/timezone can disagree with the site's —
	// encounter_date is always stamped server-side, so re-anchor to the
	// site's actual "today" every time it matters, not just once at load.
	function withServerToday(callback) {
		frappe.call({
			method: 'healthcare.healthcare.page.front_desk.front_desk.get_server_today',
			callback: function(r) {
				if (r.message) callback(r.message);
			}
		});
	}

	withServerToday(function(serverToday) {
		[ci_date, q_date, n_date, d_date].forEach(function(ctrl) {
			if (ctrl) ctrl.set_value(serverToday);
		});
	});

	// =============================================
	// STATE
	// =============================================
	let checkinMode = 'existing';
	let registeredPatient = null;
	let autoGeneratePatientUid = false;

	// =============================================
	// CHECK-IN CONTROLS
	// =============================================
	let ci_patient = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="ci_patient"]'),
		df: {
			fieldtype: 'Link', fieldname: 'ci_patient', options: 'Patient', label: 'Search Patient', placeholder: 'Name or mobile number',
			onchange: function() { checkPatientRegistrationStatus(ci_patient.get_value()); }
		},
		render_input: true
	});
	ci_patient.refresh();

	// Frappe's built-in "+ Create a new Patient" item (shown in this
	// dropdown when a search finds no match) opens a generic quick-entry
	// dialog that creates a Patient — and its Customer — immediately,
	// with none of the deferred-customer-creation / confirmation-popup /
	// registration-fee-invoice logic the New Patient tab below provides.
	// A patient created that way would end up inconsistent with everyone
	// else. Redirect it to that tab instead of disabling it outright
	// (disabling it via only_select would also kill this field's live
	// search-as-you-type, which we need to keep).
	ci_patient.new_doc = function(txt) {
		checkinMode = 'new';
		page.main.find('.toggle-btn').removeClass('active');
		page.main.find('.toggle-btn[data-mode="new"]').addClass('active');
		page.main.find('#existing-patient-block').hide();
		page.main.find('#new-patient-block').show();
		page.main.find('#patient-fee-warning').hide();
		page.main.find('#create-consultation-btn').prop('disabled', false);

		if (txt) {
			const parts = txt.trim().split(/\s+/);
			np_first_name.set_value(parts[0] || '');
			if (parts.length > 1) np_last_name.set_value(parts.slice(1).join(' '));
		}

		frappe.show_alert({
			message: __('No matching patient — use the New Patient form below to register {0}', [txt || __('them')]),
			indicator: 'blue'
		}, 6);
	};

	// Warn (and block Check In) up front if the picked/registered
	// patient still owes a registration fee, instead of only finding
	// out from the server error the check-in call would otherwise
	// throw (see _ensure_patient_enabled in front_desk.py).
	function checkPatientRegistrationStatus(patientId) {
		const $warning = page.main.find('#patient-fee-warning');
		const $checkinBtn = page.main.find('#create-consultation-btn');

		if (!patientId) {
			$warning.hide();
			$checkinBtn.prop('disabled', false);
			return;
		}

		frappe.call({
			method: 'healthcare.healthcare.page.front_desk.front_desk.get_patient_checkin_status',
			args: { patient: patientId },
			callback: function(r) {
				if (r.message && r.message.registration_fee_pending) {
					$warning.text(__('Registration fee is still pending for this patient — collect payment at the Cashier Portal before checking them in.')).show();
					$checkinBtn.prop('disabled', true);
				} else {
					$warning.hide();
					$checkinBtn.prop('disabled', false);
				}
			}
		});
	}

	let np_first_name = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="np_first_name"]'),
		df: { fieldtype: 'Data', fieldname: 'np_first_name', label: 'First Name', reqd: 1 },
		render_input: true
	});
	np_first_name.refresh();

	let np_last_name = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="np_last_name"]'),
		df: { fieldtype: 'Data', fieldname: 'np_last_name', label: 'Last Name' },
		render_input: true
	});
	np_last_name.refresh();

	let np_mobile = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="np_mobile"]'),
		df: { fieldtype: 'Data', fieldname: 'np_mobile', label: 'Mobile', options: 'Phone' },
		render_input: true
	});
	np_mobile.refresh();

	let np_gender = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="np_gender"]'),
		df: { fieldtype: 'Select', fieldname: 'np_gender', label: 'Gender', options: 'Male\nFemale\nOther' },
		render_input: true
	});
	np_gender.refresh();

	let np_dob = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="np_dob"]'),
		df: { fieldtype: 'Date', fieldname: 'np_dob', label: 'Date of Birth' },
		render_input: true
	});
	np_dob.refresh();

	let np_uid = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="np_uid"]'),
		df: { fieldtype: 'Data', fieldname: 'np_uid', label: 'Identification Number (UID)' },
		render_input: true
	});
	np_uid.refresh();

	// Whether the UID is typed in here or generated server-side is a
	// Healthcare Settings toggle - fetch it once on load so the field
	// can switch into a read-only "fetches and displays" mode instead
	// of an editable input. Defaults to the manual/editable behaviour
	// until the call returns, and again if it fails, so the field is
	// never silently stuck un-usable.
	frappe.call({
		method: 'healthcare.healthcare.page.front_desk.front_desk.get_front_desk_settings',
		callback: function(r) {
			autoGeneratePatientUid = !!(r.message && r.message.auto_generate_patient_uid);
			setUidFieldMode();
			applyTabAccess((r.message && r.message.allowed_tabs) || ['checkin', 'queue', 'nurse', 'doctor']);
		}
	});

	function applyTabAccess(allowedTabs) {
		const allTabs = ['checkin', 'queue', 'nurse', 'doctor'];

		allTabs.forEach(function(tab) {
			if (allowedTabs.indexOf(tab) === -1) {
				page.main.find(`.tab-btn[data-tab="${tab}"]`).hide();
				page.main.find(`#${tab}-tab`).removeClass('active').hide();
			}
		});

		// If the tab that's currently marked active just got hidden (or
		// nothing was active yet), fall back to the first tab this user
		// is actually allowed to see.
		const activeBtn = page.main.find('.tab-btn.active');
		if (!activeBtn.length || activeBtn.is(':hidden')) {
			page.main.find('.tab-btn').removeClass('active');
			page.main.find('.tab-content').removeClass('active');

			const firstAllowed = allTabs.find(t => allowedTabs.indexOf(t) !== -1);
			if (firstAllowed) {
				page.main.find(`.tab-btn[data-tab="${firstAllowed}"]`).addClass('active');
				page.main.find(`#${firstAllowed}-tab`).addClass('active').show();

				if (firstAllowed === 'queue') withServerToday(function(t) { q_date.set_value(t); loadQueue(); });
				if (firstAllowed === 'nurse') withServerToday(function(t) { n_date.set_value(t); loadNurseQueue(); });
				if (firstAllowed === 'doctor') withServerToday(function(t) { d_date.set_value(t); loadDoctorQueue(); });
			}
		}
	}

	function setUidFieldMode() {
		if (autoGeneratePatientUid) {
			np_uid.df.read_only = 1;
			np_uid.set_value('');
			np_uid.df.placeholder = __('Auto-generated on registration');
			if (np_uid.$input) {
				np_uid.$input.prop('placeholder', __('Auto-generated on registration'));
			}
		} else {
			np_uid.df.read_only = 0;
			np_uid.df.placeholder = '';
			if (np_uid.$input) {
				np_uid.$input.prop('placeholder', '');
			}
		}
		np_uid.refresh();
	}

	// Optional: an already-booked appointment being checked in. Left
	// blank => this is a walk-in with no prior booking.
	let ci_appointment = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="ci_appointment"]'),
		df: {
			fieldtype: 'Link', fieldname: 'ci_appointment', options: 'Patient Appointment',
			label: 'Existing Appointment (optional)',
			get_query: function() {
				return {
					filters: {
						status: ['!=', 'Cancelled']
					}
				};
			},
			onchange: function() {
				const name = ci_appointment.get_value();

				if (!name) {
					setAppointmentFieldsReadOnly(false);
					ci_practitioner.set_value('');
					ci_department.set_value('');
					ci_appointment_type.set_value('');
					ci_time.set_value('');
					withServerToday(function(t) { ci_date.set_value(t); });
					return;
				}

				frappe.db.get_doc('Patient Appointment', name).then(function(doc) {
					ci_practitioner.set_value(doc.practitioner || '');
					ci_department.set_value(doc.department || '');
					ci_appointment_type.set_value(doc.appointment_type || '');
					ci_date.set_value(doc.appointment_date || '');
					ci_time.set_value(doc.appointment_time || '');
					setAppointmentFieldsReadOnly(true);
				});
			}
		},
		render_input: true
	});
	ci_appointment.refresh();

	// Locks/unlocks the fields that get auto-filled from a picked
	// appointment, so front-desk staff can't edit values that came
	// from the booking itself.
	function setAppointmentFieldsReadOnly(readOnly) {
		[ci_practitioner, ci_department, ci_appointment_type, ci_date, ci_time].forEach(function(ctrl) {
			ctrl.df.read_only = readOnly ? 1 : 0;
			ctrl.refresh();
		});
	}

	let ci_practitioner = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="ci_practitioner"]'),
		df: { fieldtype: 'Link', fieldname: 'ci_practitioner', options: 'Healthcare Practitioner', label: 'Practitioner' },
		render_input: true
	});
	ci_practitioner.refresh();

	let ci_department = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="ci_department"]'),
		df: { fieldtype: 'Link', fieldname: 'ci_department', options: 'Medical Department', label: 'Department' },
		render_input: true
	});
	ci_department.refresh();

	// Only required for the walk-in path — when checking in a booked
	// appointment, its own appointment_type is inherited server-side.
	let ci_appointment_type = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="ci_appointment_type"]'),
		df: { fieldtype: 'Link', fieldname: 'ci_appointment_type', options: 'Appointment Type', label: 'Appointment Type' },
		render_input: true
	});
	ci_appointment_type.refresh();

	let ci_date = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="ci_date"]'),
		df: { fieldtype: 'Date', fieldname: 'ci_date', label: 'Date', default: frappe.datetime.get_today() },
		render_input: true
	});
	ci_date.refresh();
	ci_date.set_value(frappe.datetime.get_today());

	let ci_time = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="ci_time"]'),
		df: { fieldtype: 'Time', fieldname: 'ci_time', label: 'Time', default: frappe.datetime.now_time() },
		render_input: true
	});
	ci_time.refresh();

	let ci_fee = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="ci_fee"]'),
		df: { fieldtype: 'Currency', fieldname: 'ci_fee', label: 'Consultation Fee', default: 0 },
		render_input: true
	});
	ci_fee.refresh();

	// Existing/New toggle
	page.main.find('.toggle-btn').on('click', function() {
		const mode = $(this).data('mode');
		checkinMode = mode;
		page.main.find('.toggle-btn').removeClass('active');
		$(this).addClass('active');
		if (mode === 'existing') {
			page.main.find('#existing-patient-block').show();
			page.main.find('#new-patient-block').hide();
		} else {
			page.main.find('#existing-patient-block').hide();
			page.main.find('#new-patient-block').show();
			page.main.find('#patient-fee-warning').hide();
			page.main.find('#create-consultation-btn').prop('disabled', false);
		}
	});

	// Register new patient
	page.main.find('#register-patient-btn').on('click', function() {
		const first = np_first_name.get_value();
		if (!first) {
			frappe.show_alert({ message: __('First name is required'), indicator: 'orange' }, 5);
			return;
		}
		frappe.call({
			method: 'healthcare.healthcare.page.front_desk.front_desk.create_walkin_patient',
			args: {
				first_name: first,
				last_name: np_last_name.get_value(),
				mobile: np_mobile.get_value(),
				gender: np_gender.get_value(),
				dob: np_dob.get_value(),
				uid: np_uid.get_value()
			},
			freeze: true,
			freeze_message: __('Registering patient...'),
			callback: function(r) {
				if (r.message && r.message.status === 'Success') {
					// When auto-generation is on the field was left blank
					// on submit - fill it back in with whatever the
					// server actually generated so the operator sees the
					// real UID (and the confirmation popup below shows
					// it too, via details.uid).
					if (autoGeneratePatientUid) {
						np_uid.set_value(r.message.uid || '');
					}
					showPatientConfirmationDialog(r.message);
				}
			}
		});
	});

	// After a Patient record is created, show everything that was
	// entered back to the operator for a final check before the
	// registration-fee invoice gets raised against it — an invoice is
	// much more of a hassle to unwind than an unconfirmed Patient row.
	//
	// Beautified as a card-style summary (header + a two-column field
	// grid + a dedicated fee callout) instead of a plain HTML table,
	// so the registration fee amount is impossible to miss.
	function showPatientConfirmationDialog(details) {
		const fields = [
			[__('First Name'), details.first_name],
			[__('Last Name'), details.last_name],
			[__('Mobile'), details.mobile],
			[__('Gender'), details.gender],
			[__('Date of Birth'), frappe.datetime.str_to_user(details.dob)],
			[__('UID'), details.uid],
		].filter(function(row) { return row[1]; });

		const displayName = [details.first_name, details.last_name].filter(Boolean).join(' ');

		let fieldsHtml = fields.map(function(row) {
			return `
				<div class="pcd-field">
					<div class="pcd-label">${row[0]}</div>
					<div class="pcd-value">${frappe.utils.escape_html(row[1])}</div>
				</div>
			`;
		}).join('');

		let feeHtml = '';
		let noteHtml = '';

		// Mirrors the backend exactly: _raise_registration_invoice() only
		// actually raises an invoice when collect_registration_fee is on
		// AND a registration_fee amount is configured — if the amount is
		// missing it silently skips invoicing (see front_desk.py). So an
		// unconfigured amount is treated identically to "no fee" here,
		// rather than shown as a warning that implies something's broken.
		const hasAmount = details.registration_fee !== null && details.registration_fee !== undefined && details.registration_fee !== 0;
		const willActuallyCharge = !!details.fee_will_be_charged && hasAmount;

		if (willActuallyCharge) {
			feeHtml = `
				<div class="pcd-fee-box">
					<div style="display:flex; align-items:center; gap:12px;">
						<div class="pcd-fee-icon"><i class="fa fa-money"></i></div>
						<div class="pcd-fee-text">${__('Registration fee to be invoiced')}</div>
					</div>
					<div class="pcd-fee-amount">${format_currency(details.registration_fee)}</div>
				</div>
			`;
			noteHtml = `
				<div class="pcd-note">
					<i class="fa fa-info-circle"></i>
					${__('Confirming creates this patient\'s billing customer record and raises the invoice above. The patient stays disabled and blocked from check-in until the cashier confirms payment.')}
				</div>
			`;
		} else {
			feeHtml = `
				<div class="pcd-fee-box pcd-fee-free">
					<div style="display:flex; align-items:center; gap:12px;">
						<div class="pcd-fee-icon"><i class="fa fa-check"></i></div>
						<div class="pcd-fee-text">${__('No registration fee will be charged')}</div>
					</div>
				</div>
			`;
			noteHtml = `
				<div class="pcd-note">
					<i class="fa fa-info-circle"></i>
					${__('Confirming will finalize this patient\'s registration, including creating their billing customer record.')}
				</div>
			`;
		}

		let bodyHtml = `
			<div class="pcd-wrap">
				<div class="pcd-header">
					<div class="pcd-avatar"><i class="fa fa-user"></i></div>
					<div>
						<div class="pcd-title">${frappe.utils.escape_html(displayName || __('New Patient'))}</div>
						<div class="pcd-subtitle">${__('Please review the details below before confirming registration')}</div>
					</div>
				</div>
				<div class="pcd-grid">${fieldsHtml}</div>
				${feeHtml}
				${noteHtml}
			</div>
		`;

		const dialog = new frappe.ui.Dialog({
			title: __('Confirm New Patient Details'),
			fields: [{ fieldtype: 'HTML', options: bodyHtml }],
			primary_action_label: __('Confirm & Register'),
			primary_action: function() {
				frappe.call({
					method: 'healthcare.healthcare.page.front_desk.front_desk.confirm_patient_registration',
					args: { patient: details.patient },
					freeze: true,
					freeze_message: __('Confirming registration...'),
					callback: function(r) {
						if (r.message && r.message.status === 'Success') {
							dialog.confirmed = true;
							dialog.hide();

							registeredPatient = r.message.patient;

							if (r.message.registration_invoice) {
								frappe.show_alert({
									message: __('Patient {0} registered — registration fee invoice {1} created. Collect payment at the Cashier Portal before checking them in.', [r.message.patient_name, r.message.registration_invoice]),
									indicator: 'orange'
								}, 10);
							} else {
								frappe.show_alert({ message: __('Patient {0} registered', [r.message.patient_name]), indicator: 'green' }, 6);
							}

							checkinMode = 'existing';
							page.main.find('.toggle-btn').removeClass('active');
							page.main.find('.toggle-btn[data-mode="existing"]').addClass('active');
							page.main.find('#existing-patient-block').show();
							page.main.find('#new-patient-block').hide();
							ci_patient.set_value(registeredPatient);
							checkPatientRegistrationStatus(registeredPatient);
						}
					}
				});
			},
			secondary_action_label: __('Cancel'),
			secondary_action: function() {
				frappe.call({
					method: 'healthcare.healthcare.page.front_desk.front_desk.cancel_patient_registration',
					args: { patient: details.patient },
					callback: function() {
						dialog.confirmed = true; // already handled — skip the hidden-modal cleanup below
						dialog.hide();
						frappe.show_alert({ message: __('Registration discarded'), indicator: 'blue' }, 4);
					}
				});
			}
		});

		// Discard the unconfirmed Patient row if the operator closes
		// the dialog via the 'x'/escape instead of an explicit button,
		// so a walked-away registration doesn't linger unconfirmed.
		dialog.$wrapper.on('hidden.bs.modal', function() {
			if (!dialog.confirmed) {
				frappe.call({
					method: 'healthcare.healthcare.page.front_desk.front_desk.cancel_patient_registration',
					args: { patient: details.patient }
				});
			}
		});

		dialog.show();
	}

	// Check-in: either check in a picked appointment, or create a
	// walk-in encounter with no prior booking.
	page.main.find('#create-consultation-btn').on('click', function() {
		const appointment = ci_appointment.get_value();

		if (appointment) {
			frappe.call({
				method: 'healthcare.healthcare.page.front_desk.front_desk.check_in_appointment',
				args: {
					appointment: appointment,
					consultation_fee: ci_fee.get_value() || 0,
				},
				freeze: true,
				freeze_message: __('Checking in...'),
				callback: function(r) { handleCheckinResponse(r); }
			});
			return;
		}

		const patient = checkinMode === 'existing' ? ci_patient.get_value() : registeredPatient;
		const practitioner = ci_practitioner.get_value();

		if (!patient) {
			frappe.show_alert({ message: __('Please select or register a patient first'), indicator: 'orange' }, 5);
			return;
		}
		if (!practitioner) {
			frappe.show_alert({ message: __('Please select a practitioner'), indicator: 'orange' }, 5);
			return;
		}
		const appointmentType = ci_appointment_type.get_value();
		if (!appointmentType) {
			frappe.show_alert({ message: __('Please select an appointment type'), indicator: 'orange' }, 5);
			return;
		}

		frappe.call({
			method: 'healthcare.healthcare.page.front_desk.front_desk.create_walkin_encounter',
			args: {
				patient: patient,
				practitioner: practitioner,
				appointment_type: appointmentType,
				department: ci_department.get_value(),
				consultation_fee: ci_fee.get_value() || 0,
			},
			freeze: true,
			freeze_message: __('Checking in...'),
			callback: function(r) { handleCheckinResponse(r); }
		});
	});

	function handleCheckinResponse(r) {
		if (r.message && r.message.status === 'Success') {
			let msg = __('Checked in — {0}', [r.message.encounter]);
			if (r.message.invoice) {
				msg += ' — ' + __('Invoice {0} created, awaiting payment at Cashier Portal', [r.message.invoice]);
			}
			frappe.show_alert({ message: msg, indicator: r.message.invoice ? 'orange' : 'green' }, 8);
			ci_patient.set_value('');
			ci_appointment.set_value('');
			ci_practitioner.set_value('');
			ci_department.set_value('');
			ci_appointment_type.set_value('');
			ci_time.set_value('');
			setAppointmentFieldsReadOnly(false);
			withServerToday(function(t) { ci_date.set_value(t); });
			np_first_name.set_value('');
			np_last_name.set_value('');
			np_mobile.set_value('');
			np_gender.set_value('');
			np_dob.set_value('');
			np_uid.set_value('');
			setUidFieldMode();
			ci_fee.set_value(0);
			registeredPatient = null;
			page.main.find('#patient-fee-warning').hide();
			page.main.find('#create-consultation-btn').prop('disabled', false);
			if (page.main.find('#queue-tab').hasClass('active')) loadQueue();
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
		if (tab === 'queue') withServerToday(function(t) { q_date.set_value(t); loadQueue(); });
		if (tab === 'nurse') withServerToday(function(t) { n_date.set_value(t); loadNurseQueue(); });
		if (tab === 'doctor') withServerToday(function(t) { d_date.set_value(t); loadDoctorQueue(); });
	});

	// =============================================
	// QUEUE TAB
	// =============================================
	let q_date = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="q_date"]'),
		df: { fieldtype: 'Date', fieldname: 'q_date', label: 'Date', default: frappe.datetime.get_today() },
		render_input: true
	});
	q_date.refresh();
	q_date.set_value(frappe.datetime.get_today());

let currentQueueRows = [];

	page.main.find('#queue-filter-btn, #queue-refresh-btn').on('click', function() { loadQueue(); });

	page.main.find('#bulk-send-nurse-btn').on('click', function() {
		const eligible = currentQueueRows.filter(r => r.queue_status === 'Paid - Awaiting Vitals');
		if (!eligible.length) return;

		frappe.confirm(
			__('Send all {0} patient(s) awaiting vitals to the nurse queue?', [eligible.length]),
			function() {
				frappe.call({
					method: 'healthcare.healthcare.page.front_desk.front_desk.bulk_send_to_nurse',
					args: { encounters: eligible.map(r => r.name) },
					freeze: true,
					freeze_message: __('Sending to nurse...'),
					callback: function(r) {
						if (r.message && r.message.status === 'Success') {
							frappe.show_alert({
								message: __('Sent {0} patient(s) to nurse', [r.message.updated.length]),
								indicator: 'green'
							}, 5);
							loadQueue();
						}
					}
				});
			}
		);
	});
	function statusBadge(status) {
		const map = {
			'Registered': 'badge-registered',
			'Payment Pending': 'badge-pending',
			'Paid - Awaiting Vitals': 'badge-paid',
			'With Nurse': 'badge-nurse',
			'With Doctor': 'badge-doctor',
			'In Consultation': 'badge-consult',
			'Completed': 'badge-completed'
		};
		return `<span class="${map[status] || 'badge-registered'}">${status || ''}</span>`;
	}

function loadQueue() {
		frappe.call({
			method: 'healthcare.healthcare.page.front_desk.front_desk.get_queue',
			args: { date: q_date.get_value() },
			callback: function(r) {
				currentQueueRows = r.message || [];
				renderQueueTable(currentQueueRows);

				const eligibleCount = currentQueueRows.filter(row => row.queue_status === 'Paid - Awaiting Vitals').length;
				if (eligibleCount > 0) {
					page.main.find('#bulk-send-nurse-count').text(eligibleCount);
					page.main.find('#bulk-send-nurse-btn').show();
				} else {
					page.main.find('#bulk-send-nurse-btn').hide();
				}
			}
		});
	}

	function renderQueueTable(rows) {
		const container = page.main.find('#queue-table-container');
		if (!rows.length) {
			container.html(`<div class="empty-state"><i class="fa fa-inbox"></i><h4>${__('No checked-in patients')}</h4></div>`);
			return;
		}
		let body = '';
		rows.forEach(function(row) {
			let actionBtn = '';
			if (row.queue_status === 'Paid - Awaiting Vitals') {
				actionBtn = `<button class="btn btn-xs btn-primary btn-send-nurse" data-name="${row.name}">${__('Send to Nurse')}</button>`;
			}
			body += `
				<tr>
					<td>${row.encounter_time || ''}</td>
					<td>${row.patient_name || ''}</td>
					<td>${row.practitioner_name || row.practitioner || ''}</td>
					<td>${statusBadge(row.queue_status)}</td>
					<td>${row.consultation_invoice || '-'}</td>
					<td>${actionBtn}</td>
				</tr>
			`;
		});
		container.html(`
			<table class="queue-table">
				<thead><tr><th>${__('Time')}</th><th>${__('Patient')}</th><th>${__('Practitioner')}</th><th>${__('Status')}</th><th>${__('Invoice')}</th><th></th></tr></thead>
				<tbody>${body}</tbody>
			</table>
		`);
		container.find('.btn-send-nurse').on('click', function() {
			const name = $(this).data('name');
			frappe.call({
				method: 'healthcare.healthcare.page.front_desk.front_desk.send_to_nurse',
				args: { encounter: name },
				callback: function() {
					frappe.show_alert({ message: __('Sent to nurse'), indicator: 'green' }, 4);
					loadQueue();
				}
			});
		});
	}

	// =============================================
	// NURSE STATION TAB
	// =============================================
	let n_date = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="n_date"]'),
		df: { fieldtype: 'Date', fieldname: 'n_date', label: 'Date', default: frappe.datetime.get_today() },
		render_input: true
	});
	n_date.refresh();
	n_date.set_value(frappe.datetime.get_today());

	page.main.find('#nurse-refresh-btn').on('click', function() { loadNurseQueue(); });

	function loadNurseQueue() {
		frappe.call({
			method: 'healthcare.healthcare.page.front_desk.front_desk.get_queue',
			args: { date: n_date.get_value(), queue_status: 'With Nurse' },
			callback: function(r) { renderNurseTable(r.message || []); }
		});
	}

	function renderNurseTable(rows) {
		const container = page.main.find('#nurse-table-container');
		if (!rows.length) {
			container.html(`<div class="empty-state"><i class="fa fa-stethoscope"></i><h4>${__('No patients waiting for vitals')}</h4></div>`);
			return;
		}
		let body = '';
		rows.forEach(function(row) {
			body += `
				<tr class="nurse-row" data-name="${row.name}">
					<td>${row.encounter_time || ''}</td>
					<td>${row.patient_name || ''}</td>
					<td>${row.practitioner_name || row.practitioner || ''}</td>
					<td><button class="btn btn-xs btn-primary btn-open-vitals" data-name="${row.name}">${__('Record Vitals')}</button></td>
				</tr>
				<tr class="vitals-row" data-vitals-for="${row.name}"><td colspan="4">
					<div class="vitals-form" id="vitals-form-${row.name}">
						<div class="form-grid">
							<div data-vf="temp-${row.name}"></div>
							<div data-vf="bp-${row.name}"></div>
							<div data-vf="pulse-${row.name}"></div>
						</div>
						<div class="form-grid">
							<div data-vf="weight-${row.name}"></div>
							<div data-vf="height-${row.name}"></div>
							<div data-vf="bmi-${row.name}"></div>
						</div>
						<div class="form-grid">
							<div data-vf="spo2-${row.name}"></div>
							<div data-vf="fbs-${row.name}"></div>
							<div data-vf="rbs-${row.name}"></div>
						</div>
						<div class="form-grid-2">
							<div data-vf="notes-${row.name}"></div>
						</div>
						<button class="btn btn-success btn-sm btn-save-vitals" data-name="${row.name}">
							<i class="fa fa-check"></i> ${__('Save Vitals &amp; Send to Doctor')}
						</button>
					</div>
				</td></tr>
			`;
		});
		container.html(`<table class="queue-table"><tbody>${body}</tbody></table>`);

		container.find('.btn-open-vitals').on('click', function() {
			const name = $(this).data('name');
			const formEl = container.find(`#vitals-form-${name}`);
			if (formEl.hasClass('open')) { formEl.removeClass('open'); return; }
			formEl.addClass('open');
			if (formEl.data('built')) return;
			formEl.data('built', true);

			const temp = frappe.ui.form.make_control({ parent: container.find(`[data-vf="temp-${name}"]`), df: { fieldtype: 'Float', fieldname: 'temp', label: 'Temperature (°C)' }, render_input: true });
			temp.refresh();
			const bp = frappe.ui.form.make_control({ parent: container.find(`[data-vf="bp-${name}"]`), df: { fieldtype: 'Data', fieldname: 'bp', label: 'Blood Pressure', placeholder: '120/80' }, render_input: true });
			bp.refresh();
			const pulse = frappe.ui.form.make_control({ parent: container.find(`[data-vf="pulse-${name}"]`), df: { fieldtype: 'Int', fieldname: 'pulse', label: 'Pulse (bpm)' }, render_input: true });
			pulse.refresh();
			const weight = frappe.ui.form.make_control({ parent: container.find(`[data-vf="weight-${name}"]`), df: { fieldtype: 'Float', fieldname: 'weight', label: 'Weight (kg)' }, render_input: true });
			weight.refresh();
			const height = frappe.ui.form.make_control({ parent: container.find(`[data-vf="height-${name}"]`), df: { fieldtype: 'Float', fieldname: 'height', label: 'Height (cm)' }, render_input: true });
			height.refresh();
			// Read-only: this is a live client-side preview only, purely so
			// the nurse can see it while entering weight/height. The value
			// actually saved is always recomputed server-side in
			// save_vitals() -> _calculate_bmi(), never trusted from here.
			const bmi = frappe.ui.form.make_control({ parent: container.find(`[data-vf="bmi-${name}"]`), df: { fieldtype: 'Float', fieldname: 'bmi', label: 'BMI', precision: 2, read_only: 1, description: __('Auto-calculated from weight & height') }, render_input: true });
			bmi.refresh();
			const spo2 = frappe.ui.form.make_control({ parent: container.find(`[data-vf="spo2-${name}"]`), df: { fieldtype: 'Int', fieldname: 'spo2', label: 'SpO2 (%)' }, render_input: true });
			spo2.refresh();
			const fbs = frappe.ui.form.make_control({ parent: container.find(`[data-vf="fbs-${name}"]`), df: { fieldtype: 'Float', fieldname: 'fbs', label: 'FBS (mg/dL)' }, render_input: true });
			fbs.refresh();
			const rbs = frappe.ui.form.make_control({ parent: container.find(`[data-vf="rbs-${name}"]`), df: { fieldtype: 'Float', fieldname: 'rbs', label: 'RBS (mg/dL)' }, render_input: true });
			rbs.refresh();
			const notes = frappe.ui.form.make_control({ parent: container.find(`[data-vf="notes-${name}"]`), df: { fieldtype: 'Data', fieldname: 'notes', label: 'Notes' }, render_input: true });
			notes.refresh();

			function recalcBmiPreview() {
				const w = parseFloat(weight.get_value());
				const h = parseFloat(height.get_value());
				if (w > 0 && h > 0) {
					const heightM = h / 100;
					bmi.set_value(Math.round((w / (heightM * heightM)) * 100) / 100);
				} else {
					bmi.set_value('');
				}
			}
			if (weight.$input) weight.$input.on('change input', recalcBmiPreview);
			if (height.$input) height.$input.on('change input', recalcBmiPreview);

			formEl.data('controls', { temp, bp, pulse, weight, height, bmi, spo2, fbs, rbs, notes });
		});

		container.find('.btn-save-vitals').on('click', function() {
			const name = $(this).data('name');
			const formEl = container.find(`#vitals-form-${name}`);
			const c = formEl.data('controls');
			if (!c) return;
			frappe.call({
				method: 'healthcare.healthcare.page.front_desk.front_desk.save_vitals',
				args: {
					encounter: name,
					temperature: c.temp.get_value(),
					blood_pressure: c.bp.get_value(),
					pulse: c.pulse.get_value(),
					weight: c.weight.get_value(),
					height: c.height.get_value(),
					spo2: c.spo2.get_value(),
					fbs: c.fbs.get_value(),
					rbs: c.rbs.get_value(),
					notes: c.notes.get_value()
				},
				freeze: true,
				freeze_message: __('Saving vitals...'),
				callback: function(r) {
					if (r.message && r.message.status === 'Success') {
						frappe.show_alert({ message: __('Vitals saved, sent to doctor'), indicator: 'green' }, 5);
						loadNurseQueue();
					}
				}
			});
		});
	}

	// =============================================
	// DOCTOR QUEUE TAB
	// =============================================
	let d_date = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="d_date"]'),
		df: { fieldtype: 'Date', fieldname: 'd_date', label: 'Date', default: frappe.datetime.get_today() },
		render_input: true
	});
	d_date.refresh();
	d_date.set_value(frappe.datetime.get_today());

	page.main.find('#doctor-refresh-btn').on('click', function() { loadDoctorQueue(); });

	function loadDoctorQueue() {
		frappe.call({
			method: 'healthcare.healthcare.page.front_desk.front_desk.get_queue',
			args: { date: d_date.get_value(), queue_status: 'With Doctor' },
			callback: function(r) { renderDoctorTable(r.message || []); }
		});
	}

	function renderDoctorTable(rows) {
		const container = page.main.find('#doctor-table-container');
		if (!rows.length) {
			container.html(`<div class="empty-state"><i class="fa fa-user-md"></i><h4>${__('No patients waiting')}</h4></div>`);
			return;
		}
		let body = '';
		rows.forEach(function(row) {
			const vitalsSummary = [
				row.vitals_temperature ? `${row.vitals_temperature}°C` : null,
				row.vitals_blood_pressure || null,
				row.vitals_pulse ? `${row.vitals_pulse} bpm` : null,
				row.vitals_spo2 ? `SpO2 ${row.vitals_spo2}%` : null,
				row.vitals_bmi ? `BMI ${row.vitals_bmi}` : null,
				row.vitals_fbs ? `FBS ${row.vitals_fbs}` : null,
				row.vitals_rbs ? `RBS ${row.vitals_rbs}` : null
			].filter(Boolean).join(' · ') || __('No vitals recorded');
			body += `
				<tr>
					<td>${row.encounter_time || ''}</td>
					<td>${row.patient_name || ''}</td>
					<td>${row.practitioner_name || row.practitioner || ''}</td>
					<td><small>${vitalsSummary}</small></td>
					<td><button class="btn btn-xs btn-success btn-start-consult" data-name="${row.name}">${__('Start Consultation')}</button></td>
				</tr>
			`;
		});
		container.html(`
			<table class="queue-table">
				<thead><tr><th>${__('Time')}</th><th>${__('Patient')}</th><th>${__('Practitioner')}</th><th>${__('Vitals')}</th><th></th></tr></thead>
				<tbody>${body}</tbody>
			</table>
		`);
		container.find('.btn-start-consult').on('click', function() {
			const name = $(this).data('name');
			frappe.call({
				method: 'healthcare.healthcare.page.front_desk.front_desk.start_consultation',
				args: { encounter: name },
				callback: function(r) {
					if (r.message && r.message.status === 'Success') {
						// The Encounter already exists (created at check-in) —
						// open it directly instead of creating a new one.
						frappe.set_route('Form', 'Patient Encounter', r.message.encounter);
					}
				}
			});
		});
	}
};

//# sourceURL=front_desk.js