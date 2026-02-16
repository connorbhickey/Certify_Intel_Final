# PostgreSQL Migration Guide

Migrate Certify Intel from SQLite (development) to PostgreSQL 16 + pgvector (production).

---

## Prerequisites

- **Docker Desktop** (Windows/macOS) or Docker Engine (Linux)
- **Python 3.9+** with the backend virtual environment
- **psycopg2-binary** and **asyncpg** Python packages (for PostgreSQL connectivity)

Install the required Python packages:

```bash
cd backend
.\venv\Scripts\Activate.ps1   # Windows
# source venv/bin/activate    # macOS/Linux

pip install psycopg2-binary asyncpg
```

---

## Step 1: Start PostgreSQL with Docker Compose

From the project root:

```bash
docker compose -f docker-compose.postgres.yml up -d
```

This starts PostgreSQL 16 with the pgvector extension on port 5432.

Verify it is running:

```bash
docker compose -f docker-compose.postgres.yml ps
```

You should see the `certify_intel_postgres` container with status `healthy`.

**Default credentials** (change for production):

| Setting | Value |
|---------|-------|
| Host | localhost |
| Port | 5432 |
| Database | certify_intel |
| Username | certify_intel |
| Password | certify_intel_password |

Connection string:
```
postgresql://certify_intel:certify_intel_password@localhost:5432/certify_intel
```

---

## Step 2: Run the Migration Script

The migration script reads the SQLite database and copies all data to PostgreSQL with proper type conversion.

```bash
cd [PROJECT_ROOT]/

# Activate the backend venv
backend\venv\Scripts\Activate.ps1

# Run migration with defaults
python scripts/migrate_sqlite_to_postgres.py
```

**Custom paths** (if your database or PostgreSQL are non-standard):

```bash
# Override PostgreSQL URL
set DATABASE_URL=postgresql://user:pass@host:5432/dbname
python scripts/migrate_sqlite_to_postgres.py

# Override SQLite path
set SQLITE_PATH=C:\path\to\certify_intel.db
python scripts/migrate_sqlite_to_postgres.py
```

The script will:
1. Connect to SQLite and enumerate all tables
2. Read ORM model definitions for type mapping
3. Create tables in PostgreSQL (drops existing tables first)
4. Migrate all data with type conversion (Boolean, DateTime, JSON)
5. Verify row counts match between SQLite and PostgreSQL

**Expected output:**

```
=== Certify Intel - SQLite to PostgreSQL Migration ===
[1/5] Connecting to SQLite...
  Found 30 tables in SQLite
[2/5] Reading ORM model definitions...
  Found 30 ORM-defined tables
[3/5] Creating PostgreSQL tables...
  PostgreSQL connection verified
  Created 30 tables
[4/5] Migrating data...
  competitors: 82/82 rows
  users: 3/3 rows
  ...
  Total: ~5000 rows migrated in 2.3s
[5/5] Verifying migration...
  All table row counts match.
Migration complete!
```

---

## Step 3: Configure the Application

Update `backend/.env` to use PostgreSQL:

```env
# PostgreSQL connection (uncomment to switch from SQLite)
DATABASE_URL=postgresql://certify_intel:certify_intel_password@localhost:5432/certify_intel
```

The application detects the `DATABASE_URL` environment variable automatically:
- If it starts with `postgresql://`, the PostgreSQL engine is used with connection pooling
- If absent or starts with `sqlite://`, the SQLite engine is used (default for development)

### Pool Settings (Optional)

These environment variables tune the connection pool. Defaults are suitable for most deployments:

```env
DB_POOL_SIZE=10          # Base number of persistent connections
DB_MAX_OVERFLOW=20       # Extra connections allowed under load
DB_POOL_TIMEOUT=30       # Seconds to wait for a connection
DB_ECHO=false            # Set to "true" to log all SQL queries
```

---

## Step 4: Start the Application

```bash
cd backend
python main.py
```

Open http://localhost:8000 and verify:
- Login works (`[YOUR-ADMIN-EMAIL]` / `[YOUR-ADMIN-PASSWORD]`)
- Competitors load on the dashboard
- News feed displays articles
- Discovery Scout runs successfully

---

## Step 5: Verify the pgvector Tables

The Docker init script creates the `knowledge_documents` and `document_chunks` tables with pgvector support. These are used by the RAG pipeline for semantic search.

