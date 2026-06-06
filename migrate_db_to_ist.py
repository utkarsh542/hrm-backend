import sqlite3
import os
from datetime import datetime, timedelta

db_files = [
    r"c:\Users\Utkarsh Gupta\Downloads\hrm\backend\hrm.db",
    r"c:\Users\Utkarsh Gupta\Downloads\hrm\backend\hrms.db"
]

def migrate_db(db_path):
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist. Skipping.")
        return
        
    print(f"\nMigrating database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    
    offset = timedelta(hours=5, minutes=30)
    
    for table in tables:
        if table.startswith("sqlite_"):
            continue
            
        cursor.execute(f"PRAGMA table_info({table})")
        columns_info = cursor.fetchall()
        
        datetime_cols = []
        for col in columns_info:
            col_id, col_name, col_type, nullable, default_val, pk = col
            col_type = col_type.upper()
            
            # Check if column stores datetime
            is_dt = ("DATETIME" in col_type or 
                     col_name in ["check_in", "check_out", "created_at", "updated_at", 
                                  "submitted_at", "applied_at", "enrolled_at", 
                                  "processed_at", "acted_at", "approved_at", 
                                  "paid_at", "manager_action_at", "hr_action_at"])
            
            if is_dt:
                datetime_cols.append(col_name)
                
        if not datetime_cols:
            continue
            
        print(f"  Table: {table} | Datetime columns: {datetime_cols}")
        
        # We fetch all rows with primary key or rowid to update individually
        # Let's find the primary key column, default to rowid if not found
        pk_col = "rowid"
        for col in columns_info:
            col_id, col_name, col_type, nullable, default_val, pk = col
            if pk == 1:
                pk_col = col_name
                break
                
        cursor.execute(f"SELECT {pk_col}, {', '.join(datetime_cols)} FROM {table}")
        rows = cursor.fetchall()
        
        updated_count = 0
        for row in rows:
            pk_val = row[0]
            updates = {}
            for idx, col_name in enumerate(datetime_cols):
                val = row[idx + 1]
                if val:
                    # Let's try to parse the datetime string
                    # SQLite stores it in different formats depending on how it was inserted, e.g.:
                    # '2026-06-06 05:51:18.467466'
                    # '2026-05-23 09:00:32.012281'
                    # '2026-06-06T05:51:18.467466'
                    parsed = None
                    for fmt in [
                        "%Y-%m-%d %H:%M:%S.%f", 
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S.%f",
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%d %H:%M"
                    ]:
                        try:
                            parsed = datetime.strptime(val, fmt)
                            break
                        except ValueError:
                            pass
                            
                    if parsed:
                        new_dt = parsed + offset
                        new_val = new_dt.strftime("%Y-%m-%d %H:%M:%S.%f")
                        updates[col_name] = new_val
                        
            if updates:
                set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
                params = list(updates.values()) + [pk_val]
                cursor.execute(f"UPDATE {table} SET {set_clause} WHERE {pk_col} = ?", params)
                updated_count += 1
                
        if updated_count > 0:
            print(f"    Updated {updated_count} rows in {table}")
            
    conn.commit()
    conn.close()
    print(f"Finished migration for {db_path}")

if __name__ == "__main__":
    for db in db_files:
        migrate_db(db)
