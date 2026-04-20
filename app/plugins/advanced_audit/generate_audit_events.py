#!/usr/bin/env python3
"""
Script to generate audit events for testing Grafana dashboards
This script creates various audit events to populate metrics
for the advanced-audit dashboard.
"""
import asyncio
import argparse
import random
import asyncpg
import time
import logging
import uuid
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("audit_events_generator")

# Sample data for realistic event generation
USERS = ["admin", "user1", "user2", "user3", "system", "api_user", "service_account"]
ACTIONS = ["login", "logout", "create", "read", "update", "delete", "export", "import", "approve", "reject"]
RESOURCES = ["user", "document", "settings", "file", "report", "invoice", "product", "order", "payment"]
IP_ADDRESSES = ["192.168.1.1", "10.0.0.5", "172.16.0.10", "127.0.0.1", "10.10.10.10", "192.168.0.100"]
STATUS = ["success", "failure", "warning", "error", "info"]

async def create_audit_event(conn, table_name):
    """Create a random audit event."""
    try:
        # Generate random audit event data
        timestamp = datetime.now() - timedelta(minutes=random.randint(0, 60))
        user = random.choice(USERS)
        action = random.choice(ACTIONS)
        resource = random.choice(RESOURCES)
        resource_id = str(uuid.uuid4())
        ip_address = random.choice(IP_ADDRESSES)
        status = random.choice(STATUS)
        
        # Generate details based on action and status
        if status == "failure" or status == "error":
            details = f"Failed to {action} {resource}: Permission denied"
        elif status == "warning":
            details = f"Unusual {action} operation on {resource}: review recommended"
        else:
            details = f"Successfully performed {action} on {resource}"
        
        # Insert the audit event
        await conn.execute(
            f"""
            INSERT INTO {table_name} 
            (timestamp, user_id, action, resource_type, resource_id, ip_address, status, details)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            timestamp, user, action, resource, resource_id, ip_address, status, details
        )
        
        return True
    except Exception as e:
        logger.error(f"Error creating audit event: {str(e)}")
        return False

async def setup_database(conn, table_name):
    """Setup the audit events table if it doesn't exist."""
    try:
        # Create the table if it doesn't exist
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id VARCHAR(100) NOT NULL,
                action VARCHAR(50) NOT NULL,
                resource_type VARCHAR(50) NOT NULL,
                resource_id VARCHAR(100) NOT NULL,
                ip_address VARCHAR(50),
                status VARCHAR(20) NOT NULL,
                details TEXT
            )
        """)
        
        # Create indexes for better performance
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON {table_name}(timestamp)")
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_user ON {table_name}(user_id)")
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_action ON {table_name}(action)")
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_status ON {table_name}(status)")
        
        logger.info(f"Audit events table {table_name} is ready")
    
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        raise

async def generate_audit_events(db_url, table_name="audit_events", count=100, delay=0.1):
    """Generate a specified number of audit events."""
    try:
        # Connect to the database
        conn = await asyncpg.connect(db_url)
        
        # Setup the database table
        await setup_database(conn, table_name)
        
        # Generate the specified number of audit events
        success_count = 0
        logger.info(f"Generating {count} audit events...")
        
        for i in range(count):
            if await create_audit_event(conn, table_name):
                success_count += 1
            
            # Progress update every 10%
            if (i + 1) % max(1, count // 10) == 0 or i + 1 == count:
                logger.info(f"Progress: {i + 1}/{count} events generated")
            
            # Add a small delay to prevent overwhelming the database
            await asyncio.sleep(delay)
        
        await conn.close()
        logger.info(f"Audit event generation completed. {success_count}/{count} events created successfully.")
        return success_count
    
    except Exception as e:
        logger.error(f"Error generating audit events: {str(e)}")
        return 0

async def main():
    parser = argparse.ArgumentParser(description="Generate audit events for testing audit dashboards")
    parser.add_argument("--db-url", type=str, default="postgresql://postgres:postgres@localhost:5432/kaapi",
                        help="PostgreSQL connection URL")
    parser.add_argument("--table", type=str, default="audit_events",
                        help="Name of the audit events table to use")
    parser.add_argument("--count", type=int, default=100,
                        help="Number of audit events to generate")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="Delay between generating events in seconds")
    
    args = parser.parse_args()
    
    logger.info(f"Starting audit event generator with the following parameters:")
    logger.info(f"- Database URL: {args.db_url}")
    logger.info(f"- Table: {args.table}")
    logger.info(f"- Event count: {args.count}")
    logger.info(f"- Delay between events: {args.delay} seconds")
    
    await generate_audit_events(
        args.db_url,
        args.table,
        args.count,
        args.delay
    )

if __name__ == "__main__":
    asyncio.run(main())
