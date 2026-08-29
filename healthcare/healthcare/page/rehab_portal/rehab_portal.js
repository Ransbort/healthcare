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
                flex-wrap: wrap;
                gap: 15px;
                margin-bottom: 20px;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 8px;
                align-items: end;
            }

            .completed-filters .frappe-control {
                flex: 0 0 200px;
            }

            .completed-filters .form-group {
                margin-bottom: 0;
            }

            .completed-filters .btn {
                flex-shrink: 0;
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

            /* --- Stat tiles (Spa Portal's summary strip, adapted) --- */
            .rehab-stats-bar {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 12px;
                margin-bottom: 16px;
            }

            .rehab-stat-tile {
                background: white;
                border: 1px solid #e9ecef;
                border-radius: 10px;
                padding: 14px 16px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            }

            .rehab-stat-tile .stat-label {
                font-size: 0.78rem;
                color: #868e96;
                font-weight: 500;
                margin-bottom: 4px;
            }

            .rehab-stat-tile .stat-value {
                font-size: 1.35rem;
                font-weight: 700;
                color: #2c3e50;
            }

            .rehab-stat-tile.stat-orange .stat-value { color: #fd7e14; }
            .rehab-stat-tile.stat-green .stat-value { color: #28a745; }
            .rehab-stat-tile.stat-blue .stat-value { color: #667eea; }

            /* --- Session progress bar on Pending cards --- */
            .session-progress { margin-top: 8px; }

            .session-progress-label {
                display: flex;
                justify-content: space-between;
                font-size: 0.78rem;
                color: #6c757d;
                margin-bottom: 4px;
            }

            .session-progress-bar {
                height: 6px;
                background: #e9ecef;
                border-radius: 3px;
                overflow: hidden;
            }

            .session-progress-fill {
                height: 100%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 3px;
            }

            /* --- Schedule tab --- */
            .schedule-toolbar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
            }

            .sched-view-toggle {
                display: flex;
                gap: 0;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                overflow: hidden;
                width: fit-content;
            }

            .sched-view-btn {
                padding: 8px 20px;
                background: #f8f9fa;
                border: none;
                color: #6c757d;
                font-weight: 600;
                font-size: 0.9rem;
                cursor: pointer;
                transition: all 0.3s ease;
            }

            .sched-view-btn:hover { background: #e9ecef; }
            .sched-view-btn.active {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .sched-calendar { margin-top: 10px; }

            .sched-cal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }

            .sched-cal-header h5 { margin: 0; font-weight: 600; color: #495057; }

            .sched-cal-nav-btn {
                background: #f8f9fa; border: 1px solid #d1d8dd; border-radius: 4px;
                padding: 6px 12px; cursor: pointer; font-weight: 600; color: #495057;
            }
            .sched-cal-nav-btn:hover { background: #e9ecef; }

            .sched-cal-grid {
                display: grid;
                grid-template-columns: repeat(7, 1fr);
                border: 1px solid #d1d8dd;
                border-radius: 8px;
                overflow: hidden;
            }

            .sched-cal-day-header {
                background: #f8f9fa;
                color: #495057;
                padding: 10px 5px;
                text-align: center;
                font-weight: 600;
                font-size: 0.85rem;
                border-bottom: 1px solid #d1d8dd;
            }

            .sched-cal-day {
                min-height: 100px;
                padding: 5px;
                border: 1px solid #e9ecef;
                background: white;
                vertical-align: top;
                font-size: 0.8rem;
            }

            .sched-cal-day.other-month { background: #f8f9fa; color: #adb5bd; }
            .sched-cal-day.today { background: #eef2ff; }

            .sched-cal-day-num {
                font-weight: 600;
                font-size: 0.85rem;
                margin-bottom: 4px;
                color: #495057;
            }

            .sched-cal-day.other-month .sched-cal-day-num { color: #adb5bd; }
            .sched-cal-day.today .sched-cal-day-num { color: #667eea; }

            .sched-cal-event {
                background: #cfe2ff;
                color: #084298;
                padding: 2px 6px;
                border-radius: 4px;
                margin-bottom: 3px;
                font-size: 0.7rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                cursor: pointer;
            }

            .sched-cal-event:hover { opacity: 0.85; }
            .sched-cal-event.status-completed { background: #d4edda; color: #155724; }

            .assessment-score-row {
                display: grid;
                grid-template-columns: 1fr 120px;
                gap: 10px;
                align-items: center;
                padding: 6px 0;
                border-bottom: 1px solid #f1f3f5;
            }

            .assessment-history-row {
                display: flex;
                justify-content: space-between;
                padding: 8px 10px;
                border-bottom: 1px solid #f1f3f5;
                font-size: 0.88rem;
            }

            @media (max-width: 768px) {
                .rehab-stats-bar { grid-template-columns: 1fr 1fr; }
                .schedule-toolbar { flex-direction: column; align-items: flex-start; gap: 10px; }
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

                <div class="rehab-stats-bar" id="rehab-stats-bar"></div>

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
                    <button class="tab-btn" data-tab="schedule">
                        <i class="fa fa-calendar"></i> Schedule
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

            <div class="tab-content" id="schedule-tab">
                <div class="schedule-toolbar">
                    <button class="btn-new-request" id="schedule-session-btn">
                        <i class="fa fa-plus"></i> Schedule Session
                    </button>
                    <div class="sched-view-toggle">
                        <button class="sched-view-btn active" data-view="list">
                            <i class="fa fa-list"></i> List
                        </button>
                        <button class="sched-view-btn" data-view="calendar">
                            <i class="fa fa-calendar"></i> Calendar
                        </button>
                    </div>
                </div>

                <div id="sched-list-view">
                    <div class="completed-filters">
                        <div class="frappe-control" data-fieldname="sched_filter_date"></div>
                        <div class="frappe-control" data-fieldname="sched_filter_to_date"></div>
                        <button class="btn btn-primary" id="sched-filter-btn">
                            <i class="fa fa-filter"></i> Filter
                        </button>
                    </div>
                    <div class="scrollable-content">
                        <div class="rehab-list-container" id="sched-list-container"></div>
                    </div>
                </div>

                <div id="sched-calendar-view" style="display: none;">
                    <div class="sched-calendar" id="sched-calendar"></div>
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

    // Schedule tab: view mode + the month currently shown in its calendar
    // (separate from currentView/card-list toggle above, which only
    // covers the Requested/Pending/Completed queue tabs).
    let schedView = 'list';
    let schedCalYear, schedCalMonth;
    const schedNow = new Date();
    schedCalYear = schedNow.getFullYear();
    schedCalMonth = schedNow.getMonth();

    let sched_filter_date = frappe.ui.form.make_control({
        parent: page.main.find('[data-fieldname="sched_filter_date"]'),
        df: {
            fieldtype: 'Date',
            fieldname: 'sched_filter_date',
            label: 'From Date',
            default: frappe.datetime.get_today()
        },
        render_input: true
    });
    sched_filter_date.set_value(frappe.datetime.get_today());

    // Optional - leaving this blank keeps the original single-day filter
    // behavior (get_scheduled_sessions' `date` arg); filling it in switches
    // to a `from_date`/`to_date` range query instead.
    let sched_filter_to_date = frappe.ui.form.make_control({
        parent: page.main.find('[data-fieldname="sched_filter_to_date"]'),
        df: {
            fieldtype: 'Date',
            fieldname: 'sched_filter_to_date',
            label: 'To Date (optional)',
            placeholder: __('Leave blank to filter a single day')
        },
        render_input: true
    });
    sched_filter_to_date.refresh();

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
        if (tab === 'schedule') {
            if (schedView === 'list') {
                loadSchedList();
            } else {
                renderSchedCalendar();
            }
        }
    });

    // Schedule tab: list/calendar toggle (separate from the queue tabs'
    // card/list toggle - the two live in different tab-contents).
    page.main.find('.sched-view-btn').on('click', function() {
        const view = $(this).data('view');
        schedView = view;
        page.main.find('.sched-view-btn').removeClass('active');
        $(this).addClass('active');
        if (view === 'list') {
            page.main.find('#sched-list-view').show();
            page.main.find('#sched-calendar-view').hide();
            loadSchedList();
        } else {
            page.main.find('#sched-list-view').hide();
            page.main.find('#sched-calendar-view').show();
            renderSchedCalendar();
        }
    });

    page.main.find('#sched-filter-btn').on('click', function() {
        loadSchedList();
    });

    page.main.find('#schedule-session-btn').on('click', function() {
        openScheduleSessionDialog();
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

                frappe.call({
                    method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_therapy_plan_templates',
                    callback: function(rt) {
                        const templates = rt.message || [];
                        buildDialog(types, templates);
                    }
                });
            }
        });

        function buildDialog(types, templates) {
            // Slots to schedule if "Schedule session(s) now" is checked -
            // one {therapy_type, no_of_sessions} entry per therapy type in
            // play. Kept in sync with the manual therapy_type/no_of_sessions
            // fields or the selected template's rows by updateManualSlot()/
            // renderTemplatePreview() below.
            let currentSlots = [];

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
                        fieldname: 'therapy_plan_template',
                        label: 'Use a Therapy Plan Template (optional)',
                        options: [''].concat(templates.map(t => t.name)),
                        description: __('Bundles one or more therapy types with a preset number of sessions - leave blank to pick a single therapy type manually below.'),
                        onchange: function() { renderTemplatePreview(); }
                    },
                    {
                        fieldtype: 'HTML',
                        fieldname: 'template_preview',
                        depends_on: 'eval:doc.therapy_plan_template',
                        options: '<div id="therapy-template-preview"></div>'
                    },
                    {
                        fieldtype: 'Select',
                        fieldname: 'therapy_type',
                        label: 'Therapy Type',
                        depends_on: 'eval:!doc.therapy_plan_template',
                        mandatory_depends_on: 'eval:!doc.therapy_plan_template',
                        options: types.map(t => ({
                            label: `${t.name} (${format_currency(t.rate)})`,
                            value: t.name
                        })),
                        onchange: function() { updateManualSlot(); renderScheduleRows(); }
                    },
                    {
                        fieldtype: 'Int',
                        fieldname: 'no_of_sessions',
                        label: 'No of Sessions',
                        default: 1,
                        depends_on: 'eval:!doc.therapy_plan_template',
                        mandatory_depends_on: 'eval:!doc.therapy_plan_template',
                        onchange: function() { updateManualSlot(); renderScheduleRows(); }
                    },
                    { fieldtype: 'Section Break', label: __('Scheduling') },
                    {
                        fieldtype: 'Check',
                        fieldname: 'schedule_now',
                        label: __('Schedule session(s) now'),
                        description: __("Book the date/time slot(s) for this request's session(s) right away, instead of doing it later from the Schedule tab."),
                        onchange: function() { renderScheduleRows(); }
                    },
                    {
                        fieldtype: 'Select',
                        fieldname: 'schedule_location',
                        label: __('Location'),
                        options: '\nCenter\nHome\nTele',
                        depends_on: 'eval:doc.schedule_now'
                    },
                    {
                        // No depends_on here deliberately: Frappe re-applies
                        // an HTML field's static `options` into its wrapper
                        // whenever the dialog re-evaluates depends_on for
                        // other fields (e.g. right after schedule_now's own
                        // onchange finishes), which was wiping out the rows
                        // table the instant renderScheduleRows() wrote it.
                        // Left permanently visible and purely JS-controlled
                        // instead - it just renders as an empty, invisible
                        // div when there's nothing to show.
                        fieldtype: 'HTML',
                        fieldname: 'schedule_rows_html',
                        options: '<div id="therapy-schedule-rows"></div>'
                    }
                ],
                primary_action_label: __('Create Request'),
                primary_action: function(values) {
                    if (!values.therapy_plan_template && !values.therapy_type) {
                        frappe.show_alert({ message: __('Please select a therapy type or a template'), indicator: 'orange' }, 5);
                        return;
                    }

                    // Validate + collect the schedule rows *before* creating
                    // anything, so a therapist who checked "Schedule now"
                    // but left a row blank gets stopped up front rather than
                    // ending up with a request created and only some of its
                    // sessions scheduled.
                    let scheduleSlots = [];
                    if (values.schedule_now) {
                        const rowTypes = dialog._scheduleRowTypes || [];
                        if (!rowTypes.length) {
                            frappe.show_alert({ message: __('Please select a therapy type or template before scheduling sessions'), indicator: 'orange' }, 6);
                            return;
                        }
                        const dateInputs = dialog.$wrapper.find('.schedule-date-input');
                        const timeInputs = dialog.$wrapper.find('.schedule-time-input');
                        let incomplete = false;
                        rowTypes.forEach(function(therapyType, idx) {
                            const date = $(dateInputs[idx]).val();
                            const time = $(timeInputs[idx]).val();
                            if (!date || !time) {
                                incomplete = true;
                                return;
                            }
                            scheduleSlots.push({ therapy_type: therapyType, start_date: date, start_time: time + ':00' });
                        });
                        if (incomplete) {
                            frappe.show_alert({ message: __('Please fill in a date and time for every session, or uncheck "Schedule session(s) now"'), indicator: 'orange' }, 8);
                            return;
                        }
                    }

                    frappe.call({
                        method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.create_therapy_request',
                        args: {
                            patient: values.patient,
                            therapy_type: values.therapy_plan_template ? null : values.therapy_type,
                            no_of_sessions: values.no_of_sessions || 1,
                            practitioner: values.practitioner,
                            therapy_plan_template: values.therapy_plan_template || null
                        },
                        freeze: true,
                        freeze_message: __('Creating therapy request...'),
                        callback: function(r) {
                            if (!r.message || r.message.status !== 'Success') return;

                            const planName = r.message.therapy_plan_name;

                            if (!scheduleSlots.length) {
                                frappe.show_alert({ message: __('Therapy request created.'), indicator: 'green' }, 6);
                                dialog.hide();
                                loadTherapies();
                                return;
                            }

                            frappe.call({
                                method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.schedule_multiple_therapy_sessions',
                                args: {
                                    sessions: JSON.stringify(scheduleSlots.map(function(slot) {
                                        return {
                                            therapy_plan: planName,
                                            therapy_type: slot.therapy_type,
                                            start_date: slot.start_date,
                                            start_time: slot.start_time,
                                            practitioner: values.practitioner,
                                            location: values.schedule_location || null
                                        };
                                    }))
                                },
                                freeze: true,
                                freeze_message: __('Scheduling session(s)...'),
                                callback: function(r2) {
                                    if (r2.message && r2.message.status === 'Success') {
                                        frappe.show_alert({
                                            message: __('Therapy request created and {0} session(s) scheduled.', [r2.message.names.length]),
                                            indicator: 'green'
                                        }, 8);
                                    }
                                    dialog.hide();
                                    loadTherapies();
                                    if (page.main.find('#schedule-tab').hasClass('active')) {
                                        if (schedView === 'list') loadSchedList();
                                        else renderSchedCalendar();
                                    }
                                },
                                error: function(r2) {
                                    // The request itself already exists at this point - only
                                    // the scheduling step failed (e.g. a slot conflict), so
                                    // say so explicitly rather than implying nothing happened.
                                    frappe.show_alert({
                                        message: __('Therapy request {0} was created, but scheduling failed: {1}. Use the Schedule tab to try again.',
                                            [planName, r2.message || __('unknown error')]),
                                        indicator: 'orange'
                                    }, 12);
                                    dialog.hide();
                                    loadTherapies();
                                }
                            });
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

            // Keeps currentSlots in sync with the manual therapy_type/
            // no_of_sessions fields. No-op while a template is selected,
            // since renderTemplatePreview() owns currentSlots in that case.
            function updateManualSlot() {
                if (dialog.get_value('therapy_plan_template')) return;
                const type = dialog.get_value('therapy_type');
                const sessions = parseInt(dialog.get_value('no_of_sessions'), 10) || 1;
                currentSlots = type ? [{ therapy_type: type, no_of_sessions: sessions }] : [];
            }

            function renderTemplatePreview() {
                const templateName = dialog.get_value('therapy_plan_template');
                const target = dialog.$wrapper.find('#therapy-template-preview');
                if (!templateName) {
                    target.empty();
                    updateManualSlot();
                    renderScheduleRows();
                    return;
                }
                frappe.call({
                    method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_therapy_plan_template_detail',
                    args: { therapy_plan_template: templateName },
                    callback: function(r) {
                        const rows = r.message || [];
                        currentSlots = rows.map(function(row) {
                            return { therapy_type: row.therapy_type, no_of_sessions: row.no_of_sessions || 1 };
                        });
                        let html = '<table class="table table-bordered" style="margin-top:6px;"><thead><tr><th>Therapy Type</th><th>Sessions</th><th>Rate</th></tr></thead><tbody>';
                        rows.forEach(function(row) {
                            html += `<tr><td>${row.therapy_type}</td><td>${row.no_of_sessions || 0}</td><td>${format_currency(row.rate)}</td></tr>`;
                        });
                        html += '</tbody></table>';
                        target.html(html);
                        renderScheduleRows();
                    }
                });
            }

            function addDaysToToday(days) {
                const d = new Date();
                d.setDate(d.getDate() + days);
                return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
            }

            // Renders one Date+Time row per session slot (one row per
            // no_of_sessions, per therapy type) so a request with several
            // sessions can have all of them scheduled in this same dialog.
            // Plain HTML date/time inputs are used instead of frappe
            // controls since the row count changes dynamically with
            // no_of_sessions/the template selection.
            function renderScheduleRows() {
                // Deferred one tick: this can be called from a field's own
                // onchange, and Frappe's dialog-wide depends_on refresh that
                // follows in the same tick can re-render sibling fields -
                // writing the table synchronously here was getting
                // overwritten by that refresh before the user ever saw it.
                setTimeout(function() {
                    const wrapper = dialog.$wrapper.find('#therapy-schedule-rows');
                    if (!wrapper.length) return;
                    if (!dialog.get_value('schedule_now')) {
                        wrapper.empty();
                        dialog._scheduleRowTypes = [];
                        return;
                    }
                    if (!currentSlots.length) {
                        wrapper.html(`<div class="text-muted">${__('Select a therapy type or template first.')}</div>`);
                        dialog._scheduleRowTypes = [];
                        return;
                    }

                    let rowTypes = [];
                    currentSlots.forEach(function(slot) {
                        const count = parseInt(slot.no_of_sessions, 10) || 1;
                        for (let i = 0; i < count; i++) rowTypes.push(slot.therapy_type);
                    });
                    dialog._scheduleRowTypes = rowTypes;

                    let html = `<table class="table table-bordered" style="margin-top:6px;">
                        <thead><tr><th>#</th><th>${__('Therapy Type')}</th><th>${__('Date')}</th><th>${__('Time')}</th></tr></thead><tbody>`;
                    rowTypes.forEach(function(therapyType, idx) {
                        html += `
                            <tr>
                                <td>${idx + 1}</td>
                                <td>${therapyType}</td>
                                <td><input type="date" class="form-control input-sm schedule-date-input" data-idx="${idx}" value="${addDaysToToday(idx)}"></td>
                                <td><input type="time" class="form-control input-sm schedule-time-input" data-idx="${idx}"></td>
                            </tr>
                        `;
                    });
                    html += '</tbody></table>';
                    wrapper.html(html);
                }, 0);
            }

            dialog.show();
            updateManualSlot();
        }
    }

    function loadTherapies() {
        const patient = search_patient_field.get_value();
        const encounter = search_encounter_field.get_value();
        const date = search_date_field.get_value();

        pendingLoads = 3;
        loadRequestedTherapies(patient, encounter, date);
        loadPendingTherapies(patient, encounter, date);
        loadCompletedTherapies(patient, encounter, completed_date_field.get_value());
        loadRehabSummary();
    }

    // =============================================
    // STAT TILES (Spa Portal's summary strip, adapted to rehab's queue)
    // =============================================
    function loadRehabSummary() {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_rehab_summary',
            callback: function(r) {
                renderStatTiles(r.message || {});
            }
        });
    }

    function renderStatTiles(stats) {
        page.main.find('#rehab-stats-bar').html(`
            <div class="rehab-stat-tile stat-blue">
                <div class="stat-label">Requested</div>
                <div class="stat-value">${stats.requested || 0}</div>
            </div>
            <div class="rehab-stat-tile stat-orange">
                <div class="stat-label">Awaiting Payment</div>
                <div class="stat-value">${stats.pending_unpaid || 0}</div>
            </div>
            <div class="rehab-stat-tile stat-blue">
                <div class="stat-label">Sessions Scheduled Today</div>
                <div class="stat-value">${stats.sessions_scheduled_today || 0}</div>
            </div>
            <div class="rehab-stat-tile stat-green">
                <div class="stat-label">Sessions Completed Today</div>
                <div class="stat-value">${stats.sessions_completed_today || 0}</div>
            </div>
        `);
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
                            ${isPaid ? renderSessionProgress(therapy) : ''}
                        </div>
                    </div>
                    <div class="rehab-card-footer">
                        <span class="status-badge status-pending">
                            <i class="fa fa-clock-o"></i> Pending
                        </span>
                        <div class="rehab-card-actions">
                            ${isPaid && therapy.custom_therapy_plan ? `
                                <button class="btn btn-primary btn-view-plan">
                                    <i class="fa fa-eye"></i> Plan
                                </button>
                                <button class="btn btn-success btn-schedule-session">
                                    <i class="fa fa-calendar-plus-o"></i> Schedule
                                </button>
                                <button class="btn btn-secondary btn-record-assessment">
                                    <i class="fa fa-bar-chart"></i> Assess
                                </button>
                                <button class="btn btn-secondary btn-view-assessments" title="Assessment History">
                                    <i class="fa fa-history"></i>
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
                card.find('.btn-schedule-session').on('click', function(e) {
                    e.stopPropagation();
                    openScheduleSessionDialog(therapy.custom_therapy_plan);
                });
                card.find('.btn-record-assessment').on('click', function(e) {
                    e.stopPropagation();
                    openRecordAssessmentDialog(therapy.patient, therapy.patient_name);
                });
                card.find('.btn-view-assessments').on('click', function(e) {
                    e.stopPropagation();
                    viewAssessmentHistory(therapy.patient, therapy.patient_name);
                });
            }

            container.append(card);
        });
    }

    // Sessions-completed / no-of-sessions progress bar, shown on paid
    // Pending cards (and reused nowhere else - Requested rows have no
    // Therapy Plan yet to measure progress against, Completed rows are
    // already done). Falls back to a 0-length bar rather than hiding
    // itself when the counts are missing, so the layout doesn't jump.
    function renderSessionProgress(therapy) {
        const total = therapy.no_of_sessions || 0;
        const done = therapy.sessions_completed || 0;
        const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
        return `
            <div class="session-progress">
                <div class="session-progress-label">
                    <span>Sessions</span>
                    <span>${done} / ${total}</span>
                </div>
                <div class="session-progress-bar">
                    <div class="session-progress-fill" style="width: ${pct}%;"></div>
                </div>
            </div>
        `;
    }

    function renderPendingTherapyList(therapies, container) {
        let tableHtml = `
            <table class="rehab-list-table">
                <thead>
                    <tr>
                        <th>Therapy Type</th>
                        <th>Patient</th>
                        <th>Date</th>
                        <th>Progress</th>
                        <th>Payment</th>
                        <th>Priority</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        therapies.forEach(function(therapy, index) {
            const priorityClass = therapy.priority === 'High' ? 'priority-high' :
                                 therapy.priority === 'Medium' ? 'priority-medium' : 'priority-low';
            const isPaid = therapy.payment_status === 'Paid';
            const paymentBadgeClass = isPaid ? 'badge badge-success' : 'badge badge-warning';

            tableHtml += `
                <tr style="${!isPaid ? 'opacity: 0.8;' : ''}">
                    <td><strong>${therapy.therapy_type || '-'}</strong></td>
                    <td>${therapy.patient_name}<br><small>${therapy.patient}</small></td>
                    <td>${frappe.datetime.str_to_user(therapy.encounter_date)}</td>
                    <td style="min-width: 140px;">${isPaid ? renderSessionProgress(therapy) : `${therapy.sessions_completed || 0} / ${therapy.no_of_sessions || 0}`}</td>
                    <td><span class="${paymentBadgeClass}">${therapy.payment_status}</span></td>
                    <td>${therapy.priority ? `<span class="priority-badge ${priorityClass}">${therapy.priority}</span>` : '-'}</td>
                    <td>
                        <div class="rehab-list-actions">
                            ${isPaid && therapy.custom_therapy_plan ? `
                                <button class="btn btn-primary btn-sm btn-view-plan" data-therapy-plan="${therapy.custom_therapy_plan}">
                                    <i class="fa fa-eye"></i>
                                </button>
                                <button class="btn btn-success btn-sm btn-schedule-session" data-idx="${index}" title="Schedule Session">
                                    <i class="fa fa-calendar-plus-o"></i>
                                </button>
                                <button class="btn btn-secondary btn-sm btn-record-assessment" data-idx="${index}" title="Record Assessment">
                                    <i class="fa fa-bar-chart"></i>
                                </button>
                                <button class="btn btn-secondary btn-sm btn-view-assessments" data-idx="${index}" title="Assessment History">
                                    <i class="fa fa-history"></i>
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
        container.find('.btn-schedule-session').on('click', function(e) {
            e.stopPropagation();
            const therapy = therapies[$(this).data('idx')];
            if (therapy) openScheduleSessionDialog(therapy.custom_therapy_plan);
        });
        container.find('.btn-record-assessment').on('click', function(e) {
            e.stopPropagation();
            const therapy = therapies[$(this).data('idx')];
            if (therapy) openRecordAssessmentDialog(therapy.patient, therapy.patient_name);
        });
        container.find('.btn-view-assessments').on('click', function(e) {
            e.stopPropagation();
            const therapy = therapies[$(this).data('idx')];
            if (therapy) viewAssessmentHistory(therapy.patient, therapy.patient_name);
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

    // =============================================
    // SCHEDULE TAB - booking + delivering Therapy Sessions
    // (structured after Spa Portal's Bookings tab: a create form, a
    // list/calendar toggle, and a calendar built the same way - but
    // "booking" a session here means creating a real draft Therapy
    // Session against a paid Therapy Plan, and "checking in" a booking
    // means submitting it with logged exercise results.)
    // =============================================

    function openScheduleSessionDialog(prefill_plan) {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_active_therapy_plans',
            callback: function(r) {
                const plans = r.message || [];
                if (!plans.length) {
                    frappe.show_alert({ message: __('No paid, active therapy plans to schedule against'), indicator: 'orange' }, 6);
                    return;
                }

                const planOptions = plans.map(p => ({
                    label: `${p.patient_name} - ${p.name} (${p.total_sessions_completed || 0}/${p.total_sessions || 0} sessions)`,
                    value: p.name
                }));

                const dialog = new frappe.ui.Dialog({
                    title: __('Schedule Therapy Session'),
                    fields: [
                        {
                            fieldtype: 'Select',
                            fieldname: 'therapy_plan',
                            label: 'Therapy Plan',
                            options: planOptions,
                            reqd: 1,
                            default: prefill_plan || (planOptions[0] && planOptions[0].value),
                            onchange: function() { updateTherapyTypeOptions(); }
                        },
                        {
                            fieldtype: 'Select',
                            fieldname: 'therapy_type',
                            label: 'Therapy Type',
                            options: [],
                            reqd: 1
                        },
                        { fieldtype: 'Column Break' },
                        {
                            fieldtype: 'Date',
                            fieldname: 'start_date',
                            label: 'Date',
                            default: frappe.datetime.get_today(),
                            reqd: 1
                        },
                        {
                            fieldtype: 'Time',
                            fieldname: 'start_time',
                            label: 'Time',
                            reqd: 1
                        },
                        { fieldtype: 'Column Break' },
                        {
                            fieldtype: 'Link',
                            fieldname: 'practitioner',
                            label: 'Practitioner (optional override)',
                            options: 'Healthcare Practitioner'
                        },
                        {
                            fieldtype: 'Select',
                            fieldname: 'location',
                            label: 'Location',
                            options: '\nCenter\nHome\nTele'
                        }
                    ],
                    primary_action_label: __('Schedule'),
                    primary_action: function(values) {
                        frappe.call({
                            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.schedule_therapy_session',
                            args: {
                                therapy_plan: values.therapy_plan,
                                therapy_type: values.therapy_type,
                                start_date: values.start_date,
                                start_time: values.start_time,
                                practitioner: values.practitioner || null,
                                location: values.location || null
                            },
                            freeze: true,
                            freeze_message: __('Scheduling session...'),
                            callback: function(r) {
                                if (r.message && r.message.status === 'Success') {
                                    frappe.show_alert({ message: __('Session scheduled'), indicator: 'green' }, 6);
                                    dialog.hide();
                                    if (page.main.find('#schedule-tab').hasClass('active')) {
                                        if (schedView === 'list') loadSchedList();
                                        else renderSchedCalendar();
                                    }
                                }
                            },
                            error: function(r) {
                                frappe.show_alert({ message: r.message || __('Error scheduling session'), indicator: 'red' }, 10);
                            }
                        });
                    }
                });

                function updateTherapyTypeOptions() {
                    const planName = dialog.get_value('therapy_plan');
                    const plan = plans.find(p => p.name === planName);
                    const types = (plan && plan.therapy_types) || [];
                    const options = types.map(t => ({
                        label: `${t.therapy_type} (${t.sessions_completed || 0}/${t.no_of_sessions || 0})`,
                        value: t.therapy_type
                    }));
                    dialog.set_df_property('therapy_type', 'options', options);
                    dialog.set_value('therapy_type', options.length ? options[0].value : '');
                }

                dialog.show();
                updateTherapyTypeOptions();
            }
        });
    }

    function openCompleteSessionDialog(session_name) {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_therapy_session_exercises',
            args: { therapy_session: session_name },
            callback: function(r) {
                const data = r.message;
                if (!data) return;

                let exerciseRowsHtml = '';
                if (data.exercises && data.exercises.length) {
                    data.exercises.forEach(function(ex, idx) {
                        exerciseRowsHtml += `
                            <div class="assessment-score-row" data-idx="${idx}">
                                <div>
                                    <strong>${ex.exercise_type}</strong>
                                    <br><small style="color:#6c757d;">Target: ${ex.counts_target || 0}${ex.assistance_level ? ' &middot; ' + ex.assistance_level : ''}</small>
                                </div>
                                <input type="number" class="form-control exercise-completed-input" data-idx="${idx}" value="${ex.counts_completed || ex.counts_target || 0}" min="0" step="1">
                            </div>
                        `;
                    });
                } else {
                    exerciseRowsHtml = `<p style="color:#6c757d;">${__('No exercises are configured on this Therapy Type - the session will be submitted with no exercise detail.')}</p>`;
                }

                const dialog = new frappe.ui.Dialog({
                    title: __('Complete Session: {0}', [data.patient_name]),
                    size: 'large',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'exercises_html',
                            options: `<div style="margin-bottom:10px;"><strong>${data.therapy_type}</strong> &middot; ${frappe.datetime.str_to_user(data.start_date)} ${data.start_time || ''}</div>${exerciseRowsHtml}`
                        },
                        {
                            fieldtype: 'Small Text',
                            fieldname: 'notes',
                            label: 'Therapist Notes (optional)'
                        }
                    ],
                    primary_action_label: __('Submit Session'),
                    primary_action: function(values) {
                        const exercises = (data.exercises || []).map(function(ex, idx) {
                            const input = dialog.$wrapper.find(`.exercise-completed-input[data-idx="${idx}"]`);
                            return {
                                exercise_type: ex.exercise_type,
                                counts_target: ex.counts_target,
                                counts_completed: parseInt(input.val()) || 0,
                                assistance_level: ex.assistance_level
                            };
                        });

                        frappe.call({
                            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.complete_therapy_session',
                            args: {
                                therapy_session: session_name,
                                exercises: JSON.stringify(exercises),
                                notes: values.notes
                            },
                            freeze: true,
                            freeze_message: __('Submitting session...'),
                            callback: function(r) {
                                if (r.message && r.message.status === 'Success') {
                                    frappe.show_alert({
                                        message: __('Session completed. Therapy Plan status: {0}', [r.message.therapy_plan_status]),
                                        indicator: 'green'
                                    }, 7);
                                    dialog.hide();
                                    loadSchedList();
                                    loadTherapies();
                                }
                            },
                            error: function(r) {
                                frappe.show_alert({ message: r.message || __('Error completing session'), indicator: 'red' }, 10);
                            }
                        });
                    }
                });

                dialog.show();
            }
        });
    }

    function cancelScheduledSession(session_name) {
        frappe.confirm(
            __('Cancel this scheduled session?'),
            function() {
                frappe.call({
                    method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.cancel_therapy_session',
                    args: { therapy_session: session_name },
                    freeze: true,
                    callback: function(r) {
                        if (r.message && r.message.status === 'Success') {
                            frappe.show_alert({ message: __('Session cancelled'), indicator: 'green' }, 5);
                            loadSchedList();
                            if (page.main.find('#sched-calendar-view').is(':visible')) renderSchedCalendar();
                        }
                    }
                });
            }
        );
    }

    function loadSchedList() {
        const fromDate = sched_filter_date.get_value();
        const toDate = sched_filter_to_date.get_value();

        if (toDate && fromDate && toDate < fromDate) {
            frappe.show_alert({ message: __('"To Date" cannot be before "From Date"'), indicator: 'orange' }, 6);
            return;
        }

        const args = toDate ? { from_date: fromDate, to_date: toDate } : { date: fromDate };

        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_scheduled_sessions',
            args: args,
            callback: function(r) {
                renderSchedList(r.message || []);
            }
        });
    }

    function renderSchedList(sessions) {
        const container = page.main.find('#sched-list-container');
        if (!sessions.length) {
            container.html(`
                <div class="empty-state">
                    <i class="fa fa-calendar-o"></i>
                    <h4>${__('No Sessions')}</h4>
                    <p>${__('No therapy sessions found for the selected date(s).')}</p>
                </div>
            `);
            return;
        }

        let rows = '';
        sessions.forEach(function(s, idx) {
            const statusBadge = s.status === 'Completed'
                ? '<span class="badge badge-success">Completed</span>'
                : '<span class="badge badge-info">Scheduled</span>';
            rows += `
                <tr>
                    <td>${idx + 1}</td>
                    <td><strong>${s.patient_name}</strong><br><small>${s.patient}</small></td>
                    <td>${s.therapy_type || '-'}</td>
                    <td>${s.start_time ? s.start_time.substring(0,5) : '-'}</td>
                    <td>${s.practitioner || '-'}</td>
                    <td>${statusBadge}</td>
                    <td>
                        <div class="rehab-list-actions">
                            ${s.status === 'Scheduled' ? `
                                <button class="btn btn-success btn-sm btn-complete-session" data-name="${s.name}">
                                    <i class="fa fa-check"></i> Complete
                                </button>
                                <button class="btn btn-danger btn-sm btn-cancel-session" data-name="${s.name}">
                                    <i class="fa fa-times"></i>
                                </button>
                            ` : `
                                <button class="btn btn-secondary btn-sm" disabled>
                                    <i class="fa fa-check-circle"></i> Delivered
                                </button>
                            `}
                        </div>
                    </td>
                </tr>
            `;
        });

        container.html(`
            <table class="rehab-list-table">
                <thead>
                    <tr><th>#</th><th>Patient</th><th>Type</th><th>Time</th><th>Practitioner</th><th>Status</th><th>Actions</th></tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `);

        container.find('.btn-complete-session').on('click', function() {
            openCompleteSessionDialog($(this).data('name'));
        });
        container.find('.btn-cancel-session').on('click', function() {
            cancelScheduledSession($(this).data('name'));
        });
    }

    function renderSchedCalendar() {
        const calContainer = page.main.find('#sched-calendar');
        const firstDay = new Date(schedCalYear, schedCalMonth, 1);
        const lastDay = new Date(schedCalYear, schedCalMonth + 1, 0);
        const startDow = firstDay.getDay();
        const daysInMonth = lastDay.getDate();
        const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];

        const calStart = new Date(schedCalYear, schedCalMonth, 1 - startDow);
        const totalCells = Math.ceil((startDow + daysInMonth) / 7) * 7;
        const calEnd = new Date(schedCalYear, schedCalMonth, 1 - startDow + totalCells - 1);

        const fmt = d => d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');

        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_scheduled_sessions',
            args: { from_date: fmt(calStart), to_date: fmt(calEnd) },
            callback: function(r) {
                const sessions = r.message || [];
                const byDate = {};
                sessions.forEach(s => {
                    if (!byDate[s.start_date]) byDate[s.start_date] = [];
                    byDate[s.start_date].push(s);
                });

                const todayStr = frappe.datetime.get_today();

                let headerHtml = `
                    <div class="sched-cal-header">
                        <button class="sched-cal-nav-btn" id="sched-cal-prev"><i class="fa fa-chevron-left"></i></button>
                        <h5>${monthNames[schedCalMonth]} ${schedCalYear}</h5>
                        <button class="sched-cal-nav-btn" id="sched-cal-next"><i class="fa fa-chevron-right"></i></button>
                    </div>
                `;

                let gridHtml = '<div class="sched-cal-grid">';
                const dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
                dayNames.forEach(d => { gridHtml += `<div class="sched-cal-day-header">${d}</div>`; });

                for (let i = 0; i < totalCells; i++) {
                    const cellDate = new Date(schedCalYear, schedCalMonth, 1 - startDow + i);
                    const dateStr = fmt(cellDate);
                    const isOtherMonth = cellDate.getMonth() !== schedCalMonth;
                    const isToday = dateStr === todayStr;

                    let classes = 'sched-cal-day';
                    if (isOtherMonth) classes += ' other-month';
                    if (isToday) classes += ' today';

                    let eventsHtml = '';
                    if (byDate[dateStr]) {
                        byDate[dateStr].forEach(s => {
                            const statusClass = s.status === 'Completed' ? ' status-completed' : '';
                            const timeStr = s.start_time ? s.start_time.substring(0,5) : '';
                            eventsHtml += `<div class="sched-cal-event${statusClass}" data-name="${s.name}" data-status="${s.status}" title="${s.patient_name} - ${s.therapy_type} (${s.status})">${timeStr} ${s.patient_name}</div>`;
                        });
                    }

                    gridHtml += `<div class="${classes}"><div class="sched-cal-day-num">${cellDate.getDate()}</div>${eventsHtml}</div>`;
                }
                gridHtml += '</div>';

                calContainer.html(headerHtml + gridHtml);

                calContainer.find('#sched-cal-prev').on('click', function() {
                    schedCalMonth--;
                    if (schedCalMonth < 0) { schedCalMonth = 11; schedCalYear--; }
                    renderSchedCalendar();
                });
                calContainer.find('#sched-cal-next').on('click', function() {
                    schedCalMonth++;
                    if (schedCalMonth > 11) { schedCalMonth = 0; schedCalYear++; }
                    renderSchedCalendar();
                });
                calContainer.find('.sched-cal-event').on('click', function() {
                    const name = $(this).data('name');
                    const status = $(this).data('status');
                    if (status === 'Scheduled') {
                        openCompleteSessionDialog(name);
                    } else {
                        frappe.set_route('Form', 'Therapy Session', name);
                    }
                });
            }
        });
    }

    // =============================================
    // OUTCOME TRACKING - Record Assessment
    // =============================================

    function openRecordAssessmentDialog(patient, patient_name) {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_assessment_templates',
            callback: function(r) {
                const templates = r.message || [];
                if (!templates.length) {
                    frappe.show_alert({ message: __('No Patient Assessment Templates are configured'), indicator: 'orange' }, 6);
                    return;
                }

                const dialog = new frappe.ui.Dialog({
                    title: __('Record Assessment: {0}', [patient_name]),
                    size: 'large',
                    fields: [
                        {
                            fieldtype: 'Select',
                            fieldname: 'assessment_template',
                            label: 'Assessment Template',
                            options: templates.map(t => t.name),
                            reqd: 1,
                            onchange: function() { renderScoreInputs(); }
                        },
                        {
                            fieldtype: 'HTML',
                            fieldname: 'scores_html',
                            options: '<div id="assessment-score-inputs"></div>'
                        }
                    ],
                    primary_action_label: __('Save Assessment'),
                    primary_action: function(values) {
                        const template = templates.find(t => t.name === values.assessment_template);
                        const scores = [];
                        (template.parameters || []).forEach(function(param) {
                            const input = dialog.$wrapper.find(`.score-input[data-param="${param}"]`);
                            const val = input.val();
                            if (val !== '' && val !== undefined) {
                                scores.push({ parameter: param, score: parseInt(val) });
                            }
                        });
                        if (!scores.length) {
                            frappe.show_alert({ message: __('Please score at least one parameter'), indicator: 'orange' }, 5);
                            return;
                        }
                        frappe.call({
                            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.create_patient_assessment',
                            args: {
                                patient: patient,
                                assessment_template: values.assessment_template,
                                scores: JSON.stringify(scores)
                            },
                            freeze: true,
                            freeze_message: __('Saving assessment...'),
                            callback: function(r) {
                                if (r.message && r.message.status === 'Success') {
                                    frappe.show_alert({
                                        message: __('Assessment saved. Score: {0}', [r.message.total_score_obtained]),
                                        indicator: 'green'
                                    }, 7);
                                    dialog.hide();
                                }
                            },
                            error: function(r) {
                                frappe.show_alert({ message: r.message || __('Error saving assessment'), indicator: 'red' }, 10);
                            }
                        });
                    }
                });

                function renderScoreInputs() {
                    const template = templates.find(t => t.name === dialog.get_value('assessment_template'));
                    if (!template) return;
                    let html = '';
                    (template.parameters || []).forEach(function(param) {
                        html += `
                            <div class="assessment-score-row">
                                <span>${param}</span>
                                <input type="number" class="form-control score-input" data-param="${param}" min="${template.scale_min != null ? template.scale_min : ''}" max="${template.scale_max != null ? template.scale_max : ''}" placeholder="${template.scale_min || 0}-${template.scale_max || 10}">
                            </div>
                        `;
                    });
                    dialog.$wrapper.find('#assessment-score-inputs').html(html);
                }

                dialog.show();
                renderScoreInputs();
            }
        });
    }

    function viewAssessmentHistory(patient, patient_name) {
        frappe.call({
            method: 'healthcare.healthcare.page.rehab_portal.rehab_portal.get_patient_assessments',
            args: { patient: patient },
            callback: function(r) {
                const assessments = r.message || [];
                let bodyHtml;
                if (!assessments.length) {
                    bodyHtml = `<p style="color:#6c757d;">${__('No assessments recorded yet for this patient.')}</p>`;
                } else {
                    bodyHtml = assessments.map(function(a) {
                        return `
                            <div class="assessment-history-row">
                                <span>
                                    <strong>${a.assessment_template}</strong>
                                    <br><small style="color:#6c757d;">${frappe.datetime.str_to_user(a.assessment_datetime)}</small>
                                </span>
                                <span style="font-weight:600;">${a.total_score_obtained} / ${a.total_score}</span>
                            </div>
                        `;
                    }).join('');
                }

                const dialog = new frappe.ui.Dialog({
                    title: __('Assessment History: {0}', [patient_name]),
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'history_html',
                            options: bodyHtml
                        }
                    ],
                    primary_action_label: __('Record New Assessment'),
                    primary_action: function() {
                        dialog.hide();
                        openRecordAssessmentDialog(patient, patient_name);
                    }
                });

                dialog.show();
            }
        });
    }

    loadTherapies();
};
//# sourceURL=rehab_portal.js