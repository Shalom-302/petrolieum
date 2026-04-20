#!/usr/bin/env python3
"""
Script to generate API traffic for testing Grafana dashboards
This script sends requests to various API endpoints to populate metrics
for the api-performance dashboard.
"""
import asyncio
import argparse
import random
import aiohttp
import time
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api_traffic_generator")

# Sample data for API requests
HTTP_METHODS = ["GET", "POST", "PUT", "DELETE"]
API_ENDPOINTS = [
    "/apiusers",
    "/apiproducts",
    "/apiorders",
    "/apiauth/login",
    "/apiauth/refresh",
    "/apisettings",
    "/apidashboard",
    "/apireports",
    "/api/v2/users",
    "/api/v2/products"
]

SAMPLE_PAYLOADS = {
    "/apiusers": {
        "POST": {"username": "testuser", "email": "test@example.com", "role": "user"},
        "PUT": {"email": "updated@example.com", "role": "admin"}
    },
    "/apiproducts": {
        "POST": {"name": "Test Product", "price": 19.99, "category": "electronics"},
        "PUT": {"price": 24.99, "stock": 100}
    },
    "/apiorders": {
        "POST": {"product_id": 123, "quantity": 2, "user_id": 456},
        "PUT": {"status": "shipped", "tracking_number": "TRK123456"}
    },
    "/apiauth/login": {
        "POST": {"username": "testuser", "password": "password123"}
    },
    "/api/v2/users": {
        "POST": {"username": "newuser", "email": "new@example.com", "profile": {"fullName": "New User"}},
        "PUT": {"profile": {"phone": "123-456-7890"}}
    },
    "/api/v2/products": {
        "POST": {"name": "New Product", "details": {"price": 29.99, "features": ["feature1", "feature2"]}},
        "PUT": {"details": {"stock": 50, "availability": "in_stock"}}
    }
}

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "API-Performance-Test/1.0",
    "Accept": "application/json"
}

async def send_api_request(session, base_url, method, endpoint, auth_token=None):
    """Send a request to the specified API endpoint."""
    url = f"{base_url}{endpoint}"
    headers = DEFAULT_HEADERS.copy()
    
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    # Prepare payload for POST/PUT requests
    payload = None
    if method in ["POST", "PUT"]:
        # Get endpoint-specific payload or use default
        if endpoint in SAMPLE_PAYLOADS and method in SAMPLE_PAYLOADS[endpoint]:
            payload = SAMPLE_PAYLOADS[endpoint][method]
            
            # Add some randomness to payloads
            if "price" in payload:
                payload["price"] = round(random.uniform(10, 100), 2)
            if "quantity" in payload:
                payload["quantity"] = random.randint(1, 10)
        else:
            # Generic payload
            payload = {"timestamp": datetime.now().isoformat(), "value": random.randint(1, 100)}
    
    try:
        start_time = time.time()
        
        if method == "GET":
            async with session.get(url, headers=headers) as response:
                await response.text()
                status = response.status
        elif method == "POST":
            async with session.post(url, headers=headers, json=payload) as response:
                await response.text()
                status = response.status
        elif method == "PUT":
            async with session.put(url, headers=headers, json=payload) as response:
                await response.text()
                status = response.status
        elif method == "DELETE":
            async with session.delete(url, headers=headers) as response:
                await response.text()
                status = response.status
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return False, 0
        
        response_time = (time.time() - start_time) * 1000  # in milliseconds
        
        logger.info(f"{method} {url} - Status: {status} - Response time: {response_time:.2f}ms")
        return True, response_time
    
    except Exception as e:
        logger.error(f"Error sending {method} request to {url}: {str(e)}")
        return False, 0

async def generate_api_traffic(base_url, duration=60, requests_per_second=10, auth_token=None):
    """Generate API traffic for a specified duration."""
    try:
        # Create HTTP session
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            end_time = start_time + duration
            request_count = 0
            success_count = 0
            total_response_time = 0
            
            logger.info(f"Generating API traffic for {duration} seconds at {requests_per_second} requests per second")
            
            while time.time() < end_time:
                batch_start = time.time()
                batch_size = requests_per_second
                
                # Create a batch of requests
                tasks = []
                for _ in range(batch_size):
                    method = random.choice(HTTP_METHODS)
                    endpoint = random.choice(API_ENDPOINTS)
                    
                    # Special cases: Only POST to login, no DELETE for certain endpoints
                    if endpoint == "/apiauth/login":
                        method = "POST"
                    elif endpoint in ["/apiauth/refresh", "/apisettings"]:
                        method = random.choice(["GET", "POST", "PUT"])
                    
                    tasks.append(send_api_request(session, base_url, method, endpoint, auth_token))
                
                # Execute batch of requests
                results = await asyncio.gather(*tasks)
                
                # Process results
                batch_success = 0
                batch_response_time = 0
                
                for success, response_time in results:
                    request_count += 1
                    if success:
                        success_count += 1
                        batch_success += 1
                        total_response_time += response_time
                        batch_response_time += response_time
                
                # Log batch stats
                avg_response_time = batch_response_time / batch_success if batch_success > 0 else 0
                logger.info(f"Batch: {batch_success}/{batch_size} successful - Avg response time: {avg_response_time:.2f}ms")
                
                # Calculate time to sleep to maintain requests_per_second rate
                elapsed = time.time() - batch_start
                sleep_time = max(0, 1 - elapsed)  # Aim for 1 second per batch
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            # Log final stats
            test_duration = time.time() - start_time
            avg_response_time = total_response_time / success_count if success_count > 0 else 0
            requests_per_sec = request_count / test_duration
            
            logger.info(f"Traffic generation completed:")
            logger.info(f"- Duration: {test_duration:.2f} seconds")
            logger.info(f"- Total requests: {request_count}")
            logger.info(f"- Successful requests: {success_count} ({success_count/request_count*100:.1f}%)")
            logger.info(f"- Average response time: {avg_response_time:.2f}ms")
            logger.info(f"- Actual requests per second: {requests_per_sec:.2f}")
            
            return success_count
    
    except Exception as e:
        logger.error(f"Error generating API traffic: {str(e)}")
        return 0

async def main():
    parser = argparse.ArgumentParser(description="Generate API traffic for testing performance dashboards")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000",
                        help="Base URL for the API")
    parser.add_argument("--duration", type=int, default=60,
                        help="Duration of the test in seconds")
    parser.add_argument("--requests-per-second", type=int, default=10,
                        help="Number of requests to send per second")
    parser.add_argument("--auth-token", type=str,
                        help="Optional authentication token for authenticated requests")
    
    args = parser.parse_args()
    
    logger.info(f"Starting API traffic generator with the following parameters:")
    logger.info(f"- Base URL: {args.base_url}")
    logger.info(f"- Duration: {args.duration} seconds")
    logger.info(f"- Requests per second: {args.requests_per_second}")
    logger.info(f"- Auth token: {'Provided' if args.auth_token else 'Not provided'}")
    
    await generate_api_traffic(
        args.base_url,
        args.duration,
        args.requests_per_second,
        args.auth_token
    )

if __name__ == "__main__":
    asyncio.run(main())
