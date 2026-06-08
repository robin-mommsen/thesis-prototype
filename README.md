# Upcycling RAG Prototype

A FastAPI backend prototype built for a bachelor's thesis, comparing **RAG-augmented generation** against a **baseline** (no retrieval) for generating DIY upcycling solutions.

The system retrieves domain-specific upcycling factsheets via vector similarity search and injects them as context into the Claude prompt. The research question: does factsheet-based RAG improve solution quality, and how does input specificity affect this?

## Architecture

```
User Input
    │
    ├─── no-rag ──► System Prompt + User Input ──► Claude ──► Response
    │
    └─── rag ─────► Embed Input ──► pgvector Search ──► Top-5 Factsheets
                          └──► System Prompt + Factsheets + User Input ──► Claude ──► Response
```

**Stack:**
- **FastAPI** — REST API with OpenAI-compatible `/v1/chat/completions` endpoint
- **PostgreSQL + pgvector** — vector database for factsheet storage and cosine similarity search
- **Ollama** (`nomic-embed-text-v2-moe`) — local embedding model (768 dimensions)
- **Claude API** (Anthropic) — LLM for response generation
- **LibreChat** — optional chat UI (connects to the backend as a custom API)

## Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/)
- An [Anthropic API key](https://console.anthropic.com/)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/robin-mommsen/thesis-prototype
cd thesis-prototype
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
POSTGRES_USER=raguser
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=ragdb

CLAUDE_API_KEY=your_anthropic_api_key_here
CLAUDE_MODEL=claude-sonnet-4-6
RAG_FACTSHEET_LIMIT=5

LIBRECHAT_JWT_SECRET=your_random_secret
LIBRECHAT_JWT_REFRESH_SECRET=your_random_refresh_secret
LIBRECHAT_CREDS_KEY=your_64_char_hex_string
LIBRECHAT_CREDS_IV=your_32_char_hex_string
```

The LibreChat secrets are required — the container will not start without them. Generate them with Python:

```bash
# JWT_SECRET and JWT_REFRESH_SECRET (any random string, min. 32 chars)
python -c "import secrets; print(secrets.token_hex(32))"

# CREDS_KEY (exactly 64 hex chars)
python -c "import secrets; print(secrets.token_hex(32))"

# CREDS_IV (exactly 32 hex chars)
python -c "import secrets; print(secrets.token_hex(16))"
```

Run each command once and paste the output into the corresponding variable in `.env`.

### 3. Start the system

```bash
docker compose up --build
```

On first start, Docker will:
1. Start PostgreSQL with the pgvector extension
2. Run the DB initialization SQL scripts (`db/`)
3. Start Ollama and pull the embedding model (`nomic-embed-text-v2-moe:latest`) — this may take a few minutes
4. Start the FastAPI backend, which seeds the factsheet database on startup
5. Start MongoDB and LibreChat (optional UI)

Once all services are healthy, the API is available at `http://localhost:8080`.

## API Usage

### Generate a upcycling idea

**RAG mode** (retrieves relevant factsheets):

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rag",
    "messages": [{"role": "user", "content": "Ich habe zwei alte Europaletten. Was kann ich daraus bauen?"}]
  }'
```

**Baseline mode** (no retrieval):

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "no-rag",
    "messages": [{"role": "user", "content": "Ich habe zwei alte Europaletten. Was kann ich daraus bauen?"}]
  }'
```

The `model` field selects the mode: `"rag"` or `"no-rag"`.

**Streaming** is also supported:

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "rag", "stream": true, "messages": [{"role": "user", "content": "alte Holzbretter"}]}'
```

### Factsheet endpoints

```bash
# List all factsheets
GET http://localhost:8080/factsheets

# Get a single factsheet
GET http://localhost:8080/factsheet/{id}

# Add a new factsheet
POST http://localhost:8080/factsheet

# Update a factsheet
PUT http://localhost:8080/factsheet/{id}

# Delete a factsheet
DELETE http://localhost:8080/factsheet/{id}
```

### Available models

```bash
GET http://localhost:8080/v1/models
```

Returns `rag` and `no-rag` as available model IDs.

## LibreChat UI (optional)

LibreChat is included as a browser-based chat frontend. After `docker compose up`, it is available at `http://localhost:3080`.

