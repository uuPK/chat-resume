import sqlite3
import psycopg2
from psycopg2.extras import execute_values

def get_pg_columns(pg_cur, table_name):
    pg_cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{table_name}';")
    return {r[0]: r[1] for r in pg_cur.fetchall()}

def main():
    sl_conn = sqlite3.connect("chat_resume.db")
    sl_conn.row_factory = sqlite3.Row
    sl_cur = sl_conn.cursor()

    pg_conn = psycopg2.connect("postgresql://chat_resume:chat_resume_password@localhost:5432/chat_resume")
    pg_cur = pg_conn.cursor()

    sl_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in sl_cur.fetchall()]

    print("Found tables in SQLite:", tables)

    try:
        pg_cur.execute("SET session_replication_role = 'replica';")
        for table in tables:
            sl_cur.execute(f"SELECT * FROM {table}")
            rows = sl_cur.fetchall()
            if not rows:
                print(f"Table {table} is empty.")
                continue
                
            pg_cols = get_pg_columns(pg_cur, table)
            if not pg_cols:
                print(f"Skipping {table} as it does not exist in PG.")
                continue

            columns = list(rows[0].keys())
            
            # Filter columns that actually exist in PostgreSQL
            valid_cols = [c for c in columns if c in pg_cols]
            valid_indices = [columns.index(c) for c in valid_cols]
            
            bool_cols = {c for c, t in pg_cols.items() if t == 'boolean'}
            bool_indices_in_valid = [i for i, c in enumerate(valid_cols) if c in bool_cols]
            
            cols_str = ", ".join([f'"{c}"' for c in valid_cols])
            
            values = []
            for r in rows:
                row_list = list(r)
                filtered_row = [row_list[i] for i in valid_indices]
                
                # Convert 1/0 from SQLite to True/False for Postgres boolean columns
                for idx in bool_indices_in_valid:
                    if filtered_row[idx] is not None:
                        filtered_row[idx] = bool(filtered_row[idx])
                values.append(tuple(filtered_row))
            
            query = f'INSERT INTO "{table}" ({cols_str}) VALUES %s ON CONFLICT DO NOTHING;'
            try:
                execute_values(pg_cur, query, values)
                print(f"Migrated {len(rows)} rows for table {table}")
            except psycopg2.errors.UndefinedTable:
                print(f"Skipping table {table} because it does not exist in PostgreSQL yet.")
                pg_conn.rollback()
                pg_cur.execute("SET session_replication_role = 'replica';")

        # Fix sequences for auto-incrementing primary keys
        for table in tables:
            try:
                pg_cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}' AND column_default LIKE 'nextval%';")
                seq_info = pg_cur.fetchone()
                if seq_info:
                    col_name = seq_info[0]
                    pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('\"{table}\"', '{col_name}'), coalesce(max(\"{col_name}\"), 1), max(\"{col_name}\") IS NOT null) FROM \"{table}\";")
            except Exception:
                pg_conn.rollback()
                pg_cur.execute("SET session_replication_role = 'replica';")
                
        pg_conn.commit()
        print("Migration successful!")
    except Exception as e:
        pg_conn.rollback()
        print("Migration failed:", e)
    finally:
        pg_cur.execute("SET session_replication_role = 'origin';")
        pg_conn.commit()
        pg_conn.close()
        sl_conn.close()

if __name__ == "__main__":
    main()
