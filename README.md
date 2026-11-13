# Oracle Schema Dashboard

Python **Streamlit** web dashboard for exploring Oracle schemas, tables, columns, primary keys, foreign keys and ERD relationships.

## Features
- Discover Oracle schemas and tables using `ALL_*` dictionary views
- Search tables and columns
- Inspect column datatype, nullable, PK/FK and comments
- Generate interactive Graphviz ERD for selected tables
- Browse FK relationships and export CSV
- Read-only database metadata queries

## Ubuntu 24.04 quick start

```bash
git clone https://github.com/iebpr89/oracle-schema-dashboard.git
cd oracle-schema-dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0
```

Open **http://localhost:8501**.

## Oracle settings

Set values in the sidebar or environment variables:

```bash
export ORACLE_HOST=localhost
export ORACLE_PORT=1521
export ORACLE_SERVICE=FREEPDB1
export ORACLE_USER=system
# Set ORACLE_PASSWORD locally; never commit credentials.
streamlit run app.py
```

Oracle's Python thin driver does not require Oracle Instant Client. The login account must have visibility into the desired schemas. ERD relationships appear only for database FK constraints visible to the account.

**Security:** Never commit passwords, real `secrets.toml`, or `.env` to GitHub. Deploy with network restrictions and an account with minimal read-only privileges.
