frappe.pages['rehab-portal'].on_page_load = function(wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Rehabilitation Portal',
        single_column: true
    });

	// =============================================
	// REALTIME SOUND NOTIFICATIONS
	// =============================================
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
	    if (data.department !== 'rehabilitation') return;

	    playNotification();
	    frappe.show_alert({
	        message: data.message,
	        indicator: 'blue'
	    }, 6);

	    loadTherapies();
	});

    const style = `
        <style>
            .rehab-wrapper {
                padding: 20px;
                max-width: 1400px;
                margin: 0 auto;
            }

            .sticky-header {
                position: sticky;
                top: 0;
                z-index: 100;
                background: white;
                padding-bottom: 16px;
                margin-bottom: 20px;
            }

            /* --- Toolbar: title + actions --- */
            .rehab-toolbar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding-bottom: 16px;
                margin-bottom: 16px;
                border-bottom: 1px solid #e9ecef;
            }

            .rehab-toolbar-title {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .rehab-toolbar-title .icon-badge {
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

            .rehab-toolbar-title h4 {
                margin: 0;
                font-size: 1.2rem;
                font-weight: 700;
                color: #1a1a2e;
                line-height: 1.3;
            }

            .rehab-toolbar-title .rehab-toolbar-subtitle {
                font-size: 0.83rem;
                color: #868e96;
                margin-top: 1px;
            }

            .rehab-toolbar-actions {
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

            .btn-new-request {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white !important;
                border: none;
                padding: 9px 18px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 0.88rem;
                display: flex;
                align-items: center;
                gap: 8px;
                transition: opacity 0.15s ease;
            }

            .btn-new-request:hover {
                opacity: 0.9;
                color: white;
            }

            /* --- Filter card --- */
            .rehab-wrapper .search-section {
                background: #ffffff !important;
                background-image: none !important;
                border: 1px solid #e9ecef;
                border-radius: 12px;
                padding: 20px 20px 14px;
                margin-bottom: 4px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
            }

            .search-input-group {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr auto auto;
                gap: 14px;
                align-items: end;
            }

            .search-input-group .frappe-control {
                flex: 1;
            }

            .search-input-group .form-group {
                margin-bottom: 0;
            }

            .rehab-wrapper .search-input-group label {
                color: #495057 !important;
                font-weight: 500;
                font-size: 0.83rem;
            }

            .search-input-group .form-control {
                border-radius: 8px;
                border: 1px solid #dee2e6;
            }

            #search-btn {
                border-radius: 8px;
                font-weight: 600;
                padding: 8px 18px;
            }

            #clear-btn {
                border-radius: 8px;
                font-weight: 600;
                padding: 8px 16px;
                background: transparent;
                border: 1px solid #dee2e6;
                color: #495057;
            }

            #clear-btn:hover {
                background: #f8f9fa;
            }

            /* --- Last updated --- */
            .rehab-wrapper .last-updated {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 0.78rem;
                color: #adb5bd !important;
                padding: 10px 2px 2px;
            }

            .tabs-section {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                border-bottom: 2px solid #e0e0e0;
                padding-bottom: 0;
                align-items: center;
            }

            .tab-btn {
                padding: 12px 24px;
                background: transparent;
                border: none;
                border-bottom: 3px solid transparent;
                color: #6c757d;
                font-weight: 600;
                font-size: 1rem;
                cursor: pointer;
                transition: all 0.3s ease;
                position: relative;
                bottom: -2px;
            }

            .tab-btn:hover {
                color: var(--primary-color);
            }

            .tab-btn.active {
                color: var(--primary-color);
                border-bottom-color: var(--primary-color);
            }

            .tab-btn .badge {
                margin-left: 8px;
                font-size: 0.8rem;
                padding: 3px 8px;
            }

            .view-toggle-group {
                margin-left: auto;
                display: flex;
                gap: 5px;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 2px;
                background: #f8f9fa;
            }

            .view-toggle-btn {
                padding: 6px 12px;
                background: transparent;
                border: none;
                color: #6c757d;
                cursor: pointer;
                border-radius: 4px;
                transition: all 0.2s ease;
            }

            .view-toggle-btn:hover {
                background: rgba(102, 126, 234, 0.1);
                color: var(--primary-color);
            }

            .view-toggle-btn.active {
                background: white;
                color: var(--primary-color);
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }

            .completed-filters {
                display: flex;
                gap: 15px;
                margin-bottom: 20px;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 8px;
                align-items: end;
            }

            .completed-filters .frappe-control {
                flex: 1;
            }

            .scrollable-content {
                max-height: calc(100vh - 400px);
                overflow-y: auto;
                padding-right: 10px;
            }

            .scrollable-content::-webkit-scrollbar {
                width: 8px;
            }

            .scrollable-content::-webkit-scrollbar-track {
                background: #f1f1f1;
                border-radius: 4px;
            }

            .scrollable-content::-webkit-scrollbar-thumb {
                background: #888;
                border-radius: 4px;
            }

            .scrollable-content::-webkit-scrollbar-thumb:hover {
                background: #555;
            }

            .tab-content {
                display: none;
            }

            .tab-content.active {
                display: block;
            }

            .rehab-cards-container {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                gap: 20px;
            }

            .rehab-list-container {
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }

            .rehab-list-table {
                width: 100%;
                border-collapse: collapse;
            }

            .rehab-list-table thead {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .rehab-list-table th {
                padding: 12px;
                text-align: left;
                font-weight: 600;
                font-size: 0.9rem;
            }

            .rehab-list-table tbody tr {
                border-bottom: 1px solid #e9ecef;
                transition: background 0.2s ease;
                cursor: pointer;
            }

            .rehab-list-table tbody tr:hover {
                background: #f8f9fa;
            }

            .rehab-list-table td {
                padding: 12px;
                font-size: 0.9rem;
            }

            .rehab-list-actions {
                display: flex;
                gap: 5px;
            }

            .rehab-list-actions .btn {
                padding: 4px 8px;
                font-size: 0.85rem;
            }

            .rehab-card {
                background: white;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                padding: 20px;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }

            .rehab-card:hover {
                border-color: var(--primary-color);
                box-shadow: 0 4px 16px rgba(102, 126, 234, 0.2);
                transform: translateY(-2px);
            }

            .rehab-card-header {
                display: flex;
                justify-content: space-between;
                align-items: start;
                margin-bottom: 15px;
                padding-bottom: 15px;
                border-bottom: 1px solid #e9ecef;
            }

            .rehab-card-title {
                font-size: 1.1rem;
                font-weight: 700;
                color: #2c3e50;
                margin-bottom: 4px;
            }

            .rehab-card-subtitle {
                font-size: 0.9rem;
                color: #6c757d;
            }

            .priority-badge {
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 0.75rem;
                font-weight: 600;
                text-transform: uppercase;
            }

            .priority-high {
                background: #f8d7da;
                color: #721c24;
            }

            .priority-medium {
                background: #fff3cd;
                color: #856404;
            }

            .priority-low {
                background: #d1ecf1;
                color: #0c5460;
            }

            .rehab-card-body {
                margin-bottom: 15px;
            }

            .rehab-card-info {
                display: flex;
                flex-direction: column;
                gap: 8px;
            }

            .info-row {
                display: flex;
                align-items: center;
                font-size: 0.9rem;
            }

            .info-row i {
                width: 20px;
                color: #6c757d;
                margin-right: 8px;
            }

            .info-label {
                color: #6c757d;
                margin-right: 5px;
            }

            .info-value {
                color: #2c3e50;
                font-weight: 600;
            }

            .diagnosis-row {
                background: #e7f3ff;
                padding: 8px;
                border-radius: 6px;
                margin-top: 8px;
            }

            .diagnosis-row .info-value {
                color: #0c5460;
            }

            .rehab-card-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding-top: 15px;
                border-top: 1px solid #e9ecef;
            }

            .status-badge {
                padding: 6px 12px;
                border-radius: 8px;
                font-size: 0.85rem;
                font-weight: 600;
            }

            .status-requested {
                background: #cfe2ff;
                color: #084298;
            }

            .status-pending {
                background: #fff3cd;
                color: #856404;
            }

            .status-completed {
                background: #d4edda;
                color: #155724;
            }

            .rehab-card-actions {
                display: flex;
                gap: 8px;
            }

            .btn-open-rehab {
                padding: 8px 16px;
                font-size: 0.9rem;
                font-weight: 600;
                border-radius: 8px;
            }

            .empty-state {
                grid-column: 1 / -1;
                text-align: center;
                padding: 60px 20px;
                color: #6c757d;
            }

            .empty-state i {
                font-size: 64px;
                margin-bottom: 20px;
                opacity: 0.3;
            }

            .empty-state h4 {
                font-size: 1.3rem;
                margin-bottom: 10px;
                color: #495057;
            }

            .empty-state p {
                font-size: 1rem;
                margin: 0;
            }

            @media (max-width: 768px) {
                .rehab-wrapper {
                    padding: 15px;
                }

                .rehab-toolbar {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 12px;
                }

                .rehab-toolbar-actions {
                    width: 100%;
                    justify-content: flex-end;
                }

                .search-input-group {
                    grid-template-columns: 1fr;
                }

                .rehab-cards-container {
                    grid-template-columns: 1fr;
                }

                .tabs-section {
                    overflow-x: auto;
                    flex-wrap: wrap;
                }

                .view-toggle-group {
                    margin-left: 0;
                    margin-top: 10px;
                }

                .rehab-list-table {
                    font-size: 0.85rem;
                }
            }
        </style>
    `;

    $(style).appendTo(page.main);

    let html = `
        <div class="rehab-wrapper">
            <div class="sticky-header">
                <div class="rehab-toolbar">
                    <div class="rehab-toolbar-title">
                        <div class="icon-badge"><i class="fa fa-heartbeat"></i></div>
                        <div>
                            <h4>Rehabilitation Portal</h4>
                            <div class="rehab-toolbar-subtitle">Search and manage therapy requests</div>
                        </div>
                    </div>
                    <div class="rehab-toolbar-actions">
                        <button class="btn-icon" id="refresh-btn" title="Refresh">
                            <i class="fa fa-refresh"></i>
                        </button>
                        <button class="btn-new-request" id="new-therapy-request-btn">
                            <i class="fa fa-plus"></i> New Therapy Request
                        </button>
                    </div>
                </div>

                <div class="search-section">
                    <div class="search-input-group">
                        <div class="frappe-control" data-fieldname="search_patient"></div>
                        <div class="frappe-control" data-fieldname="search_date"></div>
                        <div class="frappe-control" data-fieldname="search_encounter"></div>
                        <button class="btn btn-primary" id="search-btn">
                            <i class="fa fa-search"></i> Search
                        </button>
                        <button class="btn" id="clear-btn">
                            Clear
                        </button>
                    </div>
                    <div class="last-updated">
                        <i class="fa fa-clock-o"></i>
                        <span id="last-updated-time">Not loaded yet</span>
                    </div>
                </div>

                <div class="tabs-section">
                    <button class="tab-btn active" data-tab="requested">
                        <i class="fa fa-paper-plane"></i> Requested Therapies
                        <span class="badge badge-info" id="requested-count">0</span>
                    </button>
                    <button class="tab-btn" data-tab="pending">
                        <i class="fa fa-clock-o"></i> Pending Therapies
                        <span class="badge badge-warning" id="pending-count">0</span>
                    </button>
                    <button class="tab-btn" data-tab="completed">
                        <i class="fa fa-check-circle"></i> Completed Therapies
                        <span class="badge badge-success" id="completed-count">0</span>
                    </button>
                    <div class="view-toggle-group">
                        <button class="view-toggle-btn active" data-view="card" title="Card View">
                            <i class="fa fa-th-large"></i>
                        </button>
                        <button class="view-toggle-btn" data-view="list" title="List View">
                            <i class="fa fa-list"></i>
                        </button>
                    </div>
                </div>
            </div>

            <div class="tab-content active" id="requested-tab">
                <div class="scrollable-content">
                    <div class="rehab-cards-container" id="requested-rehab-container"></div>
                    <div class="rehab-list-container" id="requested-rehab-list" style="display: none;"></div>
                </div>
            </div>

            <div class="tab-content" id="pending-tab">
                <div class="scrollable-content">
                    <div class="rehab-cards-container" id="pending-rehab-container"></div>
                    <div class="rehab-list-container" id="pending-rehab-list" style="display: none;"></div>
                </div>
            </div>

            <div class="tab-content" id="completed-tab">
                <div class="completed-filters">
                    <div class="frappe-control" data-fieldname="completed_date"></div>
                    <button class="btn btn-primary" id="filter-completed-btn">
                        <i class="fa fa-filter"></i> Filter
                    </button>
                </div>
                <div class="scrollable-content">
                    <div class="rehab-cards-container" id="completed-rehab-container"></div>
                    <div class="rehab-list-container" id="completed-rehab-list" style="display: none;"></div>
                </div>
            </div>
        </div>
    `;

    $(html).appendTo(page.main);

    // Current view mode (card or list)
    let currentView = 'card';

    // Tracks how many of the 3 parallel loads (requested/pending/completed)
    // are still in flight, so the "Last updated" timestamp only refreshes
    // once everything currently on screen is current.
    let pendingLoads = 0;

    function markLoadDone() {
        pendingLoads = Math.max(0, pendingLoads - 1);
        if (pendingLoads === 0) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            page.main.find('#last-updated-time').text(`Updated at ${timeStr}`);
        }
    }

    let search_patient_field = frappe.ui.form.make_control({
        parent: page.main.find('[data-fieldname="search_patient"]'),
        df: {
            fieldtype: 'Link',
            fieldname: 'search_patient',
            options: 'Patient',
            label: 'Patient (Optional)',
            placeholder: 'Search by patient',
            onchange: function() {
                let patient_id = search_patient_field.get_value();
                if (patient_id) {
                    updateEncounterFilter(patient_id, search_date_field.get_value());
                } else {
                    search_encounter_field.set_value('');
                }
            }
        },
        render_input: true
    });

    let search_date_field = frappe.ui.form.make_control({
        parent: page.main.find('[data-fieldname="search_date"]'),
        df: {
            fieldtype: 'Date',
            fieldname: 'search_date',
            label: 'Encounter Date (Optional)',
            placeholder: 'Filter by date',
            onchange: function() {
                let patient_id = search_patient_field.get_value();
                let date = search_date_field.get_value();
                if (patient_id || date) {
                    updateEncounterFilter(patient_id, date);
                }
            }
        },
        render_input: true
    });

    let search_encounter_field = frappe.ui.form.make_control({
        parent: page.main.find('[data-fieldname="search_encounter"]'),
        df: {
            fieldtype: 'Link',
            fieldname: 'search_encounter',
            options: 'Patient Encounter',
            label: 'Encounter (Optional)',
            placeholder: 'Search by encounter',
            get_query: function() {
                let patient_id = search_patient_field.get_value();
                let date = search_date_field.get_value();

                let filters = { 'docstatus': ['in', [0, 1]] };

                if (!patient_id && !date) {
                    filters['name'] = ['=', ''];
                    return { filters: filters };
                }

                if (patient_id) {
                    filters['patient'] = patient_id;
                }

                if (date) {
                    filters['encounter_date'] = date;
                }

                return { filters: filters };
            }
        },
        render_input: true
    });

    let completed_date_field = frappe.ui.form.make_control({
        parent: page.main.find('[data-fieldname="completed_date"]'),
        df: {
            fieldtype: 'Date',
            fieldname: 'completed_date',
            label: 'Filter by Date',
            default: frappe.datetime.get_today()
        },
        render_input: true
    });

    completed_date_field.set_value(frappe.datetime.get_today());

    function updateEncounterFilter(patient_id, date) {
        search_encounter_field.df.get_query = function() {
            let filters = { 'docstatus': ['in', [0, 1]] };

            if (patient_id) {
                filters['patient'] = patient_id;
            }

            if (date) {
                filters['encounter_date'] = date;
            }

            return { filters: filters };
        };
        search_encounter_field.refresh();
    }

    // View toggle functionality
    page.main.find('.view-toggle-btn').on('click', function() {
        const view = $(this).data('view');
        currentView = view;

        page.main.find('.view-toggle-btn').removeClass('active');
        $(this).addClass('active');

        // Refresh current tab display
        const activeTab = page.main.find('.tab-btn.active').data('tab');
        if (activeTab === 'requested') {
            displayRequestedTherapies(window.lastRequestedTherapies || []);
        } else if (activeTab === 'pending') {
            displayPendingTherapies(window.lastPendingTherapies || []);
        } else if (activeTab === 'completed') {
            displayCompletedTherapies(window.lastCompletedTherapies || []);
        }
    });

    page.main.find('.tab-btn').on('click', function() {
        const tab = $(this).data('tab');
        page.main.find('.tab-btn').removeClass('active');
        $(this).addClass('active');
        page.main.find('.tab-content').removeClass('active');
        page.main.find(`#${tab}-tab`).addClass('active');
    });

    page.main.find('#search-btn').on('click', function() {
        loadTherapies();
    });

    page.main.find('#clear-btn').on('click', function() {
        search_patient_field.set_value('');
        search_date_field.set_value('');
        search_encounter_field.set_value('');
        loadTherapies();
    });

    // Toolbar refresh icon: reloads with current filters, gives a quick
    // spin for feedback (distinct from "Clear", which also resets filters).
    page.main.find('#refresh-btn').on('click', function() {
        const $icon = $(this).find('i');
        $icon.addClass('fa-spin');
        loadTherapies();
        setTimeout(() => $icon.removeClass('fa-spin'), 600);
    });

    page.main.find('#filter-completed-btn').on('click', function() {
        loadCompletedTherapies(
            search_patient_field.get_value(),
            search_encounter_field.get_value(),
            completed_date_field.get_value()
        );
    });

    page.main.find('#new-therapy-request-btn').on('click', function() {
        openNewTherapyRequestDialog();
    });

    // Direct therapy requests: no Patient Encounter involved. Creates a
    // standalone invoiced Therapy Plan via create_therapy_request(), which
    // then shows up in the Pending tab directly (see rehab_portal.py's
    // create_therapy_request docstring - same immediate-invoice pattern
    // as Lab Portal's direct requests). Unlike Lab Portal's dialog, a
    // Practitioner is required here since Therapy Plan.practitioner is
    // mandatory and there's no encounter to source it from.
    function openNewTherapyRequestDialog() {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_therapy_types',
            callback: function(r) {
                const types = r.message || [];

                const dialog = new frappe.ui.Dialog({
                    title: __('New Therapy Request'),
                    fields: [
                        {
                            fieldtype: 'Link',
                            fieldname: 'patient',
                            options: 'Patient',
                            label: 'Patient',
                            reqd: 1
                        },
                        {
                            fieldtype: 'Link',
                            fieldname: 'practitioner',
                            options: 'Healthcare Practitioner',
                            label: 'Practitioner',
                            reqd: 1
                        },
                        {
                            fieldtype: 'Column Break'
                        },
                        {
                            fieldtype: 'Select',
                            fieldname: 'therapy_type',
                            label: 'Therapy Type',
                            options: types.map(t => ({
                                label: `${t.name} (${format_currency(t.rate)})`,
                                value: t.name
                            })),
                            reqd: 1
                        },
                        {
                            fieldtype: 'Int',
                            fieldname: 'no_of_sessions',
                            label: 'No of Sessions',
                            default: 1,
                            reqd: 1
                        }
                    ],
                    primary_action_label: __('Create Request'),
                    primary_action: function(values) {
                        frappe.call({
                            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.create_therapy_request',
                            args: {
                                patient: values.patient,
                                therapy_type: values.therapy_type,
                                no_of_sessions: values.no_of_sessions || 1,
                                practitioner: values.practitioner
                            },
                            freeze: true,
                            freeze_message: __('Creating therapy request...'),
                            callback: function(r) {
                                if (r.message && r.message.status === 'Success') {
                                    frappe.show_alert({
                                        message: __('Therapy request created.'),
                                        indicator: 'green'
                                    }, 6);
                                    dialog.hide();
                                    loadTherapies();
                                }
                            },
                            error: function(r) {
                                frappe.show_alert({
                                    message: r.message || __('Error creating therapy request'),
                                    indicator: 'red'
                                }, 10);
                            }
                        });
                    }
                });

                dialog.show();
            }
        });
    }

    function loadTherapies() {
        const patient = search_patient_field.get_value();
        const encounter = search_encounter_field.get_value();
        const date = search_date_field.get_value();

        pendingLoads = 3;
        loadRequestedTherapies(patient, encounter, date);
        loadPendingTherapies(patient, encounter, date);
        loadCompletedTherapies(patient, encounter, completed_date_field.get_value());
    }

    function loadRequestedTherapies(patient, encounter, date) {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_requested_therapies',
            args: {
                search_patient: patient || null,
                search_encounter: encounter || null,
                search_date: date || null
            },
            callback: function(r) {
                const therapies = r.message || [];
                window.lastRequestedTherapies = therapies;
                displayRequestedTherapies(therapies);
                markLoadDone();
            }
        });
    }

    function loadPendingTherapies(patient, encounter, date) {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_pending_therapies',
            args: {
                search_patient: patient || null,
                search_encounter: encounter || null,
                search_date: date || null
            },
            freeze: true,
            freeze_message: __('Loading pending therapies...'),
            callback: function(r) {
                const therapies = r.message || [];
                window.lastPendingTherapies = therapies;
                displayPendingTherapies(therapies);
                markLoadDone();
            }
        });
    }

    function loadCompletedTherapies(patient, encounter, date) {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_completed_therapies',
            args: {
                search_patient: patient || null,
                search_encounter: encounter || null,
                filter_date: date || null
            },
            callback: function(r) {
                const therapies = r.message || [];
                window.lastCompletedTherapies = therapies;
                displayCompletedTherapies(therapies);
                markLoadDone();
            }
        });
    }

    function displayRequestedTherapies(therapies) {
        const cardContainer = page.main.find('#requested-rehab-container');
        const listContainer = page.main.find('#requested-rehab-list');

        cardContainer.empty();
        listContainer.empty();

        page.main.find('#requested-count').text(therapies.length);

        if (therapies.length === 0) {
            const emptyState = `
                <div class="empty-state">
                    <i class="fa fa-inbox"></i>
                    <h4>No Requested Therapies</h4>
                    <p>All therapy requests have been accepted or there are no new requests.</p>
                </div>
            `;
            cardContainer.html(emptyState);
            listContainer.html(emptyState);
            return;
        }

        if (currentView === 'card') {
            cardContainer.show();
            listContainer.hide();
            renderRequestedTherapyCards(therapies, cardContainer);
        } else {
            cardContainer.hide();
            listContainer.show();
            renderRequestedTherapyList(therapies, listContainer);
        }
    }

    function renderRequestedTherapyCards(therapies, container) {
        therapies.forEach(function(therapy) {
            const priorityClass = therapy.priority === 'High' ? 'priority-high' :
                                 therapy.priority === 'Medium' ? 'priority-medium' : 'priority-low';

            const card = $(`
                <div class="rehab-card">
                    <div class="rehab-card-header">
                        <div>
                            <div class="rehab-card-title">${therapy.therapy_type || '-'}</div>
                            <div class="rehab-card-subtitle">Sessions: ${therapy.no_of_sessions || 'N/A'}</div>
                        </div>
                        ${therapy.priority ? `<span class="priority-badge ${priorityClass}">${therapy.priority}</span>` : ''}
                    </div>
                    <div class="rehab-card-body">
                        <div class="rehab-card-info">
                            <div class="info-row">
                                <i class="fa fa-user"></i>
                                <span class="info-label">Patient:</span>
                                <span class="info-value">${therapy.patient_name} (${therapy.patient})</span>
                            </div>
                            <div class="info-row">
                                <i class="fa fa-calendar"></i>
                                <span class="info-label">Encounter Date:</span>
                                <span class="info-value">${frappe.datetime.str_to_user(therapy.encounter_date)}</span>
                            </div>
                            ${therapy.practitioner ? `
                            <div class="info-row">
                                <i class="fa fa-user-md"></i>
                                <span class="info-label">Practitioner:</span>
                                <span class="info-value">${therapy.practitioner}</span>
                            </div>
                            ` : ''}
                            ${therapy.diagnosis ? `
                            <div class="info-row diagnosis-row">
                                <i class="fa fa-stethoscope"></i>
                                <span class="info-label">Diagnosis:</span>
                                <span class="info-value">${therapy.diagnosis}</span>
                            </div>
                            ` : ''}
                            ${therapy.interval ? `
                            <div class="info-row">
                                <i class="fa fa-clock-o"></i>
                                <span class="info-label">Interval:</span>
                                <span class="info-value">${therapy.interval}</span>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="rehab-card-footer">
                        <span class="status-badge status-requested">
                            <i class="fa fa-paper-plane"></i> Requested
                        </span>
                        <div class="rehab-card-actions">
                            <button class="btn btn-success btn-accept-therapy">
                                <i class="fa fa-check"></i> Accept & Invoice
                            </button>
                        </div>
                    </div>
                </div>
            `);

            card.find('.btn-accept-therapy').on('click', function(e) {
                e.stopPropagation();
                acceptTherapyRequest(therapy);
            });

            container.append(card);
        });
    }

    function renderRequestedTherapyList(therapies, container) {
        let tableHtml = `
            <table class="rehab-list-table">
                <thead>
                    <tr>
                        <th>Therapy Type</th>
                        <th>Patient</th>
                        <th>Date</th>
                        <th>Practitioner</th>
                        <th>Diagnosis</th>
                        <th>Priority</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        therapies.forEach(function(therapy, index) {
            const priorityClass = therapy.priority === 'High' ? 'priority-high' :
                                 therapy.priority === 'Medium' ? 'priority-medium' : 'priority-low';

            tableHtml += `
                <tr>
                    <td><strong>${therapy.therapy_type || '-'}</strong><br><small>Sessions: ${therapy.no_of_sessions || 'N/A'}</small></td>
                    <td>${therapy.patient_name}<br><small>${therapy.patient}</small></td>
                    <td>${frappe.datetime.str_to_user(therapy.encounter_date)}</td>
                    <td>${therapy.practitioner || '-'}</td>
                    <td>${therapy.diagnosis || '-'}</td>
                    <td>${therapy.priority ? `<span class="priority-badge ${priorityClass}">${therapy.priority}</span>` : '-'}</td>
                    <td>
                        <div class="rehab-list-actions">
                            <button class="btn btn-success btn-sm btn-accept-therapy" data-idx="${index}">
                                <i class="fa fa-check"></i> Accept
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        });

        tableHtml += `
                </tbody>
            </table>
        `;

        container.html(tableHtml);

        // Keyed by row index, not therapy.therapy_id - direct-sourced rows
        // (see rehab_portal.py get_requested_therapies) all have
        // therapy_id null, which would collide if looked up by that field
        // whenever more than one direct request is showing at once.
        container.find('.btn-accept-therapy').on('click', function(e) {
            e.stopPropagation();
            const idx = $(this).data('idx');
            const therapy = therapies[idx];
            if (therapy) {
                acceptTherapyRequest(therapy);
            }
        });
    }

    function displayPendingTherapies(therapies) {
        const cardContainer = page.main.find('#pending-rehab-container');
        const listContainer = page.main.find('#pending-rehab-list');

        cardContainer.empty();
        listContainer.empty();

        page.main.find('#pending-count').text(therapies.length);

        if (therapies.length === 0) {
            const emptyState = `
                <div class="empty-state">
                    <i class="fa fa-check-circle"></i>
                    <h4>No Pending Therapies</h4>
                    <p>All therapies have been completed or there are no pending plans.</p>
                </div>
            `;
            cardContainer.html(emptyState);
            listContainer.html(emptyState);
            return;
        }

        if (currentView === 'card') {
            cardContainer.show();
            listContainer.hide();
            renderPendingTherapyCards(therapies, cardContainer);
        } else {
            cardContainer.hide();
            listContainer.show();
            renderPendingTherapyList(therapies, listContainer);
        }
    }

    function renderPendingTherapyCards(therapies, container) {
        therapies.forEach(function(therapy) {
            const priorityClass = therapy.priority === 'High' ? 'priority-high' :
                                 therapy.priority === 'Medium' ? 'priority-medium' : 'priority-low';

            const isPaid = therapy.payment_status === 'Paid';
            const paymentBadgeClass = isPaid ? 'badge badge-success' : 'badge badge-warning';
            const paymentBadgeIcon = isPaid ? 'fa-check-circle' : 'fa-clock-o';

            const card = $(`
                <div class="rehab-card" style="${!isPaid ? 'opacity: 0.8;' : ''}">
                    <div class="rehab-card-header">
                        <div>
                            <div class="rehab-card-title">${therapy.therapy_type || '-'}</div>
                            <div class="rehab-card-subtitle">Sessions: ${therapy.no_of_sessions || 'N/A'}</div>
                        </div>
                        ${therapy.priority ? `<span class="priority-badge ${priorityClass}">${therapy.priority}</span>` : ''}
                    </div>
                    <div class="rehab-card-body">
                        <div class="rehab-card-info">
                            <div class="info-row">
                                <i class="fa fa-user"></i>
                                <span class="info-label">Patient:</span>
                                <span class="info-value">${therapy.patient_name} (${therapy.patient})</span>
                            </div>
                            <div class="info-row">
                                <i class="fa fa-calendar"></i>
                                <span class="info-label">Encounter Date:</span>
                                <span class="info-value">${frappe.datetime.str_to_user(therapy.encounter_date)}</span>
                            </div>
                            ${therapy.practitioner ? `
                            <div class="info-row">
                                <i class="fa fa-user-md"></i>
                                <span class="info-label">Practitioner:</span>
                                <span class="info-value">${therapy.practitioner}</span>
                            </div>
                            ` : ''}
                            ${therapy.diagnosis ? `
                            <div class="info-row diagnosis-row">
                                <i class="fa fa-stethoscope"></i>
                                <span class="info-label">Diagnosis:</span>
                                <span class="info-value">${therapy.diagnosis}</span>
                            </div>
                            ` : ''}
                            <div class="info-row">
                                <i class="fa fa-credit-card"></i>
                                <span class="info-label">Payment:</span>
                                <span class="${paymentBadgeClass}" style="padding: 2px 8px; border-radius: 4px;">
                                    <i class="fa ${paymentBadgeIcon}"></i> ${therapy.payment_status}
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="rehab-card-footer">
                        <span class="status-badge status-pending">
                            <i class="fa fa-clock-o"></i> Pending
                        </span>
                        <div class="rehab-card-actions">
                            ${isPaid && therapy.custom_therapy_plan ? `
                                <button class="btn btn-primary btn-view-plan">
                                    <i class="fa fa-eye"></i> View Plan
                                </button>
                            ` : isPaid ? `
                                <button class="btn btn-warning">
                                    <i class="fa fa-exclamation-triangle"></i> Plan Not Created
                                </button>
                            ` : `
                                <button class="btn btn-secondary" disabled>
                                    <i class="fa fa-lock"></i> Awaiting Payment
                                </button>
                            `}
                        </div>
                    </div>
                </div>
            `);

            if (isPaid && therapy.custom_therapy_plan) {
                card.find('.btn-view-plan').on('click', function(e) {
                    e.stopPropagation();
                    frappe.set_route('Form', 'Therapy Plan', therapy.custom_therapy_plan);
                });
            }

            container.append(card);
        });
    }

    function renderPendingTherapyList(therapies, container) {
        let tableHtml = `
            <table class="rehab-list-table">
                <thead>
                    <tr>
                        <th>Therapy Type</th>
                        <th>Patient</th>
                        <th>Date</th>
                        <th>Diagnosis</th>
                        <th>Payment</th>
                        <th>Priority</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        therapies.forEach(function(therapy) {
            const priorityClass = therapy.priority === 'High' ? 'priority-high' :
                                 therapy.priority === 'Medium' ? 'priority-medium' : 'priority-low';
            const isPaid = therapy.payment_status === 'Paid';
            const paymentBadgeClass = isPaid ? 'badge badge-success' : 'badge badge-warning';

            tableHtml += `
                <tr style="${!isPaid ? 'opacity: 0.8;' : ''}">
                    <td><strong>${therapy.therapy_type || '-'}</strong><br><small>Sessions: ${therapy.no_of_sessions || 'N/A'}</small></td>
                    <td>${therapy.patient_name}<br><small>${therapy.patient}</small></td>
                    <td>${frappe.datetime.str_to_user(therapy.encounter_date)}</td>
                    <td>${therapy.diagnosis || '-'}</td>
                    <td><span class="${paymentBadgeClass}">${therapy.payment_status}</span></td>
                    <td>${therapy.priority ? `<span class="priority-badge ${priorityClass}">${therapy.priority}</span>` : '-'}</td>
                    <td>
                        <div class="rehab-list-actions">
                            ${isPaid && therapy.custom_therapy_plan ? `
                                <button class="btn btn-primary btn-sm btn-view-plan" data-therapy-plan="${therapy.custom_therapy_plan}">
                                    <i class="fa fa-eye"></i> View Plan
                                </button>
                            ` : isPaid ? `
                                <button class="btn btn-warning btn-sm" disabled>
                                    <i class="fa fa-exclamation-triangle"></i> No Plan
                                </button>
                            ` : `
                                <button class="btn btn-secondary btn-sm" disabled>
                                    <i class="fa fa-lock"></i> Awaiting Payment
                                </button>
                            `}
                        </div>
                    </td>
                </tr>
            `;
        });

        tableHtml += `
                </tbody>
            </table>
        `;

        container.html(tableHtml);

        container.find('.btn-view-plan').on('click', function(e) {
            e.stopPropagation();
            const therapyPlan = $(this).data('therapy-plan');
            frappe.set_route('Form', 'Therapy Plan', therapyPlan);
        });
    }

    function displayCompletedTherapies(therapies) {
        const cardContainer = page.main.find('#completed-rehab-container');
        const listContainer = page.main.find('#completed-rehab-list');

        cardContainer.empty();
        listContainer.empty();

        page.main.find('#completed-count').text(therapies.length);

        if (therapies.length === 0) {
            const emptyState = `
                <div class="empty-state">
                    <i class="fa fa-info-circle"></i>
                    <h4>No Completed Therapies</h4>
                    <p>No therapy plans have been completed for the selected date.</p>
                </div>
            `;
            cardContainer.html(emptyState);
            listContainer.html(emptyState);
            return;
        }

        if (currentView === 'card') {
            cardContainer.show();
            listContainer.hide();
            renderCompletedTherapyCards(therapies, cardContainer);
        } else {
            cardContainer.hide();
            listContainer.show();
            renderCompletedTherapyList(therapies, listContainer);
        }
    }

    function renderCompletedTherapyCards(therapies, container) {
        therapies.forEach(function(therapy) {
            const card = $(`
                <div class="rehab-card">
                    <div class="rehab-card-header">
                        <div>
                            <div class="rehab-card-title">${therapy.therapy_type || '-'}</div>
                            <div class="rehab-card-subtitle">Sessions: ${therapy.no_of_sessions || 'N/A'}</div>
                        </div>
                    </div>
                    <div class="rehab-card-body">
                        <div class="rehab-card-info">
                            <div class="info-row">
                                <i class="fa fa-user"></i>
                                <span class="info-label">Patient:</span>
                                <span class="info-value">${therapy.patient_name} (${therapy.patient})</span>
                            </div>
                            <div class="info-row">
                                <i class="fa fa-calendar"></i>
                                <span class="info-label">Encounter Date:</span>
                                <span class="info-value">${frappe.datetime.str_to_user(therapy.encounter_date)}</span>
                            </div>
                            ${therapy.practitioner ? `
                            <div class="info-row">
                                <i class="fa fa-user-md"></i>
                                <span class="info-label">Practitioner:</span>
                                <span class="info-value">${therapy.practitioner}</span>
                            </div>
                            ` : ''}
                            ${therapy.diagnosis ? `
                            <div class="info-row diagnosis-row">
                                <i class="fa fa-stethoscope"></i>
                                <span class="info-label">Diagnosis:</span>
                                <span class="info-value">${therapy.diagnosis}</span>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="rehab-card-footer">
                        <span class="status-badge status-completed">
                            <i class="fa fa-check-circle"></i> Completed
                        </span>
                        <div class="rehab-card-actions">
                            ${therapy.custom_therapy_plan ? `
                            <button class="btn btn-primary btn-view-plan">
                                <i class="fa fa-eye"></i> View Plan
                            </button>
                            <button class="btn btn-secondary btn-print-plan">
                                <i class="fa fa-print"></i> Print
                            </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `);

            if (therapy.custom_therapy_plan) {
                card.find('.btn-view-plan').on('click', function(e) {
                    e.stopPropagation();
                    frappe.set_route('Form', 'Therapy Plan', therapy.custom_therapy_plan);
                });

                card.find('.btn-print-plan').on('click', function(e) {
                    e.stopPropagation();
                    showPrintDialog(therapy.custom_therapy_plan);
                });
            }

            container.append(card);
        });
    }

    function renderCompletedTherapyList(therapies, container) {
        let tableHtml = `
            <table class="rehab-list-table">
                <thead>
                    <tr>
                        <th>Therapy Type</th>
                        <th>Patient</th>
                        <th>Date</th>
                        <th>Practitioner</th>
                        <th>Diagnosis</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        therapies.forEach(function(therapy) {
            tableHtml += `
                <tr>
                    <td><strong>${therapy.therapy_type || '-'}</strong><br><small>Sessions: ${therapy.no_of_sessions || 'N/A'}</small></td>
                    <td>${therapy.patient_name}<br><small>${therapy.patient}</small></td>
                    <td>${frappe.datetime.str_to_user(therapy.encounter_date)}</td>
                    <td>${therapy.practitioner || '-'}</td>
                    <td>${therapy.diagnosis || '-'}</td>
                    <td>
                        <div class="rehab-list-actions">
                            ${therapy.custom_therapy_plan ? `
                                <button class="btn btn-primary btn-sm btn-view-plan" data-therapy-plan="${therapy.custom_therapy_plan}">
                                    <i class="fa fa-eye"></i> View
                                </button>
                                <button class="btn btn-secondary btn-sm btn-print-plan" data-therapy-plan="${therapy.custom_therapy_plan}">
                                    <i class="fa fa-print"></i> Print
                                </button>
                            ` : '-'}
                        </div>
                    </td>
                </tr>
            `;
        });

        tableHtml += `
                </tbody>
            </table>
        `;

        container.html(tableHtml);

        container.find('.btn-view-plan').on('click', function(e) {
            e.stopPropagation();
            const therapyPlan = $(this).data('therapy-plan');
            frappe.set_route('Form', 'Therapy Plan', therapyPlan);
        });

        container.find('.btn-print-plan').on('click', function(e) {
            e.stopPropagation();
            const therapyPlan = $(this).data('therapy-plan');
            showPrintDialog(therapyPlan);
        });
    }

    function showPrintDialog(therapy_plan_name) {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_print_formats',
            args: {
                doctype: 'Therapy Plan'
            },
            callback: function(r) {
                const print_formats = r.message || [];

                if (print_formats.length === 0) {
                    frappe.utils.print('Therapy Plan', therapy_plan_name);
                    return;
                }

                const dialog = new frappe.ui.Dialog({
                    title: __('Select Print Format'),
                    fields: [
                        {
                            fieldtype: 'Select',
                            fieldname: 'print_format',
                            label: 'Print Format',
                            options: print_formats.map(pf => pf.name),
                            default: 'Standard',
                            reqd: 1
                        }
                    ],
                    primary_action_label: __('Print'),
                    primary_action: function(values) {
                        dialog.hide();
                        printTherapyPlan(therapy_plan_name, values.print_format);
                    }
                });

                dialog.show();
            }
        });
    }

    function printTherapyPlan(therapy_plan_name, print_format) {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_print_content',
            args: {
                doctype: 'Therapy Plan',
                docname: therapy_plan_name,
                print_format: print_format
            },
            callback: function(r) {
                if (r.message && r.message.html) {
                    const printWindow = window.open('', '_blank');
                    printWindow.document.write(r.message.html);
                    printWindow.document.close();
                    setTimeout(() => {
                        printWindow.print();
                    }, 500);
                } else {
                    frappe.utils.print('Therapy Plan', therapy_plan_name, print_format);
                }
            },
            error: function() {
                frappe.utils.print('Therapy Plan', therapy_plan_name, print_format);
            }
        });
    }

    function acceptTherapyRequest(therapy) {
        // Direct-sourced rows (no Patient Encounter behind them - see
        // create_therapy_request() in rehab_portal.py) are invoiced
        // immediately on creation now, so they normally skip Requested
        // Therapies entirely. Left in place as a fallback for any direct
        // Therapy Plan that ends up uninvoiced.
        const isDirect = therapy.source === 'direct';

        frappe.confirm(
            __('Accept this therapy request and create invoice for {0}?', [therapy.patient_name]),
            function() {
                frappe.call({
                    method: isDirect
                        ? 'healthcare.healthcare.page.rehab_portal.rehab_portal.accept_direct_therapy_request'
                        : 'healthcare.healthcare.page.rehab_portal.rehab_portal.accept_therapy_request',
                    args: isDirect
                        ? { therapy_plan_name: therapy.therapy_plan_name }
                        : {
                              therapy_id: therapy.therapy_id,
                              patient_id: therapy.patient,
                              encounter_id: therapy.encounter_id,
                              therapy_type: therapy.therapy_type
                          },
                    freeze: true,
                    freeze_message: __('Creating invoice...'),
                    callback: function(r) {
                        if (r.message && r.message.status === 'Success') {
                            frappe.show_alert({
                                message: __('Therapy request accepted! Invoice {0} and Therapy Plan {1} created. Patient needs to pay before therapy can begin.',
                                    [r.message.invoice_name, r.message.therapy_plan_name]),
                                indicator: 'green'
                            }, 10);

                            loadTherapies();
                        }
                    },
                    error: function(r) {
                        frappe.show_alert({
                            message: r.message || __('Error accepting therapy request'),
                            indicator: 'red'
                        }, 10);
                    }
                });
            }
        );
    }

    loadTherapies();
};
//# sourceURL=rehab_portal.js