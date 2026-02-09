# ConnectHub Backend

FastAPI-based backend for the ConnectHub dating application. This project uses `uv` for dependency management and `arq` for asynchronous task processing.

## Prerequisites

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)** (Fast Python package installer and resolver)
- **Docker** (for PostgreSQL and Redis)

## Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd connecthub/connecthub_be
    ```

2.  **Install dependencies using `uv`:**

    ```bash
    uv sync
    ```

    This will create a virtual environment at `.venv` and install all required details from `pyproject.toml`.

3.  **Environment Configuration:**

    Copy the example environment file:

    ```bash
    cp .env.example .env
    ```

    Update the `.env` file with your database credentials, Redis URL, and other configuration settings.

## Running the Application

### 1. Start Infrastructure (Docker)

Ensure your PostgreSQL and Redis instances are running. You can use the provided `docker-compose.yml` if available (check project root) or run them individually.

```bash
docker compose up -d
```

### 2. Run Database Migrations

*Note: Add specific migration commands here if you are using Alembic, e.g., `uv run alembic upgrade head`.*

### 3. Start the API Server

Run the FastAPI server with hot-reloading enabled for development:

```bash
uv run uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive API docs: `http://localhost:8000/docs`.

### 4. Start the Async Worker (ARQ)

The application uses `arq` for background tasks (matching, notifications, etc.). To start the worker:

```bash
uv run arq app.workers.main.WorkerSettings
```

**Note:** The worker requires Redis to be running.

## Development

### Linting & Formatting

This project uses `ruff` for linting and formatting.

-   **Check code:**
    ```bash
    uv run ruff check .
    ```

-   **Format code:**
    ```bash
    uv run ruff format .
    ```

### Testing

Run the test suite using `pytest`:

```bash
uv run pytest
```

## Project Structure

-   `app/`: Main application code.
    -   `api/`: API endpoints and routers.
    -   `core/`: Core configuration, logging, and exceptions.
    -   `db/`: Database models and session management.
    -   `services/`: Business logic.
    -   `workers/`: ARQ worker tasks and settings.
-   `tests/`: Test suite.
