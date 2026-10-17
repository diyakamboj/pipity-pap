# Azure AI Search MCP Integration

This integration provides access to Azure AI Search indexes, allowing the agent to perform semantic, hybrid, and text searches across your enterprise data.

## Configuration

You need to provide the following environment variables:

1. **AZURE_SEARCH_ENDPOINT**: The URL of your Azure AI Search service (e.g., `https://<service-name>.search.windows.net`).
2. **AZURE_SEARCH_INDEX**: The name of the index you want to query.
3. **AZURE_SEARCH_API_KEY**: A valid API key for your Azure AI Search service. It is highly recommended to use a **Query Key** (read-only) rather than an Admin Key.

## Features

- **Semantic Search**: Understands the intent behind queries for better results.
- **Hybrid Search**: Combines keyword and semantic search.
- **Schema Discovery**: Allows the agent to automatically understand the structure of your index.

*Powered by `tomgutt/azure-ai-search-mcp`*
