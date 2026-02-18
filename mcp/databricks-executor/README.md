# Databricks Executor MCP Server

MCP server that exposes Databricks operations for the one-shot-build harness.

## Tools

| Tool | Description |
|------|-------------|
| `execute_code` | Run Python/SQL on a Databricks cluster |
| `cluster_status` | Check cluster state |
| `start_cluster` | Start a terminated cluster |
| `upload_file` | Upload to DBFS |
| `download_file` | Download from DBFS |
| `list_tables` | List tables in a catalog/schema |

## Configuration

Set in your project's `kyros-agent-workflow/.harnessrc`:

```yaml
databricks:
  workspace_url: "https://adb-xxxx.azuredatabricks.net"
  cluster_id: "xxxx-xxxxxx-xxxxxxxx"
  default_catalog: "main"
  default_schema: "client_xyz"
  token_env_var: "DATABRICKS_TOKEN"
```

## Setup

```bash
pip install -r requirements.txt
export DATABRICKS_TOKEN="your-token"
```
