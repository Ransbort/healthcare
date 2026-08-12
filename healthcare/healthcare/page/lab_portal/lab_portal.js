frappe.pages['lab-portal'].on_page_load = function(wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Laboratory Portal',
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
	    if (data.department !== 'laboratory') return;
	
	    playNotification();
	    frappe.show_alert({
	        message: data.message,
	        indicator: 'blue'
	    }, 6);
	
	    loadLabs();
	});

    const style = `
        <style>
            .lab-wrapper {
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
            .lab-toolbar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding-bottom: 16px;
                margin-bottom: 16px;
                border-bottom: 1px solid #e9ecef;
            }

            .lab-toolbar-title {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .lab-toolbar-title .icon-badge {
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

            .lab-toolbar-title h4 {
                margin: 0;
                font-size: 1.2rem;
                font-weight: 700;
                color: #1a1a2e;
                line-height: 1.3;
            }

            .lab-toolbar-title .lab-toolbar-subtitle {
                font-size: 0.83rem;
                color: #868e96;
                margin-top: 1px;
            }

            .lab-toolbar-actions {
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
            .lab-wrapper .search-section {
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

            .lab-wrapper .search-input-group label {
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
            .lab-wrapper .last-updated {
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

            .lab-cards-container {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                gap: 20px;
            }

            .lab-list-container {
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }

            .lab-list-table {
                width: 100%;
                border-collapse: collapse;
            }

            .lab-list-table thead {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .lab-list-table th {
                padding: 12px;
                text-align: left;
                font-weight: 600;
                font-size: 0.9rem;
            }

            .lab-list-table tbody tr {
                border-bottom: 1px solid #e9ecef;
                transition: background 0.2s ease;
                cursor: pointer;
            }

            .lab-list-table tbody tr:hover {
                background: #f8f9fa;
            }

            .lab-list-table td {
                padding: 12px;
                font-size: 0.9rem;
            }

            .lab-list-actions {
                display: flex;
                gap: 5px;
            }

            .lab-list-actions .btn {
                padding: 4px 8px;
                font-size: 0.85rem;
            }

            .lab-card {
                background: white;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                padding: 20px;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }

            .lab-card:hover {
                border-color: var(--primary-color);
                box-shadow: 0 4px 16px rgba(102, 126, 234, 0.2);
                transform: translateY(-2px);
            }

            .lab-card-header {
                display: flex;
                justify-content: space-between;
                align-items: start;
                margin-bottom: 15px;
                padding-bottom: 15px;
                border-bottom: 1px solid #e9ecef;
            }

            .lab-card-title {
                font-size: 1.1rem;
                font-weight: 700;
                color: #2c3e50;
                margin-bottom: 4px;
            }

            .lab-card-subtitle {
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

            .lab-card-body {
                margin-bottom: 15px;
            }

            .lab-card-info {
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

            .lab-card-footer {
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

            .lab-card-actions {
                display: flex;
                gap: 8px;
            }

            .btn-open-lab {
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
                .lab-wrapper {
                    padding: 15px;
                }

                .lab-toolbar {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 12px;
                }

                .lab-toolbar-actions {
                    width: 100%;
                    justify-content: flex-end;
                }

                .search-input-group {
                    grid-template-columns: 1fr;
                }

                .lab-cards-container {
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

                .lab-list-table {
                    font-size: 0.85rem;
                }
            }
        </style>
    `;

    $(style).appendTo(page.main);

    let html = `
        <div class="lab-wrapper">
            <div class="sticky-header">
                <div class="lab-toolbar">
                    <div class="lab-toolbar-title">
                        <div class="icon-badge"><i class="fa fa-flask"></i></div>
                        <div>
                            <h4>Laboratory Portal</h4>
                            <div class="lab-toolbar-subtitle">Search and manage lab requests</div>
                        </div>
                    </div>
                    <div class="lab-toolbar-actions">
                        <button class="btn-icon" id="refresh-btn" title="Refresh">
                            <i class="fa fa-refresh"></i>
                        </button>
                        <button class="btn-new-request" id="new-lab-request-btn">
                            <i class="fa fa-plus"></i> New Lab Request
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
                        <i class="fa fa-paper-plane"></i> Requested Labs
                        <span class="badge badge-info" id="requested-count">0</span>
                    </button>
                    <button class="tab-btn" data-tab="pending">
                        <i class="fa fa-clock-o"></i> Pending Labs
                        <span class="badge badge-warning" id="pending-count">0</span>
                    </button>
                    <button class="tab-btn" data-tab="completed">
                        <i class="fa fa-check-circle"></i> Completed Labs
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
                    <div class="lab-cards-container" id="requested-labs-container"></div>
                    <div class="lab-list-container" id="requested-labs-list" style="display: none;"></div>
                </div>
            </div>

            <div class="tab-content" id="pending-tab">
                <div class="scrollable-content">
                    <div class="lab-cards-container" id="pending-labs-container"></div>
                    <div class="lab-list-container" id="pending-labs-list" style="display: none;"></div>
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
                    <div class="lab-cards-container" id="completed-labs-container"></div>
                    <div class="lab-list-container" id="completed-labs-list" style="display: none;"></div>
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
            displayRequestedLabs(window.lastRequestedLabs || []);
        } else if (activeTab === 'pending') {
            displayPendingLabs(window.lastPendingLabs || []);
        } else if (activeTab === 'completed') {
            displayCompletedLabs(window.lastCompletedLabs || []);
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
        loadLabs();
    });

    page.main.find('#clear-btn').on('click', function() {
        search_patient_field.set_value('');
        search_date_field.set_value('');
        search_encounter_field.set_value('');
        loadLabs();
    });

    // Toolbar refresh icon: reloads with current filters, gives a quick
    // spin for feedback (distinct from "Clear", which also resets filters).
    page.main.find('#refresh-btn').on('click', function() {
        const $icon = $(this).find('i');
        $icon.addClass('fa-spin');
        loadLabs();
        setTimeout(() => $icon.removeClass('fa-spin'), 600);
    });

    page.main.find('#filter-completed-btn').on('click', function() {
        loadCompletedLabs(
            search_patient_field.get_value(),
            search_encounter_field.get_value(),
            completed_date_field.get_value()
        );
    });

    page.main.find('#new-lab-request-btn').on('click', function() {
        openNewLabRequestDialog();
    });

    // Direct lab requests: no Patient Encounter / Lab Prescription involved.
    // Creates a standalone Draft Lab Test via create_lab_request(), which
    // then shows up in the Requested tab alongside encounter-sourced rows
    // (get_requested_labs merges both sources - see lab_portal.py).
    function openNewLabRequestDialog() {
        frappe.call({
            method: 'healthcare.healthcare.page.lab_portal.lab_portal.get_lab_test_templates',
            callback: function(r) {
                const templates = r.message || [];

                const dialog = new frappe.ui.Dialog({
                    title: __('New Lab Request'),
                    fields: [
                        {
                            fieldtype: 'Link',
                            fieldname: 'patient',
                            options: 'Patient',
                            label: 'Patient',
                            reqd: 1
                        },
                        {
                            fieldtype: 'Select',
                            fieldname: 'lab_test_code',
                            label: 'Lab Test',
                            options: templates.map(t => ({
                                label: `${t.lab_test_name || t.name} (${format_currency(t.rate)})`,
                                value: t.name
                            })),
                            reqd: 1
                        },
                        {
                            fieldtype: 'Section Break'
                        },
                        {
                            fieldtype: 'Small Text',
                            fieldname: 'lab_test_comment',
                            label: 'Comment (Optional)'
                        }
                    ],
                    primary_action_label: __('Create Request'),
                    primary_action: function(values) {
                        frappe.call({
                            method: 'healthcare.healthcare.page.lab_portal.lab_portal.create_lab_request',
                            args: {
                                patient: values.patient,
                                lab_test_code: values.lab_test_code,
                                lab_test_comment: values.lab_test_comment || null
                            },
                            freeze: true,
                            freeze_message: __('Creating lab request...'),
                            callback: function(r) {
                                if (r.message && r.message.status === 'Success') {
                                    frappe.show_alert({
                                        message: __('Lab request created.'),
                                        indicator: 'green'
                                    }, 6);
                                    dialog.hide();
                                    loadLabs();
                                }
                            },
                            error: function(r) {
                                frappe.show_alert({
                                    message: r.message || __('Error creating lab request'),
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

    function loadLabs() {
        const patient = search_patient_field.get_value();
        const encounter = search_encounter_field.get_value();
        const date = search_date_field.get_value();

        pendingLoads = 3;
        loadRequestedLabs(patient, encounter, date);
        loadPendingLabs(patient, encounter, date);
        loadCompletedLabs(patient, encounter, completed_date_field.get_value());
    }

    function loadRequestedLabs(patient, encounter, date) {
        frappe.call({
            method: 'healthcare.healthcare.page.lab_portal.lab_portal.get_requested_labs',
            args: {
                search_patient: patient || null,
                search_encounter: encounter || null,
                search_date: date || null
            },
            callback: function(r) {
                const labs = r.message || [];
                window.lastRequestedLabs = labs;
                displayRequestedLabs(labs);
                markLoadDone();
            }
        });
    }

    function loadPendingLabs(patient, encounter, date) {
        frappe.call({
            method: 'healthcare.healthcare.page.lab_portal.lab_portal.get_pending_labs',
            args: {
                search_patient: patient || null,
                search_encounter: encounter || null,
                search_date: date || null
            },
            freeze: true,
            freeze_message: __('Loading pending labs...'),
            callback: function(r) {
                const labs = r.message || [];
                window.lastPendingLabs = labs;
                displayPendingLabs(labs);
                markLoadDone();
            }
        });
    }

    function loadCompletedLabs(patient, encounter, date) {
        frappe.call({
            method: 'healthcare.healthcare.page.lab_portal.lab_portal.get_completed_labs',
            args: {
                search_patient: patient || null,
                search_encounter: encounter || null,
                filter_date: date || null
            },
            callback: function(r) {
                const labs = r.message || [];
                window.lastCompletedLabs = labs;
                displayCompletedLabs(labs);
                markLoadDone();
            }
        });
    }

    function displayRequestedLabs(labs) {
        const cardContainer = page.main.find('#requested-labs-container');
        const listContainer = page.main.find('#requested-labs-list');
        
        cardContainer.empty();
        listContainer.empty();

        page.main.find('#requested-count').text(labs.length);

        if (labs.length === 0) {
            const emptyState = `
                <div class="empty-state">
                    <i class="fa fa-inbox"></i>
                    <h4>No Requested Labs</h4>
                    <p>All lab requests have been accepted or there are no new requests.</p>
                </div>
            `;
            cardContainer.html(emptyState);
            listContainer.html(emptyState);
            return;
        }

        if (currentView === 'card') {
            cardContainer.show();
            listContainer.hide();
            renderRequestedLabCards(labs, cardContainer);
        } else {
            cardContainer.hide();
            listContainer.show();
            renderRequestedLabList(labs, listContainer);
        }
    }

    function renderRequestedLabCards(labs, container) {
        labs.forEach(function(lab) {
            const priorityClass = lab.priority === 'High' ? 'priority-high' : 
                                 lab.priority === 'Medium' ? 'priority-medium' : 'priority-low';
            
            const card = $(`
                <div class="lab-card">
                    <div class="lab-card-header">
                        <div>
                            <div class="lab-card-title">${lab.lab_test_name || lab.lab_test_code}</div>
                            <div class="lab-card-subtitle">${lab.lab_test_code}</div>
                        </div>
                        ${lab.priority ? `<span class="priority-badge ${priorityClass}">${lab.priority}</span>` : ''}
                    </div>
                    <div class="lab-card-body">
                        <div class="lab-card-info">
                            <div class="info-row">
                                <i class="fa fa-user"></i>
                                <span class="info-label">Patient:</span>
                                <span class="info-value">${lab.patient_name} (${lab.patient})</span>
                            </div>
                            <div class="info-row">
                                <i class="fa fa-calendar"></i>
                                <span class="info-label">Encounter Date:</span>
                                <span class="info-value">${frappe.datetime.str_to_user(lab.encounter_date)}</span>
                            </div>
                            ${lab.practitioner ? `
                            <div class="info-row">
                                <i class="fa fa-user-md"></i>
                                <span class="info-label">Practitioner:</span>
                                <span class="info-value">${lab.practitioner}</span>
                            </div>
                            ` : ''}
                            ${lab.diagnosis ? `
                            <div class="info-row diagnosis-row">
                                <i class="fa fa-stethoscope"></i>
                                <span class="info-label">Diagnosis:</span>
                                <span class="info-value">${lab.diagnosis}</span>
                            </div>
                            ` : ''}
                            ${lab.lab_test_comment ? `
                            <div class="info-row">
                                <i class="fa fa-comment"></i>
                                <span class="info-label">Note:</span>
                                <span class="info-value">${lab.lab_test_comment}</span>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="lab-card-footer">
                        <span class="status-badge status-requested">
                            <i class="fa fa-paper-plane"></i> Requested
                        </span>
                        <div class="lab-card-actions">
                            <button class="btn btn-success btn-accept-lab">
                                <i class="fa fa-check"></i> Accept & Invoice
                            </button>
                        </div>
                    </div>
                </div>
            `);

            card.find('.btn-accept-lab').on('click', function(e) {
                e.stopPropagation();
                acceptLabRequest(lab);
            });

            container.append(card);
        });
    }

    function renderRequestedLabList(labs, container) {
        let tableHtml = `
            <table class="lab-list-table">
                <thead>
                    <tr>
                        <th>Test Name</th>
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

        labs.forEach(function(lab, index) {
            const priorityClass = lab.priority === 'High' ? 'priority-high' : 
                                 lab.priority === 'Medium' ? 'priority-medium' : 'priority-low';
            
            tableHtml += `
                <tr>
                    <td><strong>${lab.lab_test_name || lab.lab_test_code}</strong><br><small>${lab.lab_test_code}</small></td>
                    <td>${lab.patient_name}<br><small>${lab.patient}</small></td>
                    <td>${frappe.datetime.str_to_user(lab.encounter_date)}</td>
                    <td>${lab.practitioner || '-'}</td>
                    <td>${lab.diagnosis || '-'}</td>
                    <td>${lab.priority ? `<span class="priority-badge ${priorityClass}">${lab.priority}</span>` : '-'}</td>
                    <td>
                        <div class="lab-list-actions">
                            <button class="btn btn-success btn-sm btn-accept-lab" data-idx="${index}">
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

        // Keyed by row index, not lab.prescription_id - direct-sourced rows
        // (see lab_portal.py get_requested_labs) all have prescription_id
        // null, which would collide if looked up by that field whenever
        // more than one direct request is showing at once.
        container.find('.btn-accept-lab').on('click', function(e) {
            e.stopPropagation();
            const idx = $(this).data('idx');
            const lab = labs[idx];
            if (lab) {
                acceptLabRequest(lab);
            }
        });
    }

    function displayPendingLabs(labs) {
        const cardContainer = page.main.find('#pending-labs-container');
        const listContainer = page.main.find('#pending-labs-list');
        
        cardContainer.empty();
        listContainer.empty();

        page.main.find('#pending-count').text(labs.length);

        if (labs.length === 0) {
            const emptyState = `
                <div class="empty-state">
                    <i class="fa fa-check-circle"></i>
                    <h4>No Pending Labs</h4>
                    <p>All lab tests have been completed or there are no pending tests.</p>
                </div>
            `;
            cardContainer.html(emptyState);
            listContainer.html(emptyState);
            return;
        }

        if (currentView === 'card') {
            cardContainer.show();
            listContainer.hide();
            renderPendingLabCards(labs, cardContainer);
        } else {
            cardContainer.hide();
            listContainer.show();
            renderPendingLabList(labs, listContainer);
        }
    }

    function renderPendingLabCards(labs, container) {
        labs.forEach(function(lab) {
            const priorityClass = lab.priority === 'High' ? 'priority-high' : 
                                 lab.priority === 'Medium' ? 'priority-medium' : 'priority-low';
            
            const isPaid = lab.payment_status === 'Paid';
            const paymentBadgeClass = isPaid ? 'badge badge-success' : 'badge badge-warning';
            const paymentBadgeIcon = isPaid ? 'fa-check-circle' : 'fa-clock-o';
            
            const card = $(`
                <div class="lab-card" style="${!isPaid ? 'opacity: 0.8;' : ''}">
                    <div class="lab-card-header">
                        <div>
                            <div class="lab-card-title">${lab.lab_test_name || lab.lab_test_code}</div>
                            <div class="lab-card-subtitle">${lab.lab_test_code}</div>
                        </div>
                        ${lab.priority ? `<span class="priority-badge ${priorityClass}">${lab.priority}</span>` : ''}
                    </div>
                    <div class="lab-card-body">
                        <div class="lab-card-info">
                            <div class="info-row">
                                <i class="fa fa-user"></i>
                                <span class="info-label">Patient:</span>
                                <span class="info-value">${lab.patient_name} (${lab.patient})</span>
                            </div>
                            <div class="info-row">
                                <i class="fa fa-calendar"></i>
                                <span class="info-label">Encounter Date:</span>
                                <span class="info-value">${frappe.datetime.str_to_user(lab.encounter_date)}</span>
                            </div>
                            ${lab.practitioner ? `
                            <div class="info-row">
                                <i class="fa fa-user-md"></i>
                                <span class="info-label">Practitioner:</span>
                                <span class="info-value">${lab.practitioner}</span>
                            </div>
                            ` : ''}
                            ${lab.diagnosis ? `
                            <div class="info-row diagnosis-row">
                                <i class="fa fa-stethoscope"></i>
                                <span class="info-label">Diagnosis:</span>
                                <span class="info-value">${lab.diagnosis}</span>
                            </div>
                            ` : ''}
                            <div class="info-row">
                                <i class="fa fa-credit-card"></i>
                                <span class="info-label">Payment:</span>
                                <span class="${paymentBadgeClass}" style="padding: 2px 8px; border-radius: 4px;">
                                    <i class="fa ${paymentBadgeIcon}"></i> ${lab.payment_status}
                                </span>
                            </div>
                            ${lab.lab_test_comment ? `
                            <div class="info-row">
                                <i class="fa fa-comment"></i>
                                <span class="info-label">Note:</span>
                                <span class="info-value">${lab.lab_test_comment}</span>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="lab-card-footer">
                        <span class="status-badge status-pending">
                            <i class="fa fa-clock-o"></i> Pending
                        </span>
                        <div class="lab-card-actions">
                            ${isPaid ? `
                                <button class="btn btn-primary btn-open-lab">
                                    <i class="fa fa-flask"></i> Open Lab Test
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

            if (isPaid) {
                card.find('.btn-open-lab').on('click', function(e) {
                    e.stopPropagation();
                    openLabTest(lab);
                });
            }

            container.append(card);
        });
    }

    function renderPendingLabList(labs, container) {
        let tableHtml = `
            <table class="lab-list-table">
                <thead>
                    <tr>
                        <th>Test Name</th>
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

        labs.forEach(function(lab) {
            const priorityClass = lab.priority === 'High' ? 'priority-high' : 
                                 lab.priority === 'Medium' ? 'priority-medium' : 'priority-low';
            const isPaid = lab.payment_status === 'Paid';
            const paymentBadgeClass = isPaid ? 'badge badge-success' : 'badge badge-warning';
            
            tableHtml += `
                <tr style="${!isPaid ? 'opacity: 0.8;' : ''}">
                    <td><strong>${lab.lab_test_name || lab.lab_test_code}</strong><br><small>${lab.lab_test_code}</small></td>
                    <td>${lab.patient_name}<br><small>${lab.patient}</small></td>
                    <td>${frappe.datetime.str_to_user(lab.encounter_date)}</td>
                    <td>${lab.diagnosis || '-'}</td>
                    <td><span class="${paymentBadgeClass}">${lab.payment_status}</span></td>
                    <td>${lab.priority ? `<span class="priority-badge ${priorityClass}">${lab.priority}</span>` : '-'}</td>
                    <td>
                        <div class="lab-list-actions">
                            ${isPaid ? `
                                <button class="btn btn-primary btn-sm btn-open-lab" data-lab-test="${lab.custom_lab_test}">
                                    <i class="fa fa-flask"></i> Open
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

        container.find('.btn-open-lab').on('click', function(e) {
            e.stopPropagation();
            const labTestName = $(this).data('lab-test');
            const lab = labs.find(l => l.custom_lab_test === labTestName);
            if (lab) {
                openLabTest(lab);
            }
        });
    }

    function displayCompletedLabs(labs) {
        const cardContainer = page.main.find('#completed-labs-container');
        const listContainer = page.main.find('#completed-labs-list');
        
        cardContainer.empty();
        listContainer.empty();

        page.main.find('#completed-count').text(labs.length);

        if (labs.length === 0) {
            const emptyState = `
                <div class="empty-state">
                    <i class="fa fa-info-circle"></i>
                    <h4>No Completed Labs</h4>
                    <p>No lab test results have been entered for the selected date.</p>
                </div>
            `;
            cardContainer.html(emptyState);
            listContainer.html(emptyState);
            return;
        }

        if (currentView === 'card') {
            cardContainer.show();
            listContainer.hide();
            renderCompletedLabCards(labs, cardContainer);
        } else {
            cardContainer.hide();
            listContainer.show();
            renderCompletedLabList(labs, listContainer);
        }
    }

    function renderCompletedLabCards(labs, container) {
        labs.forEach(function(lab) {
            const card = $(`
                <div class="lab-card">
                    <div class="lab-card-header">
                        <div>
                            <div class="lab-card-title">${lab.lab_test_name || lab.lab_test_code}</div>
                            <div class="lab-card-subtitle">${lab.lab_test_code}</div>
                        </div>
                    </div>
                    <div class="lab-card-body">
                        <div class="lab-card-info">
                            <div class="info-row">
                                <i class="fa fa-user"></i>
                                <span class="info-label">Patient:</span>
                                <span class="info-value">${lab.patient_name} (${lab.patient})</span>
                            </div>
                            <div class="info-row">
                                <i class="fa fa-calendar"></i>
                                <span class="info-label">Encounter Date:</span>
                                <span class="info-value">${frappe.datetime.str_to_user(lab.encounter_date)}</span>
                            </div>
                            ${lab.practitioner ? `
                            <div class="info-row">
                                <i class="fa fa-user-md"></i>
                                <span class="info-label">Practitioner:</span>
                                <span class="info-value">${lab.practitioner}</span>
                            </div>
                            ` : ''}
                            ${lab.diagnosis ? `
                            <div class="info-row diagnosis-row">
                                <i class="fa fa-stethoscope"></i>
                                <span class="info-label">Diagnosis:</span>
                                <span class="info-value">${lab.diagnosis}</span>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="lab-card-footer">
                        <span class="status-badge status-completed">
                            <i class="fa fa-check-circle"></i> Completed
                        </span>
                        <div class="lab-card-actions">
                            ${lab.custom_lab_test ? `
                            <button class="btn btn-primary btn-view-lab">
                                <i class="fa fa-eye"></i> View Results
                            </button>
                            <button class="btn btn-secondary btn-print-lab">
                                <i class="fa fa-print"></i> Print
                            </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `);

            if (lab.custom_lab_test) {
                card.find('.btn-view-lab').on('click', function(e) {
                    e.stopPropagation();
                    frappe.set_route('Form', 'Lab Test', lab.custom_lab_test);
                });

                card.find('.btn-print-lab').on('click', function(e) {
                    e.stopPropagation();
                    showPrintDialog(lab.custom_lab_test);
                });
            }

            container.append(card);
        });
    }

    function renderCompletedLabList(labs, container) {
        let tableHtml = `
            <table class="lab-list-table">
                <thead>
                    <tr>
                        <th>Test Name</th>
                        <th>Patient</th>
                        <th>Date</th>
                        <th>Practitioner</th>
                        <th>Diagnosis</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        labs.forEach(function(lab) {
            tableHtml += `
                <tr>
                    <td><strong>${lab.lab_test_name || lab.lab_test_code}</strong><br><small>${lab.lab_test_code}</small></td>
                    <td>${lab.patient_name}<br><small>${lab.patient}</small></td>
                    <td>${frappe.datetime.str_to_user(lab.encounter_date)}</td>
                    <td>${lab.practitioner || '-'}</td>
                    <td>${lab.diagnosis || '-'}</td>
                    <td>
                        <div class="lab-list-actions">
                            ${lab.custom_lab_test ? `
                                <button class="btn btn-primary btn-sm btn-view-lab" data-lab-test="${lab.custom_lab_test}">
                                    <i class="fa fa-eye"></i> View
                                </button>
                                <button class="btn btn-secondary btn-sm btn-print-lab" data-lab-test="${lab.custom_lab_test}">
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

        container.find('.btn-view-lab').on('click', function(e) {
            e.stopPropagation();
            const labTestName = $(this).data('lab-test');
            frappe.set_route('Form', 'Lab Test', labTestName);
        });

        container.find('.btn-print-lab').on('click', function(e) {
            e.stopPropagation();
            const labTestName = $(this).data('lab-test');
            showPrintDialog(labTestName);
        });
    }

    function showPrintDialog(lab_test_name) {
        frappe.call({
            method: 'healthcare.healthcare.page.lab_portal.lab_portal.get_print_formats',
            args: {
                doctype: 'Lab Test'
            },
            callback: function(r) {
                const print_formats = r.message || [];
                
                if (print_formats.length === 0) {
                    frappe.utils.print('Lab Test', lab_test_name);
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
                        printLabTest(lab_test_name, values.print_format);
                    }
                });

                dialog.show();
            }
        });
    }

    function printLabTest(lab_test_name, print_format) {
        frappe.call({
            method: 'healthcare.healthcare.page.lab_portal.lab_portal.get_print_content',
            args: {
                doctype: 'Lab Test',
                docname: lab_test_name,
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
                    frappe.utils.print('Lab Test', lab_test_name, print_format);
                }
            },
            error: function() {
                frappe.utils.print('Lab Test', lab_test_name, print_format);
            }
        });
    }

    function acceptLabRequest(lab) {
        // Direct-sourced rows (no Patient Encounter behind them - see
        // create_lab_request() in lab_portal.py) are invoiced immediately
        // on creation now, so they normally skip Requested Labs entirely
        // and this branch shouldn't fire in practice. Left in place as a
        // fallback for any direct Lab Test that ends up uninvoiced.
        const isDirect = lab.source === 'direct';

        frappe.confirm(
            __('Accept this lab request and create invoice for {0}?', [lab.patient_name]),
            function() {
                frappe.call({
                    method: isDirect
                        ? 'healthcare.healthcare.page.lab_portal.lab_portal.accept_direct_lab_request'
                        : 'healthcare.healthcare.page.lab_portal.lab_portal.accept_lab_request',
                    args: isDirect
                        ? { lab_test_name: lab.lab_test_name_id }
                        : {
                              prescription_id: lab.prescription_id,
                              patient_id: lab.patient,
                              encounter_id: lab.encounter_id,
                              lab_test_code: lab.lab_test_code
                          },
                    freeze: true,
                    freeze_message: __('Creating invoice...'),
                    callback: function(r) {
                        if (r.message && r.message.status === 'Success') {
                            frappe.show_alert({
                                message: __('Lab request accepted! Invoice {0} and Lab Test {1} created. Patient needs to pay before lab work can begin.', 
                                    [r.message.invoice_name, r.message.lab_test_name]),
                                indicator: 'green'
                            }, 10);

                            loadLabs();
                        }
                    },
                    error: function(r) {
                        frappe.show_alert({
                            message: r.message || __('Error accepting lab request'),
                            indicator: 'red'
                        }, 10);
                    }
                });
            }
        );
    }

    function openLabTest(lab) {
        if (lab.custom_lab_test) {
            frappe.set_route('Form', 'Lab Test', lab.custom_lab_test);
        } else {
            frappe.show_alert({
                message: __('Lab Test document not found. Please contact administrator.'),
                indicator: 'red'
            });
        }
    }

    loadLabs();
};
//# sourceURL=lab_portal.js