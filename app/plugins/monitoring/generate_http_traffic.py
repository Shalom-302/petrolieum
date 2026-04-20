#!/usr/bin/env python3
"""
Script to generate HTTP traffic with various status codes for testing Grafana dashboards
This script sends requests to API endpoints to generate diverse HTTP status codes
for the http-status dashboard.
"""
import asyncio
import argparse
import random
import aiohttp
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("http_traffic_generator")

# Define endpoints that will predictably return specific status codes
STATUS_ENDPOINTS = {
    # 2xx - Success
    200: ["/apiusers", "/apiproducts", "/"],
    201: ["/apiusers", "/apiproducts"],
    
    # 3xx - Redirection
    301: ["/old-endpoint", "/deprecated"],
    302: ["/temp-redirect", "/login-redirect"],
    
    # 4xx - Client errors
    400: ["/apiusers/invalid", "/apiproducts?invalid=true"],
    401: ["/apisecure/endpoint", "/apiadmin/settings"],
    403: ["/apiadmin/users", "/apirestricted"],
    404: ["/not-found", "/missing", "/apiproducts/9999"],
    429: ["/apirate-limited"],
    
    # 5xx - Server errors
    500: ["/apierror", "/apiserver-error"],
    503: ["/apimaintenance", "/apioverloaded"]
}

# HTTP methods to use for each status code
STATUS_METHODS = {
    200: ["GET"],
    201: ["POST"],
    301: ["GET"],
    302: ["GET"],
    400: ["GET", "POST"],
    401: ["GET", "POST"],
    403: ["GET", "POST"],
    404: ["GET"],
    429: ["GET", "POST"],
    500: ["GET", "POST"],
    503: ["GET"]
}

# Weighted distribution of status codes (for realistic traffic)
STATUS_WEIGHTS = {
    200: 70,  # Most requests should be successful
    201: 10,
    301: 2,
    302: 3,
    400: 5,
    401: 3,
    403: 2,
    404: 3,
    429: 1,
    500: 0.5,
    503: 0.5
}

async def send_http_request(session, base_url, status_code):
    """Send a request designed to generate a specific HTTP status code."""
    try:
        # Select a random endpoint for this status code
        if status_code in STATUS_ENDPOINTS and STATUS_ENDPOINTS[status_code]:
            endpoint = random.choice(STATUS_ENDPOINTS[status_code])
        else:
            # Fallback for any undefined status codes
            endpoint = f"/apistatus/{status_code}"
        
        # Select an appropriate HTTP method
        if status_code in STATUS_METHODS and STATUS_METHODS[status_code]:
            method = random.choice(STATUS_METHODS[status_code])
        else:
            method = "GET"
        
        url = f"{base_url}{endpoint}"
        headers = {"User-Agent": "HTTP-Status-Test/1.0"}
        
        # Add appropriate headers or payloads to trigger specific status codes
        if status_code == 201:
            # For 201 Created, we need to send data
            payload = {"name": f"Test {random.randint(1, 1000)}", "timestamp": datetime.now().isoformat()}
            async with session.post(url, headers=headers, json=payload) as response:
                return response.status
                
        elif status_code == 401:
            # For 401 Unauthorized, don't send auth token
            async with session.request(method, url, headers=headers) as response:
                return response.status
                
        elif status_code == 400:
            # For 400 Bad Request, send invalid data
            if method == "POST":
                payload = {"invalid": "data", "missing_required": True}
                async with session.post(url, headers=headers, json=payload) as response:
                    return response.status
            else:
                async with session.get(url, headers=headers) as response:
                    return response.status
        
        elif status_code == 429:
            # For 429 Too Many Requests, send multiple requests quickly
            for _ in range(5):  # Send 5 quick requests to trigger rate limiting
                async with session.request(method, url, headers=headers) as response:
                    if response.status == 429:
                        return 429
            return 0  # If we didn't get a 429, return 0
        
        else:
            # For other status codes, just send the request
            async with session.request(method, url, headers=headers) as response:
                return response.status
    
    except Exception as e:
        logger.error(f"Error sending request for status {status_code}: {str(e)}")
        return 0

async def generate_http_traffic(base_url, duration=60, requests_per_second=5):
    """Generate HTTP traffic with various status codes for testing dashboards."""
    try:
        # Create HTTP session
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            end_time = start_time + duration
            request_count = 0
            status_counts = {status: 0 for status in STATUS_WEIGHTS.keys()}
            
            logger.info(f"Generating HTTP traffic for {duration} seconds at {requests_per_second} requests per second")
            
            # Normalize weights to sum to 1.0
            total_weight = sum(STATUS_WEIGHTS.values())
            normalized_weights = {
                status: weight / total_weight 
                for status, weight in STATUS_WEIGHTS.items()
            }
            
            # Create list of status codes and weights for random.choices
            status_codes = list(normalized_weights.keys())
            weights = list(normalized_weights.values())
            
            while time.time() < end_time:
                batch_start = time.time()
                batch_size = requests_per_second
                
                # Create a batch of requests
                tasks = []
                selected_statuses = random.choices(
                    status_codes, 
                    weights=weights, 
                    k=batch_size
                )
                
                for status in selected_statuses:
                    tasks.append(send_http_request(session, base_url, status))
                
                # Execute batch of requests
                results = await asyncio.gather(*tasks)
                
                # Process results
                for status in results:
                    request_count += 1
                    if status in status_counts:
                        status_counts[status] += 1
                    
                # Log progress
                if request_count % (requests_per_second * 5) == 0:  # Log every 5 seconds
                    elapsed = time.time() - start_time
                    logger.info(f"Sent {request_count} requests in {elapsed:.1f} seconds ({request_count/elapsed:.1f} req/sec)")
                
                # Calculate time to sleep to maintain requests_per_second rate
                elapsed = time.time() - batch_start
                sleep_time = max(0, 1 - elapsed)  # Aim for 1 second per batch
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            # Log final stats
            test_duration = time.time() - start_time
            requests_per_sec = request_count / test_duration
            
            logger.info(f"HTTP traffic generation completed:")
            logger.info(f"- Duration: {test_duration:.2f} seconds")
            logger.info(f"- Total requests: {request_count}")
            logger.info(f"- Actual requests per second: {requests_per_sec:.2f}")
            logger.info("- Status code distribution:")
            
            for status, count in sorted(status_counts.items()):
                if count > 0:
                    percentage = (count / request_count) * 100
                    logger.info(f"  {status}: {count} requests ({percentage:.1f}%)")
            
            return request_count
    
    except Exception as e:
        logger.error(f"Error generating HTTP traffic: {str(e)}")
        return 0

async def main():
    parser = argparse.ArgumentParser(description="Generate HTTP traffic with various status codes for testing dashboards")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000",
                        help="Base URL for the API")
    parser.add_argument("--duration", type=int, default=60,
                        help="Duration of the test in seconds")
    parser.add_argument("--requests-per-second", type=int, default=5,
                        help="Number of requests to send per second")
    
    args = parser.parse_args()
    
    logger.info(f"Starting HTTP traffic generator with the following parameters:")
    logger.info(f"- Base URL: {args.base_url}")
    logger.info(f"- Duration: {args.duration} seconds")
    logger.info(f"- Requests per second: {args.requests_per_second}")
    
    await generate_http_traffic(
        args.base_url,
        args.duration,
        args.requests_per_second
    )

if __name__ == "__main__":
    asyncio.run(main())
