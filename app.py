"""Oracle Schema Explorer: Streamlit dashboard showing Oracle schemas, tables, columns and FK relationships."""
import os
import html
import re

import oracledb
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Oracle Schema Explorer", page_icon="🗃️", layout="wide")
st.title("🗃️ Oracle Schema Explorer")
st.caption("Oracle ALL_* 데이터 사전 기반 · 스키마 / 테이블 / 컬럼 / PK-FK / ERD")

SCHEMAS = """SELECT owner AS schema_name, COUNT(*) AS table_count
FROM all_tables WHERE owner NOT IN ('SYS','SYSTEM','XDB','MDSYS','CTXSYS','ORDSYS',
'WMSYS','DBSNMP','OUTLN','APPQOSSYS','AUDSYS','LBACSYS','DVSYS')
GROUP BY owner ORDER BY owner"""

TABLES = """SELECT t.owner AS schema_name, t.table_name, COUNT(c.column_name) AS column_count,
NVL(tc.comments,'') AS comments FROM all_tables t
LEFT JOIN all_tab_columns c ON c.owner=t.owner AND c.table_name=t.table_name
LEFT JOIN all_tab_comments tc ON tc.owner=t.owner AND tc.table_name=t.table_name
AND tc.table_type='TABLE'
WHERE t.owner=:owner
GROUP BY t.owner,t.table_name,tc.comments ORDER BY t.table_name"""

COLUMNS = """SELECT c.column_id,c.column_name,
CASE WHEN c.data_type IN ('VARCHAR2','NVARCHAR2','CHAR','NCHAR')
THEN c.data_type || '(' || TO_CHAR(c.char_length) || ')'
WHEN c.data_type='NUMBER' AND c.data_precision IS NOT NULL
THEN c.data_type || '(' || TO_CHAR(c.data_precision) ||
CASE WHEN c.data_scale IS NULL THEN '' ELSE ',' || TO_CHAR(c.data_scale) END || ')'
ELSE c.data_type END AS data_type,c.nullable,
CASE WHEN pk.column_name IS NOT NULL THEN 'PK' ELSE '' END AS pk,
CASE WHEN fk.column_name IS NOT NULL THEN 'FK' ELSE '' END AS fk,
NVL(cc.comments,'') AS comments FROM all_tab_columns c
LEFT JOIN (SELECT ac.owner,acc.table_name,acc.column_name
FROM all_constraints ac JOIN all_cons_columns acc
ON ac.owner=acc.owner AND ac.constraint_name=acc.constraint_name
WHERE ac.constraint_type='P') pk
ON pk.owner=c.owner AND pk.table_name=c.table_name AND pk.column_name=c.column_name
LEFT JOIN (SELECT DISTINCT ac.owner,acc.table_name,acc.column_name
FROM all_constraints ac JOIN all_cons_columns acc
ON ac.owner=acc.owner AND ac.constraint_name=acc.constraint_name
WHERE ac.constraint_type='R') fk
ON fk.owner=c.owner AND fk.table_name=c.table_name AND fk.column_name=c.column_name
LEFT JOIN all_col_comments cc
ON cc.owner=c.owner AND cc.table_name=c.table_name AND cc.column_name=c.column_name
WHERE c.owner=:owner AND c.table_name=:table_name ORDER BY c.column_id"""

RELATIONS = """SELECT fk.table_name AS source_table,fkc.column_name AS source_column,
pk.owner AS target_schema,pk.table_name AS target_table,
pkc.column_name AS target_column,fk.constraint_name
FROM all_constraints fk JOIN all_cons_columns fkc
ON fkc.owner=fk.owner AND fkc.constraint_name=fk.constraint_name
JOIN all_constraints pk ON pk.owner=fk.r_owner AND pk.constraint_name=fk.r_constraint_name
JOIN all_cons_columns pkc ON pkc.owner=pk.owner
AND pkc.constraint_name=pk.constraint_name AND pkc.position=fkc.position
WHERE fk.owner=:owner AND fk.constraint_type='R'
ORDER BY fk.table_name,fk.constraint_name,fkc.position"""

def default(name, fallback=""):
    if name in os.environ:
        return os.environ[name]
    try:
        return str(st.secrets.get(name, fallback))
    except (FileNotFoundError, KeyError):
        return fallback

with st.sidebar:
    st.header("🔌 Oracle 연결")
    host = st.text_input("Host", value=default("ORACLE_HOST", "localhost"))
    port = st.number_input("Port", value=int(default("ORACLE_PORT", "1521")), min_value=1, max_value=65535)
    service = st.text_input("Service", value=default("ORACLE_SERVICE", "FREEPDB1"))
    user = st.text_input("Username", value=default("ORACLE_USER", "system"))
    password = st.text_input("Password", value=default("ORACLE_PASSWORD"), type="password")
    if st.button("연결 / 새로고침", use_container_width=True):
        st.cache_data.clear()
    st.caption("데이터 조회는 읽기 전용입니다. DB 비밀번호를 GitHub에 저장하지 마세요.")

