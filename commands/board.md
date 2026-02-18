---
description: "Launch the Kanban dashboard to visualize project progress."
disable-model-invocation: true
---

Launch the one-shot-build Kanban dashboard by running:

```bash
bash <plugin_root>/dashboard/serve.sh $(pwd) 8080
```

Then open http://localhost:8080 in your browser.

The dashboard reads kyros-agent-workflow/project-state.yaml and auto-refreshes every 5 seconds.
Use the filters to view by epic, status, or gate state.
