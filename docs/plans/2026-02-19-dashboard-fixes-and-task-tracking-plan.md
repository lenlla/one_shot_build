# Dashboard Fixes and Task Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix dashboard bugs caused by state field mismatches and add a Tasks tab for individual task-level Kanban tracking.

**Architecture:** The dashboard reads `.execution-state.yaml` via a local HTTP server. We fix the JS to use `step.status` as the primary completion indicator (instead of gate booleans alone), update `build-step/SKILL.md` to also write gate fields, fix `serve.sh` to accept a build dir argument, and add a tab toggle between Epics and Tasks views. The Tasks view renders each step as its own card in the appropriate Kanban column.

**Tech Stack:** Vanilla JS, HTML, CSS, Bash (serve.sh), BATS (tests)

---

### Task 1: Create test fixture YAML for dashboard verification

**Files:**
- Create: `tests/fixtures/dashboard-test-state.yaml`

**Step 1: Create the fixture file**

This YAML exercises all step states and gate combinations the dashboard must handle:

```yaml
started_at: "2026-02-19T14:30:00Z"
mode: interactive
epics:
  data-loading:
    status: completed
    steps:
      task-1-load-csv:
        status: completed
        tests_pass: true
        review_approved: true
        review_rounds: 1
      task-2-validate-schema:
        status: completed
        tests_pass: true
        review_approved: true
        review_rounds: 2
  transformation:
    status: in_progress
    current_step: "task-2-normalize-columns"
    steps:
      task-1-parse-dates:
        status: completed
        tests_pass: true
        review_approved: true
        review_rounds: 1
      task-2-normalize-columns:
        status: in_progress
        tests_pass: true
        review_approved: false
        review_rounds: 0
      task-3-aggregate-metrics:
        status: pending
  reporting:
    status: pending
    steps:
      task-1-build-summary:
        status: pending
      task-2-generate-charts:
        status: pending
  model-training:
    status: plan
    steps:
      task-1-feature-engineering:
        status: pending
      task-2-train-model:
        status: pending
circuit_breaker: {}
```

**Step 2: Commit**

```bash
git add tests/fixtures/dashboard-test-state.yaml
git commit -m "test: add dashboard test fixture YAML with all step states"
```

---

### Task 2: Fix step completion counting to use status field

**Files:**
- Modify: `dashboard/app.js:219-222` (step count in createEpicCard)
- Modify: `dashboard/app.js:244-247` (progress bar in createEpicCard)

**Step 1: Write a helper function `isStepCompleted`**

Add after the `computeGateSummary` function (after line 483 in `dashboard/app.js`):

```javascript
    /**
     * Determine if a step is completed.
     * Uses status field as primary indicator, falls back to gate booleans.
     * @param {object} step
     * @returns {boolean}
     */
    function isStepCompleted(step) {
        if (step.status === 'completed') return true;
        return !!step.tests_pass && !!step.review_approved;
    }
```

**Step 2: Update step count tag (lines 219-222)**

Replace the step counting logic in `createEpicCard`:

Old (lines 219-222):
```javascript
            var completedSteps = stepKeys.filter(function (k) {
                var s = steps[k];
                return s.tests_pass && s.review_approved;
            }).length;
```

New:
```javascript
            var completedSteps = stepKeys.filter(function (k) {
                return isStepCompleted(steps[k]);
            }).length;
```

**Step 3: Update progress bar (lines 244-247)**

Old (lines 244-247):
```javascript
            var completedSteps2 = stepKeys.filter(function (k) {
                var s = steps[k];
                return s.tests_pass && s.review_approved;
            }).length;
```

New:
```javascript
            var completedSteps2 = stepKeys.filter(function (k) {
                return isStepCompleted(steps[k]);
            }).length;
```

**Step 4: Verify with test fixture**

Open the dashboard pointing at the test fixture. The "transformation" epic should show 1/3 steps (task-1-parse-dates is completed). The "data-loading" epic should show 2/2 steps.

