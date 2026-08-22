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

The .NET catalog endpoint and Python catalog client are implemented, with live Gate 1 contract
verification still pending. Week 5 connects the registered LangGraph workflow to `/api/chat`, so
searches, comparisons, substitutions, stock checks, and confirmation-only proposed actions now
flow through the protected endpoint. Full ASP.NET-to-FastAPI response and failure-path verification
remains a joint Gate 2 task.

The independently testable Python portion of Week 6 covers the protected route, catalog boundary,
conversation storage, service credentials, request IDs, production settings, and failure responses.
Gate 2 is not complete until the same cases pass through the live ASP.NET gateway and real catalog.

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

## Joint Week 6 handoff

The public request continues to go to ASP.NET at `POST /api/Assistant/chat` and contains only
`message`, optional `conversationId`, and optional `cartId`. ASP.NET builds trusted `cart.items`
and `shopper.preferences` context, then calls this service at `POST /api/chat`. Python reads the
catalog from ASP.NET at `GET /api/assistant/catalog` using `pageIndex`, `pageSize`, `search`, and
the existing filter query names.

Before Gate 2 is approved, run search, details, stock, comparison, substitution, contextual
follow-up, and cart-proposal cases through the live ASP.NET gateway. Also verify invalid service
keys, a stopped FastAPI process, catalog timeouts, malformed downstream responses, and preserved
conversation IDs. Python intentionally accepts the currently omitted `storageInstructions` and
`shelfLifeDays` fields as `null`; their authoritative projection remains .NET-owned.

## Contract handoff

Files under `tests/fixtures/` are the AI-side Gate 0 proposal. The .NET developer must review
them against `dotnet_plan.md`, then publish the accepted canonical fixtures under
`skinet/docs/contracts/`. After acceptance, changes require coordination between both tracks.
