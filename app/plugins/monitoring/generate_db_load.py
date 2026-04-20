#!/usr/bin/env python3
"""
Script to generate database load for testing Grafana dashboards
This script executes various database operations to generate metrics
for the database-performance dashboard.
"""
import asyncio
import argparse
import random
import asyncpg
import time
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db_load_generator")

async def execute_query(conn, query_type, table_name, duration=60, delay=0.5):
    """Execute database queries based on the specified type."""
    start_time = time.time()
    end_time = start_time + duration
    query_count = 0
    
    logger.info(f"Starting {query_type} operations on {table_name}")
    
    while time.time() < end_time:
        try:
            if query_type == "SELECT":
                # Random SELECT operation with varying complexity
                if random.random() < 0.3:
                    # Simple SELECT
                    await conn.fetch(f"SELECT * FROM {table_name} LIMIT {random.randint(10, 100)}")
                elif random.random() < 0.6:
                    # Filtered SELECT
                    await conn.fetch(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT {random.randint(5, 50)}")
                else:
                    # Complex SELECT with aggregation
                    await conn.fetch(f"SELECT COUNT(*), AVG(id::float) FROM {table_name}")
            
            elif query_type == "INSERT":
                # INSERT operation
                current_time = datetime.now().isoformat()
                value = random.uniform(0, 100)
                await conn.execute(
                    f"INSERT INTO {table_name} (metric_name, metric_value, timestamp) VALUES ($1, $2, $3)",
                    f"metric_{random.randint(1, 10)}", value, current_time
                )
            
            elif query_type == "UPDATE":
                # UPDATE operation with random criteria
                await conn.execute(
                    f"UPDATE {table_name} SET metric_value = $1 WHERE id IN (SELECT id FROM {table_name} ORDER BY random() LIMIT 1)",
                    random.uniform(0, 100)
                )
            
            elif query_type == "DELETE":
                # DELETE operation (limited to control growth)
                if random.random() < 0.2:  # Only do this occasionally
                    await conn.execute(
                        f"DELETE FROM {table_name} WHERE id IN (SELECT id FROM {table_name} ORDER BY random() LIMIT 1)"
                    )
            
            elif query_type == "VACUUM":
                # VACUUM operation
                if random.random() < 0.05:  # Very rarely
                    await conn.execute(f"VACUUM {table_name}")
            
            query_count += 1
            await asyncio.sleep(delay)  # Control query frequency
            
        except Exception as e:
            logger.error(f"Error executing {query_type} query: {str(e)}")
    
    logger.info(f"Completed {query_count} {query_type} operations on {table_name}")
    return query_count

async def setup_database(conn, table_name):
    """Setup the test database table if it doesn't exist."""
    try:
        # Create the table if it doesn't exist
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                metric_name VARCHAR(50) NOT NULL,
                metric_value FLOAT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better performance
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_name ON {table_name}(metric_name)")
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON {table_name}(timestamp)")
        
        logger.info(f"Database table {table_name} is ready")
        
        # Check if we need to populate initial data
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
        if count < 100:
            logger.info(f"Populating initial data in {table_name}")
            # Add some initial data points
            for i in range(100):
                metric_name = f"metric_{random.randint(1, 10)}"
                metric_value = random.uniform(0, 100)
                timestamp = datetime.now() - timedelta(minutes=random.randint(0, 60))
                await conn.execute(
                    f"INSERT INTO {table_name} (metric_name, metric_value, timestamp) VALUES ($1, $2, $3)",
                    metric_name, metric_value, timestamp
                )
            logger.info("Initial data populated")
    
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        raise

async def run_load_test(db_url, table_name="monitoring_test", duration=60, connections=5, delay=0.1):
    """Run a full load test with multiple query types and connections."""
    try:
        # Connect to the database
        conn = await asyncpg.connect(db_url)
        
        # Setup the database table
        await setup_database(conn, table_name)
        await conn.close()
        
        # Define query mix
        query_types = ["SELECT", "INSERT", "UPDATE", "DELETE", "VACUUM"]
        query_weights = [0.6, 0.3, 0.08, 0.01, 0.01]  # Weights for random selection
        
        # Start multiple connections for different query types
        tasks = []
        for _ in range(connections):
            # Select random query type based on weights
            query_type = random.choices(query_types, weights=query_weights, k=1)[0]
            
            # Create a new connection for each task
            conn = await asyncpg.connect(db_url)
            
            # Create and schedule the task
            task = asyncio.create_task(
                execute_query(conn, query_type, table_name, duration, delay)
            )
            tasks.append((task, conn))
        
        # Wait for all tasks to complete
        results = []
        for task, conn in tasks:
            try:
                result = await task
                results.append(result)
            finally:
                await conn.close()
        
        total_queries = sum(results)
        logger.info(f"Load test completed. Total queries executed: {total_queries}")
        return total_queries
    
    except Exception as e:
        logger.error(f"Error in load test: {str(e)}")
        return 0

async def main():
    parser = argparse.ArgumentParser(description="Generate database load for testing monitoring dashboards")
    parser.add_argument("--db-url", type=str, default="postgresql://postgres:postgres@localhost:5432/kaapi",
                        help="PostgreSQL connection URL")
    parser.add_argument("--table", type=str, default="monitoring_test",
                        help="Name of the test table to use")
    parser.add_argument("--duration", type=int, default=60,
                        help="Duration of the test in seconds")
    parser.add_argument("--connections", type=int, default=5,
                        help="Number of concurrent connections to use")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="Delay between queries in seconds")
    
    args = parser.parse_args()
    
    logger.info(f"Starting database load generator with the following parameters:")
    logger.info(f"- Database URL: {args.db_url}")
    logger.info(f"- Table: {args.table}")
    logger.info(f"- Duration: {args.duration} seconds")
    logger.info(f"- Connections: {args.connections}")
    logger.info(f"- Delay between queries: {args.delay} seconds")
    
    await run_load_test(
        args.db_url,
        args.table,
        args.duration,
        args.connections,
        args.delay
    )

if __name__ == "__main__":
    asyncio.run(main())
