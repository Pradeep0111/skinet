# Skinet Shopping AI

Internal FastAPI service for the Skinet shopping assistant. Browser traffic must go through
the ASP.NET gateway; this service does not accept Identity cookies, access SQL Server, or
write shopping carts.

## Implemented scope

- FastAPI application factory and `/health` endpoint
- environment-based settings with safe defaults
- request IDs and structured request logging without bodies or query strings
- camelCase product/chat contracts backed by JSON fixtures
- deterministic mock LLM provider for independent development
- pytest and Ruff configuration
- configurable async Claude provider using the official Anthropic SDK
- memory and Redis conversation stores with bounded history, typed product references, and a
  24-hour default TTL
- protected `POST /api/chat` endpoint with safe errors and strict request validation
- rejection of unknown fields so PII cannot silently enter the AI service contract
- async, service-authenticated .NET catalog client using the current Pydantic-maintained HTTPX2
  package, with strict paginated response validation
- read-only keyword search, product-details, and current-stock tools for Week 4 orchestration
- mocked HTTP coverage for catalog filters, pagination, upstream failures, and contract failures
- deterministic LangGraph routing for search, details, stock, comparison, and substitutions
- deterministic follow-ups such as `Compare those` and `Add the first one to cart`, resolved only
  from ordered product IDs produced by the most recent validated response
- confirmation-only `add_to_cart` proposals that re-check current stock but never mutate a cart
- cart-aware stock validation that includes quantities already supplied by the trusted ASP.NET
  gateway
- bounded end-to-end chat processing, strict pagination checks, safe Redis-corruption recovery,
  and non-retryable catalog credential/contract errors
- an explicit tool allowlist with no cart-write, order, payment, or admin operation
- opt-in Week 7 hybrid retrieval using a content-hashed catalog snapshot, local embeddings,
  in-memory FAISS cosine search, deterministic reciprocal-rank fusion, and live price/stock filters
- inclusive price constraints such as `boots under $200`, with keyword-only fallback whenever the
  embedding model, FAISS, or complete-catalog snapshot is unavailable

The .NET catalog endpoint, Python catalog client, and graph-backed gateway flow have passed the
joint A-G live database test. Gate 1 and the functional Gate 2 slice are complete; canonical shared
fixtures and release hardening remain open.

The independently testable Python portion of Week 6 covers the protected route, catalog boundary,
conversation storage, service credentials, request IDs, production settings, and failure responses.

Contextual routing never parses prior user or assistant prose and never sends the stored transcript
to an LLM. Explicit product IDs in the current request take precedence, ambiguous references are
clarified, and contextual product IDs are always re-fetched from the live catalog. The ASP.NET
gateway must issue an opaque, unpredictable conversation ID per browser/user session before this
is production-ready; clients must not choose or share conversation IDs.

## Local setup with uv

Install [uv](https://docs.astral.sh/uv/) first. `uv` can install Python 3.12, create the
project virtual environment, and synchronize development dependencies.

```powershell
cd shopping-ai
uv python install 3.12
uv venv --python 3.12
uv sync --extra dev
Copy-Item .env.example .env
```

Activation is optional because `uv run` automatically uses `.venv`. To activate it manually,
run `.\.venv\Scripts\Activate.ps1`. Keep `LLM_PROVIDER=mock` for deterministic local development
unless you intentionally want to call Claude. Never commit `.env` or API keys.

Set a local-only `INTERNAL_SERVICE_KEY` before calling `/api/chat`. The default
`CONVERSATION_BACKEND=memory` requires no infrastructure. To exercise Redis storage, change it to
`redis` and ensure the Skinet Redis service is running. To use Claude instead of the deterministic
mock, set `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_MODEL`.

## Run and verify

```powershell
uv run uvicorn app.main:app --reload --reload-dir app --port 8000
Invoke-RestMethod http://localhost:8000/health
uv run pytest
uv run ruff check .
```

Week 7 semantic search is optional so ordinary development does not download an ML model. Install
and enable it explicitly:

```powershell
uv sync --extra dev --extra semantic
$env:SEMANTIC_SEARCH_ENABLED = "true"
uv run uvicorn app.main:app --reload --reload-dir app --port 8000
```

The model loads lazily on the first search and is cached under `.data/embedding-models`. The FAISS
index remains in memory and rebuilds only when searchable catalog content changes. Price and stock
are deliberately excluded from the embedding hash and are taken from the current .NET response;
cart proposals continue to re-fetch the product before returning an action.

After pre-caching the model, set `EMBEDDING_LOCAL_FILES_ONLY=true` to prevent Hugging Face metadata
requests in an offline environment. Staging and production additionally require
`EMBEDDING_REVISION` to be the model's immutable 40-character commit SHA; a mutable label such as
`main`, a missing revision, or a non-local model policy fails configuration validation.

Expected health response:

```json
{"status":"ok","service":"skinet-shopping-ai","version":"0.1.0"}
```

The .NET development API is configured as `https://localhost:5000`, matching the existing
Skinet launch profile. `DOTNET_SERVICE_KEY` is sent only in the
`X-Assistant-Service-Key` header. Keep `DOTNET_VERIFY_TLS=true`; set it to `false` only for a local
self-signed development certificate. The current ASP.NET implementation uses one
`Assistant:ServiceKey` in both directions, so local integration requires `INTERNAL_SERVICE_KEY`
and `DOTNET_SERVICE_KEY` to contain that same value. Staging and production require service keys
of at least 16 non-whitespace characters, Redis conversation storage, and verified HTTPS.
`CHAT_TIMEOUT_SECONDS` defaults to 20 seconds, below the current 30-second ASP.NET gateway timeout.

`--reload-dir app` prevents Uvicorn from watching `.venv`, test caches, and other project files.
Without it, installing dependencies while the server is running can trigger repeated reloads.

Test the protected mock chat endpoint from PowerShell:

```powershell
$headers = @{ "X-Assistant-Service-Key" = "your-local-secret" }
$body = @{ message = "Show me boots" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/chat `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

The header value must match `INTERNAL_SERVICE_KEY` in the untracked `.env` file.

## Joint integration handoff

The public request continues to go to ASP.NET at `POST /api/Assistant/chat` and contains only
`message`, optional `conversationId`, and optional `cartId`. ASP.NET builds trusted `cart.items`
and `shopper.preferences` context, then calls this service at `POST /api/chat`. Python reads the
catalog from ASP.NET at `GET /api/assistant/catalog` using `pageIndex`, `pageSize`, `search`, and
the existing filter query names.

The Week 6 joint run covered search, details, stock, comparison, substitution, contextual follow-up,
cart proposals, invalid service keys, stopped FastAPI behavior, preserved conversation IDs, and no
cart mutation. After Week 7, repeat one semantic search such as `outdoor footwear under $200`
through ASP.NET. Python intentionally accepts the currently omitted `storageInstructions` and
`shelfLifeDays` fields as `null`; their authoritative projection remains .NET-owned.

## Contract handoff

Files under `tests/fixtures/` are the AI-side Gate 0 proposal. The .NET developer must review
them against `dotnet_plan.md`, then publish the accepted canonical fixtures under
`skinet/docs/contracts/`. After acceptance, changes require coordination between both tracks.
