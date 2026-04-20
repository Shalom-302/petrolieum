#!/usr/bin/env python3
"""
Script to generate log events for testing Grafana dashboards
This script creates various log entries to populate metrics
for the advanced-logging dashboard.
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
logger = logging.getLogger("log_events_generator")

# Sample data for realistic log generation
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LOG_SOURCES = ["api", "database", "auth", "scheduler", "worker", "cache", "frontend", "backend"]
LOG_MESSAGES = {
    "DEBUG": [
        "Processing request data",
        "Validating input parameters",
        "Checking cache for object",
        "Executing database query",
        "Parsing response from external API",
        "Rendering template"
    ],
    "INFO": [
        "User logged in successfully",
        "New account created",
        "Payment processed",
        "File uploaded successfully",
        "Email sent to user",
        "Configuration reloaded"
    ],
    "WARNING": [
        "Rate limit approaching threshold",
        "Deprecated API endpoint called",
        "Database connection pool running low",
        "High memory usage detected",
        "Slow query execution time"
    ],
    "ERROR": [
        "Failed to connect to database",
        "API request timed out",
        "Invalid authentication token",
        "File upload failed",
        "Payment processing error"
    ],
    "CRITICAL": [
        "Database connection lost",
        "Out of memory error",
        "Unhandled exception in main thread",
        "Security breach detected",
        "System shutdown initiated"
    ]
}

async def create_log_event(conn, table_name):
    """Create a random log event."""
    try:
        # Generate random log event data
        timestamp = datetime.now() - timedelta(minutes=random.randint(0, 60))
        level = random.choice(LOG_LEVELS)
        source = random.choice(LOG_SOURCES)
        message = random.choice(LOG_MESSAGES[level])
        
        # Add some randomness to the message
        if random.random() < 0.3:
            message += f" [id: {str(uuid.uuid4())[:8]}]"
        
        # For errors and critical logs, add stack trace
        trace = None
        if level in ["ERROR", "CRITICAL"]:
            trace = f"""Traceback (most recent call last):
  File "app/{source}.py", line {random.randint(10, 500)}, in process_request
    result = handler.process()
  File "app/core/handlers.py", line {random.randint(10, 300)}, in process
    return self._execute_operation()
Exception: {message}"""
        
        # Insert the log event
        await conn.execute(
            f"""
            INSERT INTO {table_name} 
            (timestamp, level, source, message, trace)
            VALUES ($1, $2, $3, $4, $5)
            """,
            timestamp, level, source, message, trace
        )
        
        return True
    except Exception as e:
        logger.error(f"Error creating log event: {str(e)}")
        return False

async def setup_database(conn, table_name):
    """Setup the log events table if it doesn't exist."""
    try:
        # Create the table if it doesn't exist
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level VARCHAR(20) NOT NULL,
                source VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                trace TEXT
            )
        """)
        
        # Create indexes for better performance
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON {table_name}(timestamp)")
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_level ON {table_name}(level)")
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_source ON {table_name}(source)")
        
        logger.info(f"Log events table {table_name} is ready")
    
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        raise

async def generate_log_events(db_url, table_name="log_events", count=100, delay=0.1):
    """Generate a specified number of log events."""
    try:
        # Connect to the database
        conn = await asyncpg.connect(db_url)
        
        # Setup the database table
        await setup_database(conn, table_name)
        
        # Generate the specified number of log events
        success_count = 0
        logger.info(f"Generating {count} log events...")
        
        for i in range(count):
            if await create_log_event(conn, table_name):
                success_count += 1
            
            # Progress update every 10%
            if (i + 1) % max(1, count // 10) == 0 or i + 1 == count:
                logger.info(f"Progress: {i + 1}/{count} events generated")
            
            # Add a small delay to prevent overwhelming the database
            await asyncio.sleep(delay)
        
        await conn.close()
        logger.info(f"Log event generation completed. {success_count}/{count} events created successfully.")
        return success_count
    
    except Exception as e:
        logger.error(f"Error generating log events: {str(e)}")
        return 0

async def main():
    parser = argparse.ArgumentParser(description="Generate log events for testing logging dashboards")
    parser.add_argument("--db-url", type=str, default="postgresql://postgres:postgres@localhost:5432/kaapi",
                        help="PostgreSQL connection URL")
    parser.add_argument("--table", type=str, default="log_events",
                        help="Name of the log events table to use")
    parser.add_argument("--count", type=int, default=100,
                        help="Number of log events to generate")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="Delay between generating events in seconds")
    
    args = parser.parse_args()
    
    logger.info(f"Starting log event generator with the following parameters:")
    logger.info(f"- Database URL: {args.db_url}")
    logger.info(f"- Table: {args.table}")
    logger.info(f"- Event count: {args.count}")
    logger.info(f"- Delay between events: {args.delay} seconds")
    
    await generate_log_events(
        args.db_url,
        args.table,
        args.count,
        args.delay
    )

if __name__ == "__main__":
    asyncio.run(main())
