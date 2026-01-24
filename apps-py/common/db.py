"""
Database connection helpers for fabrik Python services.
Parses JDBC-style URLs for compatibility with Java service configuration.
"""
import os
import re
import logging
import psycopg2

logger = logging.getLogger(__name__)


def parse_jdbc_url(jdbc_url: str) -> dict:
    """
    Parse JDBC URL format: jdbc:postgresql://host:port/database
    Returns dict with host, port, database keys.
    """
    pattern = r'jdbc:postgresql://([^:]+):(\d+)/(\w+)'
    match = re.match(pattern, jdbc_url)
    if match:
        return {
            'host': match.group(1),
            'port': int(match.group(2)),
            'database': match.group(3)
        }
    raise ValueError(f"Invalid JDBC URL format: {jdbc_url}")


def get_db_connection():
    """
    Get a PostgreSQL connection using environment variables.
    Expects DB_URL (JDBC format), DB_USER, DB_PASSWORD.
    """
    db_url = os.environ.get('DB_URL', 'jdbc:postgresql://postgres:5432/fabrik')
    db_user = os.environ.get('DB_USER', 'fabrik')
    db_password = os.environ.get('DB_PASSWORD', 'fabrik')

    conn_params = parse_jdbc_url(db_url)

    return psycopg2.connect(
        host=conn_params['host'],
        port=conn_params['port'],
        database=conn_params['database'],
        user=db_user,
        password=db_password
    )


def init_db_tables(conn):
    """
    Initialize database tables if they don't exist.
    Idempotent - safe to call multiple times.
    """
    cursor = conn.cursor()

    # Orders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id VARCHAR(255) PRIMARY KEY,
            customer_name VARCHAR(255),
            customer_email VARCHAR(255),
            product VARCHAR(255),
            quantity INTEGER,
            price DECIMAL(10, 2),
            status VARCHAR(50) DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Inventory table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            product_name VARCHAR(255) UNIQUE,
            quantity INTEGER DEFAULT 0
        )
    """)

    # Shipments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shipments (
            id VARCHAR(255) PRIMARY KEY,
            order_id VARCHAR(255),
            carrier VARCHAR(100),
            tracking_number VARCHAR(255),
            status VARCHAR(50) DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed inventory data (idempotent with ON CONFLICT)
    products = [
        ('Widget A', 100),
        ('Widget B', 50),
        ('Widget C', 25),
        ('Gadget X', 10),
        ('Gadget Y', 5),
    ]
    for product, quantity in products:
        cursor.execute("""
            INSERT INTO inventory (product_name, quantity)
            VALUES (%s, %s)
            ON CONFLICT (product_name) DO UPDATE SET quantity = EXCLUDED.quantity
        """, (product, quantity))

    conn.commit()
    cursor.close()
    logger.info("Database tables initialized (idempotent)")
