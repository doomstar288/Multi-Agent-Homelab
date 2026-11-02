Put one API key per file here (these files are git-ignored):

- `claude_api_key`
- `gemini_api_key`
- `grok_api_key`

An empty file is fine for a provider you haven't set up yet. The container runs as
UID 10001, so make the files readable by it and nobody else:

    sudo chown 10001:10001 secrets/*_api_key && sudo chmod 400 secrets/*_api_key
