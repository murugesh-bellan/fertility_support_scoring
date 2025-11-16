# Fertility Support Agent 🤖💚

An agentic AI system that analyzes text messages from women undergoing fertility treatment, scores emotional distress (1-10), and triggers appropriate interventions.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Server                       │
│  POST /score    GET /health    GET /metrics             │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Scoring Agent (LangGraph)                   │
│  1. Domain Validator → Check relevance                   │
│  2. Emotional Analyzer → Score distress (1-10)           │
│  3. Action Router → Determine intervention               │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│         Bedrock LLM (via HolisticAI Proxy)              │
│              Claude 3.5 Sonnet                           │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Observability Layer                         │
│  LangSmith • Structured Logs • Prometheus Metrics        │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install dependencies
```bash
# Using uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Run the server
```bash
uv run uvicorn main:app --reload
```

### 4. Test the API
```bash
# Normal message
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{"message": "Another negative test today. Feeling really sad."}'

# Crisis message
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{"message": "I cannot do this anymore. There is no point."}'

# Out-of-domain
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather today?"}'
```

## API Endpoints

### POST /score
Score a message for emotional distress.

**Request:**
```json
{
  "message": "string"
}
```

**Response:**
```json
{
  "score": 8,
  "confidence": 0.87,
  "domain_match": true,
  "reasoning": "Message expresses hopelessness after failed treatment...",
  "key_indicators": ["hopelessness", "failed treatment"],
  "recommended_action": "book_gp_appointment",
  "action_rationale": "Score 8 requires soonest GP appointment",
  "trace_id": "langsmith-trace-url",
  "latency_ms": 1234,
  "tokens_used": 450
}
```

### GET /health
Health check with system status.

### GET /metrics
Prometheus metrics endpoint.

## Scoring Logic

- **Score 10**: Emergency alert (crisis intervention)
- **Score 8-9**: Book soonest GP appointment
- **Score 6-7**: Notify caretaker to provide support
- **Score 1-5**: Log for monitoring, no immediate action
- **Score -1**: Out-of-domain message

## Security Features

- Input validation and sanitization
- Prompt injection detection
- Rate limiting (60 req/min default)
- Max message length (2000 chars)
- Structured security logging

## Performance

- **Latency**: p95 < 3s
- **Caching**: Reduces repeat requests by 90%
- **Cost**: ~$0.003 per request
- **Tokens**: ~400 per request (optimized)

## Development

### Run tests
```bash
uv run pytest
```

### Format code
```bash
uv run ruff format .
```

### Lint
```bash
uv run ruff check .
```

## Project Structure

```
fertility-support-agent/
├── main.py                 # FastAPI server
├── agent/
│   ├── graph.py           # LangGraph agent
│   ├── prompts.py         # Prompt templates
│   └── tools.py           # Helper functions
├── models/
│   ├── bedrock.py         # HolisticAI Bedrock client
│   └── schemas.py         # Pydantic models
├── security/
│   ├── injection.py       # Injection detection
│   └── validation.py      # Input validation
├── observability/
│   ├── logging.py         # Structured logging
│   └── metrics.py         # Prometheus metrics
└── tests/
    ├── test_agent.py
    ├── test_dataset.json
    └── test_attacks.py
```
