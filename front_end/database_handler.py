import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pathlib

class DatabaseHandler:
    def __init__(self, db_name: str = "chat_app.db"):
        current_dir = pathlib.Path(__file__).parent.absolute()
        self.databases_dir = current_dir.parent / "databases"
        self.databases_dir.mkdir(exist_ok=True, parents=True)
        
        self.db_path = self.databases_dir / db_name
        self.init_database()
    
    def get_connection(self):
        """Get a connection to the SQLite database"""
        return sqlite3.connect(str(self.db_path))
    
    def init_database(self):
        """Initialize SQLite database and create tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create messages table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create urls table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                description TEXT,
                status TEXT DEFAULT 'Submitted',
                submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            conn.commit()
    
    # Message-related methods
    def add_message(self, role: str, content: str) -> bool:
        """Add a new message to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (role, content) VALUES (?, ?)",
                    (role, content)
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error adding message: {e}")
            return False
    
    def get_all_messages(self) -> List[Dict]:
        """Get all messages from the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT role, content, timestamp FROM messages ORDER BY timestamp")
                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        "role": row[0],
                        "content": row[1],
                        "timestamp": row[2]
                    })
                return messages
        except sqlite3.Error as e:
            print(f"Error getting messages: {e}")
            return []
    
    def clear_messages(self) -> bool:
        """Delete all messages from the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM messages")
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error clearing messages: {e}")
            return False
    
    def get_message_count(self) -> int:
        """Get the total number of messages"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM messages")
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            print(f"Error getting message count: {e}")
            return 0
    
    # URL-related methods
    def add_url(self, url: str, description: Optional[str] = None) -> Tuple[bool, str]:
        """Add a new URL to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO urls (url, description) VALUES (?, ?)",
                    (url, description)
                )
                conn.commit()
                return True, "URL added successfully"
        except sqlite3.IntegrityError:
            return False, "URL already exists"
        except sqlite3.Error as e:
            return False, f"Error adding URL: {e}"
    
    def get_all_urls(self) -> List[Dict]:
        """Get all URLs from the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT url, description, status, submitted_at FROM urls ORDER BY submitted_at")
                urls = []
                for row in cursor.fetchall():
                    urls.append({
                        "url": row[0],
                        "description": row[1],
                        "status": row[2],
                        "timestamp": row[3]
                    })
                return urls
        except sqlite3.Error as e:
            print(f"Error getting URLs: {e}")
            return []
    
    def update_url_status(self, url: str, status: str) -> bool:
        """Update the status of a URL"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE urls SET status = ? WHERE url = ?",
                    (status, url)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error updating URL status: {e}")
            return False
    
    def delete_url(self, url: str) -> bool:
        """Delete a URL from the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM urls WHERE url = ?", (url,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error deleting URL: {e}")
            return False
    
    def clear_urls(self) -> bool:
        """Delete all URLs from the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM urls")
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error clearing URLs: {e}")
            return False
    
    def get_url_count(self) -> int:
        """Get the total number of URLs"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM urls")
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            print(f"Error getting URL count: {e}")
            return 0
    
    def get_active_url_count(self) -> int:
        """Get the number of active URLs"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM urls WHERE status = 'Active'")
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            print(f"Error getting active URL count: {e}")
            return 0
    
    # Database management methods
    def clear_all_data(self) -> bool:
        """Clear all data from both tables"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM messages")
                cursor.execute("DELETE FROM urls")
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error clearing all data: {e}")
            return False
    
    def get_database_info(self) -> Dict:
        """Get database statistics and information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get message count
                cursor.execute("SELECT COUNT(*) FROM messages")
                total_messages = cursor.fetchone()[0]
                
                # Get URL count
                cursor.execute("SELECT COUNT(*) FROM urls")
                total_urls = cursor.fetchone()[0]
                
                # Get active URL count
                cursor.execute("SELECT COUNT(*) FROM urls WHERE status = 'Active'")
                active_urls = cursor.fetchone()[0]
                
                return {
                    "total_messages": total_messages,
                    "total_urls": total_urls,
                    "active_urls": active_urls,
                    "database_file": str(self.db_path),
                    "database_size": self.get_database_size()
                }
        except sqlite3.Error as e:
            print(f"Error getting database info: {e}")
            return {}
    
    def get_database_size(self) -> float:
        """Get the database file size in KB"""
        if os.path.exists(str(self.db_path)):
            return os.path.getsize(str(self.db_path)) / 1024  # Size in KB
        return 0.0
    
    def backup_database(self, backup_path: str) -> bool:
        """Create a backup of the database"""
        try:
            import shutil
            if backup_name is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"backup_{timestamp}.db"
            
            backup_path = self.databases_dir / backup_name
            shutil.copy2(self.db_path, backup_path)
            return True, str(backup_path)
        except Exception as e:
            print(f"Error backing up database: {e}")
            return False, str(e)

    def list_backups(self) -> List[str]:
        """List all backup files in the databases directory"""
        try:
            backups = []
            for file in self.databases_dir.iterdir():
                if file.is_file() and file.name.startswith('backup_') and file.name.endswith('.db'):
                    backups.append({
                        'name': file.name,
                        'size': file.stat().st_size / 1024,  # KB
                        'modified': datetime.fromtimestamp(file.stat().st_mtime)
                    })
            return sorted(backups, key=lambda x: x['modified'], reverse=True)
        except Exception as e:
            print(f"Error listing backups: {e}")
            return []
    
    def restore_backup(self, backup_name: str) -> bool:
        """Restore database from a backup"""
        try:
            backup_path = self.databases_dir / backup_name
            if backup_path.exists():
                # Close any existing connections
                import sqlite3
                sqlite3.connect(str(self.db_path)).close()
                
                # Restore backup
                import shutil
                shutil.copy2(backup_path, self.db_path)
                return True
            return False
        except Exception as e:
            print(f"Error restoring backup: {e}")
            return False
# Singleton instance for easy access
db_handler = DatabaseHandler()

# Example usage (for testing)
if __name__ == "__main__":
    # Test the database handler
    print(f"Database will be stored in: {db_handler.databases_dir}")
    print(f"Database path: {db_handler.db_path}")
    
    # Test messages
    db_handler.add_message("user", "Hello, world!")
    db_handler.add_message("bot", "Hi there!")
    
    # Test URLs
    db_handler.add_url("https://example.com", "Test website")
    
    # Get data
    messages = db_handler.get_all_messages()
    urls = db_handler.get_all_urls()
    
    print("Messages:", messages)
    print("URLs:", urls)
    print("Database info:", db_handler.get_database_info())
    
    # Test backup
    success, backup_path = db_handler.backup_database()
    if success:
        print(f"Backup created: {backup_path}")
    
    # List backups
    backups = db_handler.list_backups()
    print("Backups:", backups)