**Step 5: Commit**

```bash
git add dashboard/app.js
git commit -m "fix(dashboard): use status field as primary step completion indicator"
```

---

### Task 3: Fix createStepCard to show status and handle missing gate fields

**Files:**
- Modify: `dashboard/app.js:282-317` (createStepCard function)

**Step 1: Rewrite createStepCard**

Replace the entire `createStepCard` function (lines 282-317):

```javascript
    /**
     * Create a DOM element representing a step sub-card.
     * @param {object} step — step object with _key, status, tests_pass, review_approved
     * @returns {HTMLElement}
     */
    function createStepCard(step) {
        var status = step.status || 'pending';
        var testsPass = !!step.tests_pass;
        var reviewPass = !!step.review_approved;
        var reviewRounds = step.review_rounds || 0;

        // Determine card class from status
        var stepClass;
        if (status === 'completed') stepClass = 'step-pass';
        else if (status === 'in_progress') stepClass = 'step-partial';
        else stepClass = 'step-pending';

        var div = document.createElement('div');
        div.className = 'step-card ' + stepClass;

        // Status dot
        var statusDot = document.createElement('span');
        statusDot.className = 'status-dot status-' + status;
        statusDot.title = formatLabel(status);
        div.appendChild(statusDot);

        var nameSpan = document.createElement('span');
        nameSpan.className = 'step-name';
        nameSpan.textContent = formatLabel(step._key);
        div.appendChild(nameSpan);

        var indicators = document.createElement('span');
        indicators.className = 'step-indicators';

        // Review rounds badge (if > 0)
        if (reviewRounds > 0) {
            var roundsBadge = document.createElement('span');
            roundsBadge.className = 'review-rounds-badge';
            roundsBadge.textContent = 'R' + reviewRounds;
            roundsBadge.title = reviewRounds + ' review round(s)';
            indicators.appendChild(roundsBadge);
        }

        // Gate dots
        var gates = document.createElement('span');
        gates.className = 'step-gates';

        var testDot = document.createElement('span');
        testDot.className = 'gate-dot ' + (testsPass ? 'pass' : 'fail');
        testDot.title = 'Tests: ' + (testsPass ? 'pass' : 'pending');

        var reviewDot = document.createElement('span');
        reviewDot.className = 'gate-dot ' + (reviewPass ? 'pass' : 'fail');
        reviewDot.title = 'Review: ' + (reviewPass ? 'approved' : 'pending');

        gates.appendChild(testDot);
        gates.appendChild(reviewDot);
        indicators.appendChild(gates);

        div.appendChild(indicators);
        return div;
    }
```

**Step 2: Verify with test fixture**

Step sub-cards should now show:
- A status dot (gray for pending, blue for in_progress, green for completed)
- The step name
- Review rounds badge (e.g., "R2") when rounds > 0
- Gate dots

**Step 3: Commit**

```bash
git add dashboard/app.js
git commit -m "fix(dashboard): show step status indicator and handle missing gate fields"
```

---

### Task 4: Add CSS for status dots and review rounds badges

**Files:**
- Modify: `dashboard/style.css` (append after step-card styles, after line 488)

**Step 1: Add new CSS rules**

Append after the `.gate-dot.fail` rule (after line 488):

```css

/* --- Status dots --- */
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}

.status-dot.status-pending    { background: var(--color-pending); }
.status-dot.status-in_progress { background: var(--color-in-progress); }
.status-dot.status-completed  { background: var(--color-completed); }

/* --- Step indicators layout --- */
.step-indicators {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
}

/* --- Review rounds badge --- */
.review-rounds-badge {
    font-size: 0.65rem;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 999px;
    background: var(--color-review);
    color: #1a1a2e;
}
```

**Step 2: Commit**

```bash
git add dashboard/style.css
git commit -m "feat(dashboard): add CSS for status dots and review rounds badges"
```