if not password:
    st.info("왼쪽에서 Oracle 접속 정보를 입력하세요.")
    st.stop()

@st.cache_data(ttl=120, show_spinner=False)
def query(host, port, service, user, password, sql, **binds):
    # Thin mode: Oracle Instant Client not required
    with oracledb.connect(user=user, password=password, dsn=f"{host}:{port}/{service}") as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, binds)
            names = [d[0].lower() for d in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=names)

def read(sql, **binds):
    return query(host, port, service, user, password, sql, **binds)

try:
    schemas = read(SCHEMAS)
except Exception as exc:
    st.error("Oracle 연결 또는 메타데이터 조회 실패")
    st.code(str(exc))
    st.stop()

if schemas.empty:
    st.warning("조회 가능한 스키마가 없습니다.")
    st.stop()

with st.sidebar:
    schema_names = schemas.schema_name.tolist()
    schema = st.selectbox("📁 스키마", schema_names,
                          index=schema_names.index("HR") if "HR" in schema_names else 0)

try:
    tables = read(TABLES, owner=schema)
    relations = read(RELATIONS, owner=schema)
except Exception as exc:
    st.error(f"스키마 조회 실패: {exc}")
    st.stop()

a,b,c,d = st.columns(4)
a.metric("스키마", schema)
b.metric("테이블", len(tables))
c.metric("컬럼", int(tables.column_count.sum()) if not tables.empty else 0)
d.metric("FK 제약조건", relations.constraint_name.nunique() if not relations.empty else 0)

tab1,tab2,tab3,tab4 = st.tabs(["📋 테이블 목록", "🔎 컬럼 상세", "🧩 ERD", "🔗 FK 관계"])

with tab1:
    search = st.text_input("테이블 검색")
    shown = tables[tables.table_name.str.contains(search, case=False, regex=False)] if search else tables
    st.dataframe(shown, use_container_width=True, hide_index=True)
    st.download_button("테이블 CSV 다운로드", shown.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{schema}_tables.csv", mime="text/csv")
with tab2:
    names = tables.table_name.tolist()
    if names:
        name = st.selectbox("테이블 선택", names)
        cols = read(COLUMNS, owner=schema, table_name=name)
        keyword = st.text_input("컬럼명 검색")
        if keyword:
            cols = cols[cols.column_name.str.contains(keyword, case=False, regex=False)]
        st.dataframe(cols, use_container_width=True, hide_index=True)
        st.download_button("컬럼 CSV 다운로드", cols.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"{schema}_{name}_columns.csv", mime="text/csv")
    else:
        st.info("테이블이 없습니다.")
with tab3:
    selected = st.multiselect("ERD 테이블 선택 (최대 25개)", tables.table_name.tolist(),
                              default=tables.table_name.tolist()[:8])
    limit = st.slider("테이블당 표시 컬럼", 4, 30, 12)
    if selected and len(selected) <= 25:
        dot = ['digraph ERD {', 'graph [rankdir=LR, bgcolor="transparent"];',
               'node [shape=plain];', 'edge [color="#517dbd"];']
        node_ids = {name: "n" + str(i) for i,name in enumerate(selected)}
        for name in selected:
            columns = read(COLUMNS, owner=schema, table_name=name)
            cells = [f'<TR><TD BGCOLOR="#184d92"><FONT COLOR="white"><B>{html.escape(name)}</B></FONT></TD></TR>']
            for _,r in columns.head(limit).iterrows():
                flag = "🔑 " if r["pk"] == "PK" else ("FK " if r["fk"] == "FK" else "")
                label = html.escape(f'{flag}{r["column_name"]}: {r["data_type"]}')
                cells.append(f'<TR><TD ALIGN="LEFT">{label}</TD></TR>')
            dot.append(f'{node_ids[name]} [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5">{"".join(cells)}</TABLE>>];')
        for _,r in relations.iterrows():
            if r.source_table in node_ids and r.target_schema == schema and r.target_table in node_ids:
                dot.append(f'{node_ids[r.source_table]} -> {node_ids[r.target_table]};')
        dot.append("}")
        source = "\n".join(dot)
        st.graphviz_chart(source, use_container_width=True)
        st.download_button("ERD DOT 다운로드", source, file_name=f"{schema}_erd.dot")
    elif len(selected) > 25:
        st.warning("최대 25개 테이블을 선택하세요.")
with tab4:
    st.dataframe(relations, use_container_width=True, hide_index=True)
    st.download_button("FK CSV 다운로드", relations.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{schema}_foreign_keys.csv", mime="text/csv")
st.caption("ALL_TABLES · ALL_TAB_COLUMNS · ALL_CONSTRAINTS · ALL_CONS_COLUMNS · 캐시 TTL 120초")
