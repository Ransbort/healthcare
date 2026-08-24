frappe.pages['nurse-station'].on_page_load = function(wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Nurse Station',
		single_column: true
	});

	// =============================================
	// REALTIME SOUND NOTIFICATIONS
	// =============================================
	// Same pattern as Front Desk / Cashier Portal - a nurse working
	// something else (charting, another patient) still hears/sees a new
	// arrival instead of having to keep this tab in view.
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
		loadNurseQueue();
	});

	// Add custom CSS
	const style = `
		<style>
			.ns-wrapper { padding: 20px; max-width: 1400px; margin: 0 auto; }

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

			@media (max-width: 768px) {
				.ns-wrapper { padding: 15px; }
			}
		</style>
	`;
	$(style).appendTo(page.main);

	let html = `
		<div class="ns-wrapper">
			<div class="filter-bar">
				<div data-fieldname="n_date"></div>
				<button class="btn btn-primary" id="nurse-refresh-btn"><i class="fa fa-refresh"></i> Refresh</button>
				<button class="btn btn-danger" id="nurse-clear-all-btn"><i class="fa fa-trash"></i> Clear All</button>
			</div>
			<div class="queue-table-container" id="nurse-table-container"></div>
		</div>
	`;
	$(html).appendTo(page.main);

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

	// =============================================
	// NURSE STATION QUEUE
	// =============================================
	let n_date = frappe.ui.form.make_control({
		parent: page.main.find('[data-fieldname="n_date"]'),
		df: { fieldtype: 'Date', fieldname: 'n_date', label: 'Date', default: frappe.datetime.get_today() },
		render_input: true
	});
	n_date.refresh();
	n_date.set_value(frappe.datetime.get_today());
	loadNurseQueue();

	page.main.find('#nurse-refresh-btn').on('click', function() { loadNurseQueue(); });

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
			callback: function(r) { renderNurseTable(r.message || []); }
		});
	}

	function renderNurseTable(rows) {
		const container = page.main.find('#nurse-table-container');
		if (!rows.length) {
			container.html(`<div class="empty-state"><i class="fa fa-stethoscope"></i><h4>${__('Nurse queue is empty')}</h4></div>`);
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
					<td>${row.encounter_time || ''}</td>
					<td>${row.patient_name || ''}</td>
					<td>${row.practitioner_name || row.practitioner || ''}</td>
					<td>${statusBadge(row.queue_status)}</td>
					<td>
						${actionBtn}
					</td>
				</tr>
			`;
		});
		container.html(`<table class="queue-table"><tbody>${body}</tbody></table>`);

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
};
