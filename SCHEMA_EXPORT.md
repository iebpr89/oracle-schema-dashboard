# Oracle schema metadata export

This tool exports **schema definitions only**, never business table rows.

## Run on your Ubuntu server

```bash
python3 -m pip install oracledb
export ORACLE_USER='your_oracle_user'
read -rsp 'Oracle password: ' ORACLE_PASSWORD; export ORACLE_PASSWORD; echo
export ORACLE_DSN='localhost:1521/FREEPDB1'
python3 export_schema.py --schemas HR CO OE SH BI PM
unset ORACLE_PASSWORD
```

The account needs access to the schema metadata through Oracle `ALL_*` views.
Outputs: `schema/<OWNER>/tables.csv`, `columns.csv`, `constraints.csv`,
`constraint_columns.csv`, `foreign_keys.csv`, and `metadata.json`.

For GitHub upload of **metadata only**, review the generated files for sensitive
information (especially defaults, CHECK expressions, names, and comments) before
committing. Never commit credentials, `.env` files, or actual customer data.

```bash
git add schema/HR schema/CO schema/OE schema/SH schema/BI schema/PM
git commit -m "Add Oracle schema metadata export"
git push origin main
```