Connect to PostgreSQL and check:

```bash
docker exec -it certify_intel_postgres psql -U certify_intel -d certify_intel

# Verify pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';

# Check tables
\dt

# Check vector index
\di document_chunks_embedding_idx

# Exit
\q
```

---

## Switching Back to SQLite

To revert to SQLite, simply remove or comment out the `DATABASE_URL` line in `backend/.env`:

```env
# DATABASE_URL=postgresql://certify_intel:certify_intel_password@localhost:5432/certify_intel
```

Restart the backend and it will use `backend/certify_intel.db` again.

---

## Stopping PostgreSQL

```bash
# Stop containers (data persists in Docker volume)
docker compose -f docker-compose.postgres.yml down

# Stop AND delete all data
docker compose -f docker-compose.postgres.yml down -v
```

---

## Cloud Deployment Options

### AWS RDS for PostgreSQL

1. Create an RDS PostgreSQL 16 instance with the `pgvector` extension enabled
2. Use the RDS endpoint as your `DATABASE_URL`:
   ```
   DATABASE_URL=postgresql://username:password@your-instance.rds.amazonaws.com:5432/certify_intel
   ```
3. Run the migration script against the RDS endpoint
4. Enable RDS automated backups and Multi-AZ for production

### Google Cloud SQL

1. Create a Cloud SQL PostgreSQL 16 instance
2. Enable the `pgvector` extension via Cloud Console or SQL:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Use the Cloud SQL connection string with Cloud SQL Proxy or direct IP
4. Run the migration script

### Azure Database for PostgreSQL

1. Create a Flexible Server with PostgreSQL 16
2. Enable the `pgvector` extension in Server Parameters
3. Use the Azure connection string as `DATABASE_URL`
4. Run the migration script

### Docker on VPS (DigitalOcean, Linode, etc.)

1. Copy `docker-compose.postgres.yml` to your server
2. Update the `POSTGRES_PASSWORD` to a strong value
3. Run `docker compose -f docker-compose.postgres.yml up -d`
4. Set up a reverse proxy (nginx) for the FastAPI backend
5. Configure SSL/TLS with Let's Encrypt

---

## Troubleshooting

### "Cannot connect to PostgreSQL"

- Verify Docker is running: `docker ps`
- Check the container health: `docker compose -f docker-compose.postgres.yml ps`
- View container logs: `docker compose -f docker-compose.postgres.yml logs postgres`
- Ensure port 5432 is not already in use: `netstat -ano | findstr :5432`

### "relation does not exist" errors

The ORM tables are created by SQLAlchemy on application startup. If you see this error:
1. Make sure `DATABASE_URL` is set in `backend/.env`
2. Start the application once (`python main.py`) to trigger table creation
3. Or re-run the migration script

### "psycopg2 not installed"

```bash
pip install psycopg2-binary
```

For production, use the non-binary version:
```bash
pip install psycopg2
```

### Migration script fails partway through

The script is idempotent. Fix the underlying issue and run it again. It drops and recreates all tables on each run.

### Performance is slower than SQLite

- Check `DB_POOL_SIZE` is appropriate for your load
- Ensure PostgreSQL has enough `shared_buffers` (set in docker-compose)
- Run `ANALYZE` on all tables after migration:
  ```sql
  ANALYZE;
  ```

### pgvector extension not available

The `pgvector/pgvector:pg16` Docker image includes pgvector pre-installed. If using a managed service, you may need to enable the extension manually:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## Architecture Notes

### How the dual-database support works

`backend/database.py` contains the engine configuration:

```
DATABASE_URL env var
    |
    +-- starts with "postgresql://" --> PostgreSQL engine (pool_size=10, pool_pre_ping=True)
    |
    +-- absent or "sqlite://..."    --> SQLite engine (check_same_thread=False, WAL mode)
```

Both engines use the same SQLAlchemy ORM models. The async engine (`DATABASE_URL_ASYNC`) is configured automatically from `DATABASE_URL` by replacing the driver prefix.

### Tables overview

- **30 ORM-managed tables**: Created by SQLAlchemy (`Base.metadata.create_all()`)
- **2 pgvector tables**: `knowledge_documents` and `document_chunks` (created by `scripts/postgres_init.sql`)
- **Composite indexes**: 25+ covering common query patterns (defined in `database.py`)
