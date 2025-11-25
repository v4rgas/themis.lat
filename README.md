<p align="center">
  <img src="./themis-logo.svg" alt="Themis Logo" width="200" />
</p>

<h1 align="center">Themis</h1>

<p align="center">
  <strong>Automated exploration and auditing of suspicious public procurement in Chile</strong>
</p>

<p align="center">
  <a href="https://themis.lat">themis.lat</a>
</p>

---

## What is Themis?

Themis is an AI-powered platform that automatically analyzes public tenders from Chile's Mercado Público to detect:

- **Regulatory violations** - Non-compliance with procurement laws and regulations
- **Suspicious patterns** - Anomalies in award decisions and bidding behavior
- **Procurement irregularities** - Red flags in purchasing processes

Themis brings transparency to public spending by making it easy to investigate and audit government contracts.

## How it works

Themis uses a multi-agent AI system built with LangGraph that can:

1. **Fetch tender data** from Mercado Público's API
2. **Analyze documents** including contracts, specifications, and award decisions
3. **Detect anomalies** using specialized fraud detection agents
4. **Generate reports** summarizing findings and ranking issues by severity

## Tech Stack

**Frontend**
- React 19 + TypeScript + Vite
- Mosaic for data visualization
- Embedding Atlas for document exploration

**Backend**
- FastAPI + Python 3.13
- LangGraph + LangChain for AI orchestration
- PostgreSQL + SQLAlchemy
- Mistral AI for language processing

**Infrastructure**
- Docker & Docker Compose

## Getting Started

### Prerequisites

- Docker Desktop

### Environment Variables

Create a `backend/.env` file:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/postgres

ANTHROPIC_API_KEY=your-anthropic-api-key
MISTRAL_API_KEY=your-mistral-api-key
OPENROUTER_API_KEY=your-openrouter-api-key

LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=your-project-name

ADMIN_API_KEY=your-admin-key
DISCORD_WEBHOOK_URL=your-discord-webhook-url
```

### Run

```bash
docker compose up
```

## Team

Built by:

- **Víctor Tirreau** - [@viantirreau](https://github.com/viantirreau)
- **Ernesto Bernardo** - [@ignaciobernardo](https://github.com/ignaciobernardo)
- **Emerson Salazar** - [@emersoftware](https://github.com/emersoftware)
- **Juan Vargas** - [@v4rgas](https://github.com/v4rgas)
- **René Cáceres** - [@panquequelol](https://github.com/panquequelol)

## License

This project was created for the Platanus Hackathon 2024 and is open source.
