# Live E2E Tests

These tests call a live LLM (OpenAI or Azure OpenAI). Configuration is loaded from the project `.env` file via `config.loader`. An API key and a chat-capable model are required; see CONTRIBUTING.md for setup.

## Running the tests

Set the required variables in `.env` at the project root, then:

```bash
pytest tests/e2e/ -v -m live
```

### Example .env (placeholders only; do not commit real values)

```bash
# OpenAI
OPENAI_API_KEY=your-openai-key
LLM_MODEL=gpt-4o

# Azure OpenAI (use a deployment that supports chat completions)
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
# Optional: dedicated deployment for live tests
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
```

### Troubleshooting

- **DeploymentNotFound:** Set `AZURE_OPENAI_DEPLOYMENT_NAME` or `AZURE_OPENAI_CHAT_DEPLOYMENT` to the deployment name shown in the Azure portal.
- **OperationNotSupported / "does not work with the specified model":** The deployment is not a chat model. Set `AZURE_OPENAI_CHAT_DEPLOYMENT` (or `AZURE_OPENAI_DEPLOYMENT_NAME`) to a chat-capable deployment (e.g. `gpt-4o`).
