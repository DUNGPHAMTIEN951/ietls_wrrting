import mysql.connector

def cleanup_db():
    try:
        conn = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="",
            database="ielts_speaking"
        )
        cur = conn.cursor()
        
        # Delete pending image tasks
        cur.execute("DELETE FROM ai_tasks WHERE task_type = 'IMAGE' AND status = 'pending'")
        deleted_count = cur.rowcount
        conn.commit()
        
        print(f"Successfully deleted {deleted_count} pending image tasks.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    cleanup_db()
