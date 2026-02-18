/* ==========================================================================
   One-Shot Build — Kanban Dashboard (app.js)
   ========================================================================== */

(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Configuration
    // -----------------------------------------------------------------------
    const urlParams = new URLSearchParams(window.location.search);
    const STATE_PATH = urlParams.get('state') || '/execution-state.yaml';
    const REFRESH_INTERVAL_MS = 5000;

    // DOM references
    const dom = {
        projectName:  document.getElementById('project-name'),
        phaseBadge:   document.getElementById('phase-badge'),
        epicBadge:    document.getElementById('epic-badge'),
        progressBadge: document.getElementById('progress-badge'),
        circuitBadge: document.getElementById('circuit-badge'),
        filterEpic:   document.getElementById('filter-epic'),
        filterStatus: document.getElementById('filter-status'),
        filterGate:   document.getElementById('filter-gate'),
        showSteps:    document.getElementById('show-steps'),
        board:        document.getElementById('board'),
        lastUpdated:  document.getElementById('last-updated'),
        autoRefresh:  document.getElementById('auto-refresh'),
    };

    // Cached state for diffing
    let lastStateRaw = null;
    let currentState = null;
    let refreshTimer = null;

    // -----------------------------------------------------------------------
    // State loading
    // -----------------------------------------------------------------------

    /**
     * Fetch and parse execution-state.yaml from the local server.
     * @param {string} path — URL path to the YAML file
     * @returns {Promise<object|null>} parsed state object or null on error
     */
    async function loadState(path) {
        try {
            const res = await fetch(path, { cache: 'no-store' });
            if (!res.ok) {
                showError('Failed to load state: ' + res.status + ' ' + res.statusText);
                return null;
            }
            const raw = await res.text();

            // Skip re-render if content has not changed
            if (raw === lastStateRaw) {
                return currentState;
            }
            lastStateRaw = raw;

            // js-yaml is loaded as a global via the script tag
            const state = jsyaml.load(raw);
            currentState = state;
            clearError();
            return state;
        } catch (err) {
            showError('Error loading state: ' + err.message);
            return null;
        }
    }

    // -----------------------------------------------------------------------
    // Summary bar
    // -----------------------------------------------------------------------

    /**
     * Update header badges from the parsed state object.
     * @param {object} state — parsed execution-state.yaml
     */
    function updateSummaryBar(state) {
        if (!state) return;

        // Project name
        const name = (state.project && state.project.name) || 'One-Shot Build';
        dom.projectName.textContent = name;

        // Derive phase from epic statuses (no global phase concept)
        const epics = state.epics || {};
        const epicNames = Object.keys(epics);
        const inProgress = epicNames.find(function (k) {
            return !['completed', 'pending'].includes(epics[k].status);
        });
        const phase = inProgress ? epics[inProgress].status : (epicNames.every(function (k) { return epics[k].status === 'completed'; }) ? 'done' : 'pending');
        dom.phaseBadge.textContent = 'Phase: ' + formatLabel(phase);
        dom.phaseBadge.className = 'badge phase-' + phase;

        // Current epic — derive from active status
        const epic = inProgress || '—';
        dom.epicBadge.textContent = 'Epic: ' + formatLabel(epic);

        // Progress — count completed epics vs total
        const completedCount = epicNames.filter(function (k) {
            return epics[k].status === 'completed';
        }).length;
        dom.progressBadge.textContent =
            'Progress: ' + completedCount + '/' + epicNames.length + ' epics';

        // Circuit breaker
        const cb = state.circuit_breaker || (state.workflow && state.workflow.circuit_breaker) || {};
        const cbState = cb.state || cb.status || 'CLOSED';
        dom.circuitBadge.textContent = 'Circuit: ' + cbState;
        dom.circuitBadge.className = 'badge circuit-' + cbState;
    }

    // -----------------------------------------------------------------------
    // Rendering
    // -----------------------------------------------------------------------

    /**
     * Clear and re-render all cards into columns based on state and active filters.
     * @param {object} state — parsed YAML state
     * @param {object} filters — { epic, status, gate }
     */
    function renderBoard(state, filters) {
        // Clear all card containers
        var containers = dom.board.querySelectorAll('.card-container');
        containers.forEach(function (c) { c.innerHTML = ''; });

        if (!state || !state.epics) {
            showEmptyAll();
            return;
        }

        var epics = state.epics;
        var epicNames = Object.keys(epics);
        var showSteps = dom.showSteps.checked;
        var cardIndex = 0;

        // Populate the epic filter dropdown (preserving current selection)
        populateEpicFilter(epicNames);

        epicNames.forEach(function (epicKey) {
            var epic = epics[epicKey];
            epic._key = epicKey;

            // Apply filters
            if (!matchesFilters(epic, filters)) return;

            // Determine which column this epic belongs to
            var status = normalizeStatus(epic.status);
            var column = dom.board.querySelector('.column[data-status="' + status + '"]');
            if (!column) {
                // Fallback to pending
                column = dom.board.querySelector('.column[data-status="pending"]');
            }

            var container = column.querySelector('.card-container');
            var card = createEpicCard(epic, showSteps);
            card.style.animationDelay = (cardIndex * 0.04) + 's';
            container.appendChild(card);
            cardIndex++;
        });

        // Add empty-state placeholders to empty columns
        containers.forEach(function (c) {
            if (c.children.length === 0) {
                var empty = document.createElement('div');
                empty.className = 'empty-state';
                empty.textContent = 'No items';
                c.appendChild(empty);
            }
        });
    }

    /**
     * Create a DOM element representing an epic card.
     * @param {object} epic — epic object from state with _key added
     * @param {boolean} showSteps — whether to render step sub-cards
     * @returns {HTMLElement}
     */
    function createEpicCard(epic, showSteps) {
        var status = normalizeStatus(epic.status);
        var steps = epic.steps || {};
        var stepKeys = Object.keys(steps);

        // Card wrapper
        var card = document.createElement('div');
        card.className = 'epic-card status-' + status;

        // Header (clickable to expand)
        var header = document.createElement('div');
        header.className = 'epic-card-header';

        // Title row
        var title = document.createElement('div');
        title.className = 'epic-card-title';

        var expandIcon = document.createElement('span');
        expandIcon.className = 'expand-icon';
        expandIcon.textContent = '\u25B6'; // right-pointing triangle

        var titleText = document.createElement('span');
        titleText.textContent = formatLabel(epic._key);

        title.appendChild(expandIcon);
        title.appendChild(titleText);

        // Meta row
        var meta = document.createElement('div');
        meta.className = 'epic-card-meta';

        // Status tag
        var statusTag = document.createElement('span');
        statusTag.className = 'meta-tag tag-status ' + status;
        statusTag.textContent = formatLabel(status);
        meta.appendChild(statusTag);

        // Step count tag
        if (stepKeys.length > 0) {
            var completedSteps = stepKeys.filter(function (k) {
                var s = steps[k];
                return s.tests_pass && s.review_approved;
            }).length;
            var stepsTag = document.createElement('span');
            stepsTag.className = 'meta-tag tag-steps';
            stepsTag.textContent = completedSteps + '/' + stepKeys.length + ' steps';
            meta.appendChild(stepsTag);
        }

        // Gate summary tag
        if (stepKeys.length > 0) {
            var gateInfo = computeGateSummary(steps);
            var gateTag = document.createElement('span');
            gateTag.className = 'meta-tag tag-gate ' + gateInfo.cls;
            gateTag.textContent = gateInfo.label;
            meta.appendChild(gateTag);
        }

        header.appendChild(title);
        header.appendChild(meta);
        card.appendChild(header);

        // Progress bar
        if (stepKeys.length > 0) {
            var completedSteps2 = stepKeys.filter(function (k) {
                var s = steps[k];
                return s.tests_pass && s.review_approved;
            }).length;
            var progressBar = document.createElement('div');
            progressBar.className = 'epic-progress';
            var fill = document.createElement('div');
            fill.className = 'epic-progress-fill';
            fill.style.width = Math.round((completedSteps2 / stepKeys.length) * 100) + '%';
            progressBar.appendChild(fill);
            card.appendChild(progressBar);
        }

        // Step list
        if (showSteps && stepKeys.length > 0) {
            var stepList = document.createElement('div');
            stepList.className = 'step-list';
            stepKeys.forEach(function (stepKey) {
                var step = steps[stepKey];
                step._key = stepKey;
                stepList.appendChild(createStepCard(step));
            });
            card.appendChild(stepList);
        }

        // Toggle expand on header click
        header.addEventListener('click', function () {
            card.classList.toggle('expanded');
        });

        return card;
    }

    /**
     * Create a DOM element representing a step sub-card.
     * @param {object} step — step object with _key, tests_pass, review_approved
     * @returns {HTMLElement}
     */
    function createStepCard(step) {
        var testsPass = !!step.tests_pass;
        var reviewPass = !!step.review_approved;
        var bothPass = testsPass && reviewPass;
        var neitherPass = !testsPass && !reviewPass;

        var stepClass;
        if (bothPass) stepClass = 'step-pass';
        else if (neitherPass) stepClass = 'step-pending';
        else stepClass = 'step-partial';

        var div = document.createElement('div');
        div.className = 'step-card ' + stepClass;

        var nameSpan = document.createElement('span');
        nameSpan.className = 'step-name';
        nameSpan.textContent = formatLabel(step._key);

        var gates = document.createElement('span');
        gates.className = 'step-gates';

        var testDot = document.createElement('span');
        testDot.className = 'gate-dot ' + (testsPass ? 'pass' : 'fail');
        testDot.title = 'Tests: ' + (testsPass ? 'pass' : 'fail');

        var reviewDot = document.createElement('span');
        reviewDot.className = 'gate-dot ' + (reviewPass ? 'pass' : 'fail');
        reviewDot.title = 'Review: ' + (reviewPass ? 'pass' : 'fail');

        gates.appendChild(testDot);
        gates.appendChild(reviewDot);

        div.appendChild(nameSpan);
        div.appendChild(gates);
        return div;
    }

    // -----------------------------------------------------------------------
    // Filtering
    // -----------------------------------------------------------------------

    /**
     * Read current filter dropdowns and return a filters object.
     * @returns {object} { epic, status, gate }
     */
    function readFilters() {
        return {
            epic:   dom.filterEpic.value,
            status: dom.filterStatus.value,
            gate:   dom.filterGate.value,
        };
    }

    /**
     * Read filter dropdowns and re-render the board.
     */
    function applyFilters() {
        if (!currentState) return;
        var filters = readFilters();
        renderBoard(currentState, filters);
    }

    /**
     * Test whether an epic matches the active filters.
     * @param {object} epic — epic object with _key and status
     * @param {object} filters — { epic, status, gate }
     * @returns {boolean}
     */
    function matchesFilters(epic, filters) {
        // Epic filter
        if (filters.epic !== 'all' && epic._key !== filters.epic) {
            return false;
        }

        // Status filter
        if (filters.status !== 'all') {
            var normalized = normalizeStatus(epic.status);
            if (normalized !== filters.status) return false;
        }

        // Gate filter
        if (filters.gate !== 'all') {
            var steps = epic.steps || {};
            var stepKeys = Object.keys(steps);
            if (stepKeys.length === 0) {
                // No steps — only match "tests_pending"
                return filters.gate === 'tests_pending';
            }
            var gateInfo = computeGateSummary(steps);
            if (filters.gate === 'both_pass' && gateInfo.id !== 'both_pass') return false;
            if (filters.gate === 'tests_pending' && gateInfo.id !== 'tests_pending') return false;
            if (filters.gate === 'review_pending' && gateInfo.id !== 'review_pending') return false;
        }

        return true;
    }

    /**
     * Populate the epic filter dropdown with discovered epic keys.
     * Preserves the user's current selection when possible.
     * @param {string[]} epicNames
     */
    function populateEpicFilter(epicNames) {
        var current = dom.filterEpic.value;
        // Only rebuild if the option count changed
        if (dom.filterEpic.options.length === epicNames.length + 1) return;

        dom.filterEpic.innerHTML = '<option value="all">All Epics</option>';
        epicNames.forEach(function (name) {
            var opt = document.createElement('option');
            opt.value = name;
            opt.textContent = formatLabel(name);
            dom.filterEpic.appendChild(opt);
        });

        // Restore selection
        if (current && dom.filterEpic.querySelector('option[value="' + current + '"]')) {
            dom.filterEpic.value = current;
        }
    }

    // -----------------------------------------------------------------------
    // Auto-refresh
    // -----------------------------------------------------------------------

    /**
     * Start polling for state changes at the given interval.
     * @param {number} interval — milliseconds between refreshes
     */
    function autoRefresh(interval) {
        if (refreshTimer) clearInterval(refreshTimer);

        refreshTimer = setInterval(async function () {
            var state = await loadState(STATE_PATH);
            if (state) {
                updateSummaryBar(state);
                renderBoard(state, readFilters());
                updateTimestamp();
            }
        }, interval);

        dom.autoRefresh.textContent = 'Auto-refresh: ' + (interval / 1000) + 's';
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    /**
     * Normalize epic status values to column data-status values.
     * @param {string} status
     * @returns {string}
     */
    function normalizeStatus(status) {
        if (!status) return 'pending';
        var s = String(status).toLowerCase().trim();
        var map = {
            'pending':     'pending',
            'not_started': 'pending',
            'planning':    'plan',
            'plan':        'plan',
            'in_progress': 'in_progress',
            'in-progress': 'in_progress',
            'building':    'in_progress',
            'submitting':  'review',
            'active':      'in_progress',
            'review':      'review',
            'in_review':   'review',
            'completed':   'completed',
            'complete':    'completed',
            'done':        'completed',
            'blocked':     'blocked',
            'failed':      'blocked',
        };
        return map[s] || 'pending';
    }

    /**
     * Compute an overall gate summary for an epic's steps.
     * @param {object} steps — { step_key: { tests_pass, review_approved } }
     * @returns {{ id: string, label: string, cls: string }}
     */
    function computeGateSummary(steps) {
        var keys = Object.keys(steps);
        if (keys.length === 0) return { id: 'tests_pending', label: 'No steps', cls: 'gate-fail' };

        var allTestsPass = true;
        var allReviewPass = true;

        keys.forEach(function (k) {
            if (!steps[k].tests_pass) allTestsPass = false;
            if (!steps[k].review_approved) allReviewPass = false;
        });

        if (allTestsPass && allReviewPass) {
            return { id: 'both_pass', label: 'All gates pass', cls: 'gate-pass' };
        }
        if (allTestsPass && !allReviewPass) {
            return { id: 'review_pending', label: 'Review pending', cls: 'gate-partial' };
        }
        return { id: 'tests_pending', label: 'Tests pending', cls: 'gate-fail' };
    }

    /**
     * Convert a snake_case or kebab-case key into a human-readable label.
     * @param {string} key
     * @returns {string}
     */
    function formatLabel(key) {
        if (!key || key === '—') return '—';
        return key
            .replace(/[_-]/g, ' ')
            .replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    }

    /**
     * Update the "last updated" timestamp in the footer.
     */
    function updateTimestamp() {
        var now = new Date();
        dom.lastUpdated.textContent = 'Last updated: ' + now.toLocaleTimeString();
    }

    /**
     * Show an error banner above the board.
     * @param {string} message
     */
    function showError(message) {
        var existing = document.querySelector('.error-banner');
        if (existing) {
            existing.textContent = message;
            return;
        }
        var banner = document.createElement('div');
        banner.className = 'error-banner';
        banner.textContent = message;
        dom.board.parentNode.insertBefore(banner, dom.board);
    }

    /**
     * Remove any error banner.
     */
    function clearError() {
        var banner = document.querySelector('.error-banner');
        if (banner) banner.remove();
    }

    /**
     * Add an empty-state placeholder to all columns.
     */
    function showEmptyAll() {
        dom.board.querySelectorAll('.card-container').forEach(function (c) {
            if (c.children.length === 0) {
                var empty = document.createElement('div');
                empty.className = 'empty-state';
                empty.textContent = 'No items';
                c.appendChild(empty);
            }
        });
    }

    // -----------------------------------------------------------------------
    // Event listeners
    // -----------------------------------------------------------------------
    dom.filterEpic.addEventListener('change', applyFilters);
    dom.filterStatus.addEventListener('change', applyFilters);
    dom.filterGate.addEventListener('change', applyFilters);
    dom.showSteps.addEventListener('change', applyFilters);

    // -----------------------------------------------------------------------
    // Bootstrap
    // -----------------------------------------------------------------------
    (async function init() {
        var state = await loadState(STATE_PATH);
        if (state) {
            updateSummaryBar(state);
            renderBoard(state, readFilters());
            updateTimestamp();
        }
        autoRefresh(REFRESH_INTERVAL_MS);
    })();
})();