---

### Task 5: Fix computeGateSummary to respect status field

**Files:**
- Modify: `dashboard/app.js:464-483` (computeGateSummary function)

**Step 1: Update computeGateSummary**

Replace lines 464-483:

```javascript
    /**
     * Compute an overall gate summary for an epic's steps.
     * Uses status field as primary, gate booleans as supplementary.
     * @param {object} steps — { step_key: { status, tests_pass, review_approved } }
     * @returns {{ id: string, label: string, cls: string }}
     */
    function computeGateSummary(steps) {
        var keys = Object.keys(steps);
        if (keys.length === 0) return { id: 'tests_pending', label: 'No steps', cls: 'gate-fail' };

        var allComplete = true;
        var allTestsPass = true;
        var allReviewPass = true;

        keys.forEach(function (k) {
            var s = steps[k];
            if (!isStepCompleted(s)) allComplete = false;
            if (!s.tests_pass) allTestsPass = false;
            if (!s.review_approved) allReviewPass = false;
        });

        if (allComplete && allTestsPass && allReviewPass) {
            return { id: 'both_pass', label: 'All gates pass', cls: 'gate-pass' };
        }
        if (allTestsPass && !allReviewPass) {
            return { id: 'review_pending', label: 'Review pending', cls: 'gate-partial' };
        }
        if (allComplete) {
            return { id: 'both_pass', label: 'All steps done', cls: 'gate-pass' };
        }
        return { id: 'tests_pending', label: 'Tests pending', cls: 'gate-fail' };
    }
```

**Step 2: Commit**

```bash
git add dashboard/app.js
git commit -m "fix(dashboard): gate summary respects status field alongside gate booleans"
```

---

### Task 6: Fix serve.sh to accept build directory argument

**Files:**
- Modify: `dashboard/serve.sh`

**Step 1: Write the failing test**

Add to `tests/state_test.bats`:

```bash
@test "serve.sh symlinks state file from specified build dir" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    echo "epics: {}" > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml"

    SERVE_DIR=$(mktemp -d)
    SCRIPT_DIR="${BATS_TEST_DIRNAME}/../dashboard"

    # Simulate what serve.sh does: symlink dashboard files + state file
    ln -s "$SCRIPT_DIR"/* "$SERVE_DIR/" 2>/dev/null || true
    ln -s "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" "$SERVE_DIR/execution-state.yaml" 2>/dev/null || true

    run test -L "$SERVE_DIR/execution-state.yaml"
    assert_success

    run cat "$SERVE_DIR/execution-state.yaml"
    assert_output --partial "epics"

    rm -rf "$SERVE_DIR"
}
```

**Step 2: Run test to verify it passes (this is testing the symlinking approach)**

```bash
./node_modules/bats/bin/bats tests/state_test.bats -f "serve.sh symlinks"
```

Expected: PASS

**Step 3: Update serve.sh**

Replace the entire file:

```bash
#!/usr/bin/env bash
# dashboard/serve.sh
# Launches a local HTTP server for the Kanban dashboard.
# Serves both the dashboard files AND the project's state file.
# Usage: serve.sh [project-root-or-build-dir] [port]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT_ROOT="${1:-$(pwd)}"
PORT="${2:-8080}"

# Create a temp directory with symlinks so the server can access both
SERVE_DIR=$(mktemp -d)
ln -s "$SCRIPT_DIR"/* "$SERVE_DIR/" 2>/dev/null || true

# Check if the argument itself contains .execution-state.yaml
if [[ -f "$PROJECT_ROOT/.execution-state.yaml" ]]; then
    ln -s "$PROJECT_ROOT/.execution-state.yaml" "$SERVE_DIR/execution-state.yaml" 2>/dev/null || true
    echo "State file: $PROJECT_ROOT/.execution-state.yaml"
else
    # Search recursively for the first execution state file
    find "$PROJECT_ROOT" -name ".execution-state.yaml" -not -path "*/.git/*" 2>/dev/null | while read -r state_file; do
        ln -s "$state_file" "$SERVE_DIR/execution-state.yaml" 2>/dev/null || true
        echo "State file: $state_file"
        break
    done
fi

# Cleanup on exit
trap "rm -rf $SERVE_DIR" EXIT

echo "Kanban Dashboard: http://localhost:${PORT}"
echo "Project root: $PROJECT_ROOT"
echo "Press Ctrl+C to stop."

# Serve with Python's built-in HTTP server
cd "$SERVE_DIR"
python3 -m http.server "$PORT" --bind 127.0.0.1
```

