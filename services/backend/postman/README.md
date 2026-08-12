# Postman collection

Manual API testing for the backend. Free — a Postman account is optional; the
desktop app or the web app both import these files.

## Files

- `HerHealthGPT.postman_collection.json` — the requests.
- `HerHealthGPT.local.postman_environment.json` — sets `baseUrl` to
  `http://localhost:8000`. A staging environment is a copy with a different URL.

## Use it

1. **Start the API** against a local database:

   ```
   make db-up      # PostgreSQL in Docker (infra/compose.yml)
   make migrate    # apply migrations
   make serve      # http://localhost:8000
   ```

   (No `make` on Windows? Run the command each target prints — see the Makefile.)

2. **Import** both files: Postman → Import → drop them in.

3. **Select** the "HerHealthGPT — local" environment (top-right), open
   **Health → Health check**, and Send. You should get `200` and
   `{"status":"ok"}`; the request's Tests tab asserts both.

Stop the database with `make db-down` when you are done.

## Extending it

Every new endpoint gets a request here, grouped in a folder per area (Health,
Registering, Verifying, …), mirroring the Accounts user stories. Keep `baseUrl`
as an environment variable so the same collection runs against staging.
