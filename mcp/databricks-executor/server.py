"""
Databricks Executor MCP Server
Exposes Databricks operations as MCP tools for the one-shot-build harness.
Reads configuration from .harnessrc in the current project directory.
"""

import os
import yaml
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.compute import State

app = Server("databricks-executor")


def load_config() -> dict:
    """Load Databricks config from .harnessrc."""
    harnessrc = Path.cwd() / ".harnessrc"
    if not harnessrc.exists():
        raise FileNotFoundError("No .harnessrc found. Run /init first.")
    with open(harnessrc) as f:
        config = yaml.safe_load(f)
    return config.get("databricks", {})


def get_client(config: dict) -> WorkspaceClient:
    """Create authenticated Databricks client."""
    token_var = config.get("token_env_var", "DATABRICKS_TOKEN")
    token = os.environ.get(token_var)
    if not token:
        raise ValueError(f"Environment variable {token_var} not set")
    return WorkspaceClient(
        host=config["workspace_url"],
        token=token,
    )


@app.tool()
async def execute_code(code: str, language: str = "python") -> list[TextContent]:
    """Execute a code snippet on the configured Databricks cluster.
    Returns the output of the execution."""
    config = load_config()
    client = get_client(config)
    cluster_id = config["cluster_id"]

    # Ensure cluster is running
    cluster = client.clusters.get(cluster_id)
    if cluster.state != State.RUNNING:
        client.clusters.start(cluster_id).result()

    # Execute via command API
    context = client.command.create(
        cluster_id=cluster_id,
        language=language,
        command=code,
    ).result()

    output = context.results.data if context.results else "No output"
    return [TextContent(type="text", text=str(output))]


@app.tool()
async def cluster_status() -> list[TextContent]:
    """Check the status of the configured Databricks cluster."""
    config = load_config()
    client = get_client(config)
    cluster = client.clusters.get(config["cluster_id"])
    return [TextContent(
        type="text",
        text=f"Cluster: {cluster.cluster_name}\nState: {cluster.state.value}\nID: {config['cluster_id']}",
    )]


@app.tool()
async def start_cluster() -> list[TextContent]:
    """Start the configured Databricks cluster if it's terminated."""
    config = load_config()
    client = get_client(config)
    cluster_id = config["cluster_id"]
    cluster = client.clusters.get(cluster_id)

    if cluster.state == State.RUNNING:
        return [TextContent(type="text", text="Cluster is already running.")]

    client.clusters.start(cluster_id).result()
    return [TextContent(type="text", text=f"Cluster {cluster_id} started successfully.")]


@app.tool()
async def upload_file(local_path: str, dbfs_path: str) -> list[TextContent]:
    """Upload a local file to DBFS."""
    config = load_config()
    client = get_client(config)
    with open(local_path, "rb") as f:
        client.dbfs.put(dbfs_path, f, overwrite=True)
    return [TextContent(type="text", text=f"Uploaded {local_path} to {dbfs_path}")]


@app.tool()
async def download_file(dbfs_path: str, local_path: str) -> list[TextContent]:
    """Download a file from DBFS to local filesystem."""
    config = load_config()
    client = get_client(config)
    with open(local_path, "wb") as f:
        for chunk in client.dbfs.read(dbfs_path).data:
            f.write(chunk)
    return [TextContent(type="text", text=f"Downloaded {dbfs_path} to {local_path}")]


@app.tool()
async def list_tables(catalog: str = "", schema: str = "") -> list[TextContent]:
    """List tables in a Databricks catalog/schema for data discovery."""
    config = load_config()
    client = get_client(config)
    cat = catalog or config.get("default_catalog", "main")
    sch = schema or config.get("default_schema", "default")
    tables = client.tables.list(catalog_name=cat, schema_name=sch)
    table_list = "\n".join(f"- {t.full_name}" for t in tables)
    return [TextContent(type="text", text=f"Tables in {cat}.{sch}:\n{table_list}")]


if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run())