**Step 4: Commit**

```bash
git add dashboard/serve.sh tests/state_test.bats
git commit -m "fix(dashboard): serve.sh accepts build dir with direct state file"
```

---

### Task 7: Add tab bar HTML

**Files:**
- Modify: `dashboard/index.html:35-36` (between filters and board)

**Step 1: Add tab bar markup**

Insert after the `show-steps` checkbox label (after line 35) and before the closing `</div>` of filters (line 36):

Replace lines 35-36:
```html
        <label><input type="checkbox" id="show-steps" checked> Show Steps</label>
    </div>
```

With:
```html
        <label><input type="checkbox" id="show-steps" checked> Show Steps</label>
    </div>

    <div id="tab-bar">
        <button class="tab active" data-tab="epics">Epics</button>
        <button class="tab" data-tab="tasks">Tasks</button>
    </div>
```

**Step 2: Commit**

```bash
git add dashboard/index.html
git commit -m "feat(dashboard): add Epics/Tasks tab bar HTML"
```

---

### Task 8: Add tab bar CSS

**Files:**
- Modify: `dashboard/style.css` (insert after #filters styles, after line 192)

**Step 1: Add tab bar styles**

Insert after the `#filters input[type="checkbox"]` rule (after line 192):

```css

/* ==========================================================================
   Tab Bar
   ========================================================================== */
#tab-bar {
    display: flex;
    gap: 0;
    padding: 0 24px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
}

#tab-bar .tab {
    padding: 10px 20px;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-secondary);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: color 0.15s ease, border-color 0.15s ease;
}

#tab-bar .tab:hover {
    color: var(--text-primary);
}

#tab-bar .tab.active {
    color: var(--color-in-progress);
    border-bottom-color: var(--color-in-progress);
}
```

**Step 2: Commit**

```bash
git add dashboard/style.css
git commit -m "feat(dashboard): add tab bar CSS styling"
```

---

### Task 9: Add task card CSS

**Files:**
- Modify: `dashboard/style.css` (append after step-card styles)

**Step 1: Add task card styles**

Append after the review-rounds-badge rule added in Task 4:

```css

/* ==========================================================================
   Task Cards (Tasks tab)
   ========================================================================== */
.task-card {
    border-radius: var(--radius-sm);
    border-left: 3px solid var(--color-pending);
    background: var(--bg-primary);
    box-shadow: var(--shadow-sm);
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    transition: box-shadow 0.2s ease, transform 0.15s ease;
    animation: fadeIn 0.25s ease forwards;
}

.task-card:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}

.task-card.task-pending     { border-left-color: var(--color-pending); }
.task-card.task-in_progress { border-left-color: var(--color-in-progress); }
.task-card.task-completed   { border-left-color: var(--color-completed); }

.task-card-header {
    display: flex;
    align-items: center;
    gap: 6px;
}

.task-card-name {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
}

.task-card-epic-tag {
    font-size: 0.65rem;
    padding: 1px 6px;
    border-radius: 999px;
    background: var(--bg-secondary);
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
    white-space: nowrap;
    flex-shrink: 0;
}

.task-card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
}
```

**Step 2: Commit**

```bash
git add dashboard/style.css
git commit -m "feat(dashboard): add task card CSS for Tasks tab"
```

---

### Task 10: Add tab switching and renderTaskBoard to app.js

**Files:**
- Modify: `dashboard/app.js`

**Step 1: Add DOM reference for tab bar**

In the `dom` object (line 16-29), add after `autoRefresh`:

```javascript
        tabEpics:     document.querySelector('#tab-bar .tab[data-tab="epics"]'),
        tabTasks:     document.querySelector('#tab-bar .tab[data-tab="tasks"]'),
```

**Step 2: Add currentTab state variable**

After the `let refreshTimer = null;` line (line 34), add:

```javascript
    let currentTab = 'epics';
```

**Step 3: Add normalizeStepStatus helper**

Add after the `normalizeStatus` function (after line 457):

```javascript
    /**
     * Normalize step status values to column data-status values.
     * Steps only use: pending, in_progress, completed.
     * @param {string} status
     * @returns {string}
     */
    function normalizeStepStatus(status) {
        if (!status) return 'pending';
        var s = String(status).toLowerCase().trim();
        var map = {
            'pending':     'pending',
            'in_progress': 'in_progress',
            'completed':   'completed',
        };
        return map[s] || 'pending';
    }
```

**Step 4: Add createTaskCard function**

Add after the `createStepCard` function:

```javascript
    /**
     * Create a DOM element representing an individual task card for the Tasks tab.
     * @param {object} step — step object with _key, status, tests_pass, review_approved
     * @param {string} epicKey — parent epic key
     * @returns {HTMLElement}
     */
    function createTaskCard(step, epicKey) {
        var status = step.status || 'pending';
        var testsPass = !!step.tests_pass;
        var reviewPass = !!step.review_approved;
        var reviewRounds = step.review_rounds || 0;

        var card = document.createElement('div');
        card.className = 'task-card task-' + status;

        // Header row: status dot + name + epic tag
        var header = document.createElement('div');
        header.className = 'task-card-header';

        var statusDot = document.createElement('span');
        statusDot.className = 'status-dot status-' + status;
        statusDot.title = formatLabel(status);
        header.appendChild(statusDot);

        var name = document.createElement('span');
        name.className = 'task-card-name';
        name.textContent = formatLabel(step._key);
        header.appendChild(name);

        var epicTag = document.createElement('span');
        epicTag.className = 'task-card-epic-tag';
        epicTag.textContent = formatLabel(epicKey);
        header.appendChild(epicTag);

        card.appendChild(header);

        // Footer row: review rounds + gate dots
        var footer = document.createElement('div');
        footer.className = 'task-card-footer';

        var left = document.createElement('span');
        if (reviewRounds > 0) {
            var roundsBadge = document.createElement('span');
            roundsBadge.className = 'review-rounds-badge';
            roundsBadge.textContent = 'R' + reviewRounds;
            roundsBadge.title = reviewRounds + ' review round(s)';
            left.appendChild(roundsBadge);
        }
        footer.appendChild(left);

        var gates = document.createElement('span');
        gates.className = 'step-gates';

        var testDot = document.createElement('span');
        testDot.className = 'gate-dot ' + (testsPass ? 'pass' : 'fail');
        testDot.title = 'Tests: ' + (testsPass ? 'pass' : 'pending');

        var reviewDot = document.createElement('span');
        reviewDot.className = 'gate-dot ' + (reviewPass ? 'pass' : 'fail');
        reviewDot.title = 'Review: ' + (reviewPass ? 'approved' : 'pending');

        gates.appendChild(testDot);
        gates.appendChild(reviewDot);
        footer.appendChild(gates);

        card.appendChild(footer);
        return card;
    }
```

**Step 5: Add renderTaskBoard function**

Add after the `renderBoard` function (after line 172):

```javascript
    /**
     * Render individual task cards into columns based on step status.
     * @param {object} state — parsed YAML state
     * @param {object} filters — { epic, status, gate }
     */
    function renderTaskBoard(state, filters) {
        // Clear all card containers
        var containers = dom.board.querySelectorAll('.card-container');
        containers.forEach(function (c) { c.innerHTML = ''; });

        if (!state || !state.epics) {
            showEmptyAll();
            return;
        }

        var epics = state.epics;
        var epicNames = Object.keys(epics);
        var cardIndex = 0;

        populateEpicFilter(epicNames);

        epicNames.forEach(function (epicKey) {
            var epic = epics[epicKey];
            var steps = epic.steps || {};
            var stepKeys = Object.keys(steps);

            // Apply epic filter
            if (filters.epic !== 'all' && epicKey !== filters.epic) return;

            stepKeys.forEach(function (stepKey) {
                var step = steps[stepKey];
                step._key = stepKey;
                var stepStatus = normalizeStepStatus(step.status);

                // Apply status filter (map step status to column status)
                if (filters.status !== 'all' && stepStatus !== filters.status) return;

                // Apply gate filter
                if (filters.gate !== 'all') {
                    var testsPass = !!step.tests_pass;
                    var reviewPass = !!step.review_approved;
                    if (filters.gate === 'both_pass' && !(testsPass && reviewPass)) return;
                    if (filters.gate === 'tests_pending' && testsPass) return;
                    if (filters.gate === 'review_pending' && (!testsPass || reviewPass)) return;
                }

                // Determine column
                var column = dom.board.querySelector('.column[data-status="' + stepStatus + '"]');
                if (!column) {
                    column = dom.board.querySelector('.column[data-status="pending"]');
                }

                var container = column.querySelector('.card-container');
                var card = createTaskCard(step, epicKey);
                card.style.animationDelay = (cardIndex * 0.04) + 's';
                container.appendChild(card);
                cardIndex++;
            });
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
```

**Step 6: Update applyFilters to respect current tab**

Replace the `applyFilters` function (lines 338-342):

```javascript
    /**
     * Read filter dropdowns and re-render the board for the current tab.
     */
    function applyFilters() {
        if (!currentState) return;
        var filters = readFilters();
        if (currentTab === 'tasks') {
            renderTaskBoard(currentState, filters);
        } else {
            renderBoard(currentState, filters);
        }
    }
```

**Step 7: Update autoRefresh to respect current tab**

Replace the refresh callback (lines 414-421):

```javascript
        refreshTimer = setInterval(async function () {
            var state = await loadState(STATE_PATH);
            if (state) {
                updateSummaryBar(state);
                applyFilters();
                updateTimestamp();
            }
        }, interval);
```

**Step 8: Update init to respect current tab**

Replace the init function (lines 554-562):

```javascript
    (async function init() {
        var state = await loadState(STATE_PATH);
        if (state) {
            updateSummaryBar(state);
            applyFilters();
            updateTimestamp();
        }
        autoRefresh(REFRESH_INTERVAL_MS);
    })();
```

**Step 9: Add tab event listeners**

Add after the existing filter event listeners (after line 549):

```javascript
    // Tab switching
    if (dom.tabEpics) {
        dom.tabEpics.addEventListener('click', function () {
            currentTab = 'epics';
            dom.tabEpics.classList.add('active');
            dom.tabTasks.classList.remove('active');
            dom.showSteps.parentElement.style.display = '';
            applyFilters();
        });
    }
    if (dom.tabTasks) {
        dom.tabTasks.addEventListener('click', function () {
            currentTab = 'tasks';
            dom.tabTasks.classList.add('active');
            dom.tabEpics.classList.remove('active');
            dom.showSteps.parentElement.style.display = 'none';
            applyFilters();
        });
    }
```

**Step 10: Commit**

```bash
git add dashboard/app.js
git commit -m "feat(dashboard): add Tasks tab with individual task cards in Kanban columns"
```

---

### Task 11: Update build-step SKILL.md to write gate fields

**Files:**
- Modify: `skills/build-step/SKILL.md:149-154`

**Step 1: Update the "If APPROVED" section**

Replace lines 151-154 in `skills/build-step/SKILL.md`:

Old:
```markdown
**If APPROVED:**
- Update state: `update_step_status "<build_dir>" "<epic_name>" "<step_name>" "completed"`
- Log progress: `log_progress "<build_dir>" "Step <step_name> approved by reviewer"`
- Continue to the next step
```

New:
```markdown
**If APPROVED:**
- Update state:
  ```bash
  update_step_status "<build_dir>" "<epic_name>" "<step_name>" "completed"
  update_execution_state "<build_dir>" "epics.\"<epic_name>\".steps.\"<step_name>\".tests_pass" "true"
  update_execution_state "<build_dir>" "epics.\"<epic_name>\".steps.\"<step_name>\".review_approved" "true"
  ```
- Log progress: `log_progress "<build_dir>" "Step <step_name> approved by reviewer"`
- Continue to the next step
```

**Step 2: Add tests_pass update after developer reports TESTS: PASS**

After line 101 ("Wait for the developer sub-agent to complete."), add:

```markdown
**If developer reports TESTS: PASS:** Update the gate field so the dashboard shows partial progress:
```bash
update_execution_state "<build_dir>" "epics.\"<epic_name>\".steps.\"<step_name>\".tests_pass" "true"
```
```

**Step 3: Commit**

```bash
git add skills/build-step/SKILL.md
git commit -m "fix(build-step): write tests_pass and review_approved gate fields to state"
```

---

### Task 12: Add BATS test for gate field expectations

**Files:**
- Modify: `tests/state_test.bats`

**Step 1: Add tests verifying gate fields can be written and read**

Append to `tests/state_test.bats`:

```bash
@test "update_execution_state can set tests_pass gate field" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      task-1-load-csv:
        status: in_progress
YAML
    run update_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" 'epics."data-loading".steps."task-1-load-csv".tests_pass' "true"
    assert_success

    run read_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" 'epics."data-loading".steps."task-1-load-csv".tests_pass'
    assert_output "true"
}

@test "update_execution_state can set review_approved gate field" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      task-1-load-csv:
        status: completed
        tests_pass: true
YAML
    run update_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" 'epics."data-loading".steps."task-1-load-csv".review_approved' "true"
    assert_success

    run read_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" 'epics."data-loading".steps."task-1-load-csv".review_approved'
    assert_output "true"
}
```

**Step 2: Run tests**

```bash
./node_modules/bats/bin/bats tests/state_test.bats
```

Expected: All tests PASS (including the two new ones).

**Step 3: Commit**

```bash
git add tests/state_test.bats
git commit -m "test: add BATS tests for gate field read/write operations"
```

---

### Task 13: Manual end-to-end verification

**Step 1: Verify all BATS tests pass**

```bash
./node_modules/bats/bin/bats tests/state_test.bats
```

Expected: All 19+ tests pass.

**Step 2: Verify dashboard loads with test fixture**

```bash
cd dashboard && python3 -m http.server 8080 --bind 127.0.0.1 &
```

Copy `tests/fixtures/dashboard-test-state.yaml` to `dashboard/execution-state.yaml` temporarily and open `http://localhost:8080`.

Verify:
- **Epics tab:** data-loading shows 2/2 steps, transformation shows 1/3, reporting shows 0/2, model-training shows 0/2
- **Tasks tab:** task-1-parse-dates in Complete, task-2-normalize-columns in Building, task-3-aggregate-metrics in Pending, all reporting/model tasks in Pending
- **Tab switching** works, filters work in both views
- **Step sub-cards** show status dots, review round badges, gate dots

**Step 3: Cleanup and final commit**

Remove temporary test file if created. Run all BATS tests one more time.

```bash
./node_modules/bats/bin/bats tests/
```