To connect it to the RAG backend:
1. Open LibreChat in your browser and create a local account
2. The backend is pre-configured via `librechat.yaml` as a custom API endpoint
3. Select `rag` or `no-rag` as the model in the UI

## Running the Research Experiment

The experiment runs all 24 test prompts (`experiments/test_inputs.json`) against both modes and saves results to `experiments/results/`.

### Requirements

Install Python dependencies (outside Docker):

```bash
pip install -r requirements.txt
```

### 1. Run the experiment

Make sure the Docker stack is running, then:

```bash
python experiments/run_experiment.py
```

This generates a timestamped JSON file in `experiments/results/`, e.g. `experiment_20240115_120000.json`.

Failed generations are automatically retried (up to 10 attempts per prompt/mode).

### 2. Generate rater scoring sheets

```bash
python experiments/evaluate.py experiments/results/experiment_<timestamp>.json
```

This produces:
- `experiment_<timestamp>.xlsx` — master file with the anonymization mapping (stays with the researcher)
- `experiment_<timestamp>_rater_1.xlsx` to `_rater_4.xlsx` — anonymized scoring sheets for human raters, each in a different randomized order

Raters score each response across 4 criteria:
- Task fit
- Material integration
- Feasibility
- Creativity

### 3. Aggregate rater scores

After all raters have filled in their sheets:

```bash
python experiments/aggregate_rater_scores.py \
  --master experiment_<timestamp>.xlsx \
  experiment_<timestamp>_rater_1.xlsx \
  experiment_<timestamp>_rater_2.xlsx \
  experiment_<timestamp>_rater_3.xlsx \
  experiment_<timestamp>_rater_4.xlsx
```

This produces `aggregated_rater_scores.xlsx` with per-response means across raters, condition means (RAG vs. baseline), Krippendorff's alpha per criterion, and Wilcoxon signed-rank test results comparing RAG against baseline per criterion.

## Environment Variables Reference

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_USER` | PostgreSQL username | — |
| `POSTGRES_PASSWORD` | PostgreSQL password | — |
| `POSTGRES_DB` | PostgreSQL database name | — |
| `CLAUDE_API_KEY` | Anthropic API key | — |
| `CLAUDE_MODEL` | Claude model ID | `claude-sonnet-4-6` |
| `RAG_FACTSHEET_LIMIT` | Number of factsheets retrieved per query | `5` |
| `LIBRECHAT_JWT_SECRET` | LibreChat JWT signing secret | — |
| `LIBRECHAT_JWT_REFRESH_SECRET` | LibreChat JWT refresh secret | — |
| `LIBRECHAT_CREDS_KEY` | LibreChat credentials encryption key (64 hex chars) | — |
| `LIBRECHAT_CREDS_IV` | LibreChat credentials encryption IV (32 hex chars) | — |

## Reproducibility Note

The embedding model (`nomic-embed-text-v2-moe:latest`) has no versioned tags on the Ollama registry. To verify you are using the same model version as the original experiment, check the model hash after first startup:

```bash
docker exec upcycling-rag-ollama ollama list
```

The model hash used for the thesis experiment: `ff9c2f10ef5e`

## Project Structure

```
.
├── app/
│   ├── main.py                  # FastAPI app, startup
│   ├── routers/
│   │   ├── chat.py              # /v1/chat/completions endpoint
│   │   ├── factsheet.py         # Factsheet CRUD
│   │   └── models.py            # /v1/models
│   ├── services/
│   │   ├── rag_service.py       # Core RAG and baseline logic, system prompt
│   │   ├── claude_service.py    # Anthropic API wrapper
│   │   ├── embedding_service.py # Ollama embeddings
│   │   └── data_initializer.py  # Seeds factsheets on startup
│   ├── models/
│   │   ├── upcycling_factsheet.py
│   │   └── query_log.py
│   └── config/
│       ├── config.py
│       └── database.py
├── db/                          # PostgreSQL init scripts
├── experiments/                 # Experiment runner and evaluation scripts
│   ├── run_experiment.py
│   ├── evaluate.py
│   ├── aggregate_rater_scores.py
│   └── test_inputs.json         # 24 prompts (8 vague, 8 medium, 8 concrete)
├── docker-compose.yml
├── Dockerfile
└── .env.example
```
