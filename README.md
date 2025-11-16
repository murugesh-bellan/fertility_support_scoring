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
# Using the demo script (recommended)
bash demo.sh

# Or test manually with curl
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{"message": "Another negative test today. Feeling really sad."}'
```

## Development Environment Setup

### Enable Development Mode

To enable the dashboard and additional development features, set the environment to `dev` in your `.env` file:

```bash
ENVIRONMENT=dev
```

**Important**: Development mode enables CORS for local dashboard access. For production deployments, set `ENVIRONMENT=production` to disable CORS.

### Using the Interactive Dashboard

The project includes a web-based dashboard (`dashboard.html`) for testing and monitoring in development mode.

#### Starting the Dashboard

1. Ensure the server is running in dev mode:
   ```bash
   # Make sure ENVIRONMENT=dev in your .env file
   uv run uvicorn main:app --reload
   ```

2. Open the dashboard:
   ```bash
   # Simply open the file in your browser
   open dashboard.html
   # Or drag dashboard.html to your browser
   ```

#### Dashboard Features

**Real-time Monitoring:**
- System health status (API, Bedrock, Cache)
- Live request metrics (total requests, avg latency, avg tokens)
- Security monitoring (injection attempts, errors, success rate)
- Auto-refresh every 5 seconds

**Interactive Testing:**
The dashboard includes 11 pre-configured test cases from `demo.sh`:

| Button | Category | Description |
|--------|----------|-------------|
| 🚨 Crisis | Score 10 | Emergency/suicidal ideation |
| 😢 High Distress | Score 8-9 | Severe emotional distress |
| 📝 Normal | Score 6-7 | Moderate concern |
| 😊 Positive | Score 1-2 | Positive/hopeful message |
| 🤔 Young & Uncertain | Score 3-5 | First-time IVF, uncertain |
| 😰 Cultural Pressure | Score 6-7 | Family/cultural stress |
| 💬 Gender Pronoun | Score 2-3 | Partner communication |
| ❌ Out of Domain | Score -1 | Non-fertility related |
| 🛡️ Injection Attack | Security | Prompt injection attempt |
| ⚠️ Privacy Breach | Security | Data access attempt |
| 🎭 Pretend Attack | Security | Role-play attack |

**Testing Workflow:**
1. Click any example button to load a test message
2. Click "Score Message" to analyze
3. View detailed results including:
   - Emotional distress score (1-10)
   - Confidence level
   - Reasoning and key indicators
   - Recommended action
   - Performance metrics (latency, tokens)
   - Security alerts (if injection detected)

#### Running Automated Tests

For comprehensive testing, use the included demo script:

```bash
# Run all 11 test cases
bash demo.sh

# View specific test categories:
# - Normal emotional distress (scores 1-10)
# - Out-of-domain detection
# - Security/injection attempts
# - Cultural sensitivity tests
```

### Environment Variables for Development

Key development settings in `.env`:

```bash
# Environment (dev enables CORS for dashboard)
ENVIRONMENT=dev

# Logging (set to DEBUG for verbose output)
LOG_LEVEL=INFO

# LangSmith tracing (optional, for debugging)
LANGSMITH_API_KEY=your_key_here
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=fertility-support-agent

# Rate limiting (adjust for testing)
RATE_LIMIT_PER_MINUTE=60
```

### Switching to Production

To deploy in production mode:

1. Update `.env`:
   ```bash
   ENVIRONMENT=production
   LOG_LEVEL=WARNING
   ```

2. CORS will be automatically disabled
3. Dashboard will not work (as intended for security)
4. Use API endpoints directly or build a production frontend

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
fertility-support-scoring/
├── main.py                 # FastAPI server
├── dashboard.html          # Interactive web dashboard (dev mode)
├── demo.sh                 # Automated test script
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
