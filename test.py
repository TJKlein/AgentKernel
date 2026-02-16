import os
from openai import AzureOpenAI

from dotenv import load_dotenv

load_dotenv()

# Make sure these environment variables are set:
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION")

if not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION]):
    raise ValueError("Missing Azure OpenAI configuration in .env file")

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

# Try a simple test prompt using your deployment
deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5.1-codex-mini")

response = client.chat.completions.create(
    model=deployment_name,
    messages=[
        {"role": "user", "content": "Write a simple Python function that adds two numbers."}
    ]
)

print("Response:")
print(response.choices[0].message.content)
