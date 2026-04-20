# app/plugins/advanced_logging/loki_client.py
# A simple Loki HTTP client
import requests
import time
from typing import Dict, List, Any
import logging
import json
import socket
from urllib.parse import urlparse, urlencode

class LokiClient:
    def __init__(self, loki_url: str):
        """
        Initialize the client with a Loki URL.
        Example: http://loki:3100
        """
        import logging
        # Force use of the Docker service name regardless of the provided URL
        # This ensures connectivity within Docker Compose networks
        if "localhost" in loki_url:
            self.loki_url = loki_url.replace("localhost", "loki")
            logging.warning(f"Changed Loki URL from {loki_url} to {self.loki_url}")
        else:
            self.loki_url = loki_url
        
        logging.info(f"LokiClient initialized with URL: {self.loki_url}")
        self.loki_url = self.loki_url.rstrip("/")

    def push_log(self, level: str, message: str, labels: Dict[str, str] = None):
        """
        Minimal example of pushing a single log line to Loki's /loki/apipush
        """
        if labels is None:
            labels = {}
        # Some default labels
        labels.setdefault("job", "kaapi_advanced_logging")
        labels.setdefault("level", level)

        # Loki expects a timeseries payload with entries
        # https://grafana.com/docs/loki/latest/api/#post-lokiapiv1push
        timestamp_ns = int(time.time() * 1e9)

        streams = [
            {
                "stream": labels,
                "values": [
                    [
                        str(timestamp_ns),
                        message
                    ]
                ]
            }
        ]
        payload = {"streams": streams}

        url = f"{self.loki_url}/loki/apipush"
        try:
            logging.info(f"Sending log to Loki at: {url}")
            logging.info(f"Payload: {json.dumps(payload)}")
            
            # Try to establish a connection to verify Loki availability
            # Parse host and port from the Loki URL
            parsed_url = urlparse(self.loki_url)
            host = parsed_url.hostname
            port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
            
            logging.info(f"Testing connection to Loki at {host}:{port}")
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            try:
                s.connect((host, port))
                logging.info(f"Connection to Loki successful")
                s.close()
            except Exception as socket_error:
                logging.error(f"Cannot connect to Loki: {socket_error}")
                s.close()
                
            # Send the HTTP request
            resp = requests.post(url, json=payload, timeout=5)
            logging.info(f"Loki response status: {resp.status_code}")
            logging.info(f"Loki response headers: {resp.headers}")
            
            if resp.status_code != 204 and resp.status_code >= 400:
                logging.error(f"Loki error response: {resp.text}")
            resp.raise_for_status()
            logging.info("Successfully sent log to Loki")
            return True
        except requests.RequestException as e:
            logging.error(f"Error pushing log to Loki: {e}")
            logging.error(f"URL: {url}")
            if hasattr(e, 'response') and e.response:
                logging.error(f"Response status: {e.response.status_code}")
                logging.error(f"Response headers: {e.response.headers}")
                logging.error(f"Response content: {e.response.text}")
            return False
        except Exception as general_error:
            logging.error(f"Unexpected error when pushing to Loki: {general_error}")
            return False
    
    def query_logs(self, labels: Dict[str, str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Query logs from Loki using LogQL
        Returns a list of log entries with level, message, and labels
        """
        if labels is None:
            labels = {}
        
        # Build the LogQL query string from the labels
        query_parts = []
        for k, v in labels.items():
            query_parts.append(f'{k}="{v}"')
        
        logql_query = "{" + ", ".join(query_parts) + "}"
        params = {
            "query": logql_query,
            "limit": str(limit)
        }
        
        url = f"{self.loki_url}/loki/apiquery_range?{urlencode(params)}"
        logging.info(f"Querying Loki logs: {url}")
        
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                logging.error(f"Error querying Loki: {resp.status_code} - {resp.text}")
                return []
            
            data = resp.json()
            logging.info(f"Loki query response: {json.dumps(data)}")
            
            # Extract the log entries from the Loki response
            logs = []
            for stream in data.get("data", {}).get("result", []):
                stream_labels = stream.get("stream", {})
                level = stream_labels.get("level", "INFO")
                
                for value in stream.get("values", []):
                    timestamp, message = value
                    logs.append({
                        "level": level,
                        "message": message,
                        "labels": stream_labels
                    })
            
            logging.info(f"Retrieved {len(logs)} logs from Loki")
            return logs
        except Exception as e:
            logging.error(f"Error querying logs from Loki: {e}")
            # Return an empty list in case of error
            return []