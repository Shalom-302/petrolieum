#!/bin/bash

# Script to manage Docker operations for Kaapi API
# Usage: ./docker-run.sh [command] [options]
# Commands:
#   up: Start all containers
#   down: Stop all containers
#   build: Rebuild containers
#   logs: View logs
#   restart: Restart all containers
#   api: Bash into the API container
#   db: Connect to PostgreSQL
#   redis: Connect to Redis CLI
#   api-logs: Follow API logs in real-time (development mode)
#   restart-api: Restart only the API container (for quick development)
#   dev: Start in development mode with API logs in foreground
# Options:
#   --monitoring: Include monitoring services (Prometheus, Grafana, Loki, etc.)

set -e

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Default command
COMMAND=${1:-up}
MONITORING=false

# Parse arguments
shift 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --monitoring)
            MONITORING=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Compose command with monitoring if requested
if [ "$MONITORING" = true ]; then
    COMPOSE_CMD="docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml"
    echo "🔍 Monitoring enabled - Prometheus, Grafana and Loki services will be included"
    echo "   Grafana: http://localhost:3002 (admin/admin)"
    echo "   Prometheus: http://localhost:9090"
    echo "   Alertmanager: http://localhost:9093"
else
    COMPOSE_CMD="docker-compose"
fi

case "$COMMAND" in
    up)
        echo "Starting containers..."
        $COMPOSE_CMD up -d
        echo "Containers started! API is available at http://localhost:8000"
        ;;
    down)
        echo "Stopping containers..."
        $COMPOSE_CMD down
        echo "Containers stopped!"
        ;;
    build)
        echo "Rebuilding containers..."
        $COMPOSE_CMD build
        echo "Build complete!"
        ;;
    logs)
        echo "Showing logs (Ctrl+C to exit)..."
        $COMPOSE_CMD logs -f
        ;;
    restart)
        echo "Restarting containers..."
        $COMPOSE_CMD restart
        echo "Containers restarted!"
        ;;
    api)
        echo "Opening shell in API container..."
        $COMPOSE_CMD exec api bash
        ;;
    db)
        echo "Connecting to PostgreSQL..."
        $COMPOSE_CMD exec kaapi-db psql -U postgres -d kaapi
        ;;
    redis)
        echo "Connecting to Redis CLI..."
        $COMPOSE_CMD exec redis redis-cli
        ;;
    api-logs)
        echo "Following API logs in real-time (Ctrl+C to exit)..."
        $COMPOSE_CMD logs -f api
        ;;
    restart-api)
        echo "Restarting API container..."
        $COMPOSE_CMD restart api
        echo "API restarted!"
        ;;
    dev)
        echo "Starting in development mode with API logs in foreground..."
        if [ "$MONITORING" = true ]; then
            $COMPOSE_CMD up -d kaapi-db redis celery prometheus grafana loki alertmanager promtail
            $COMPOSE_CMD up api
        else
            $COMPOSE_CMD up -d kaapi-db redis celery
            $COMPOSE_CMD up api
        fi
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Available commands: up, down, build, logs, restart, api, db, redis, api-logs, restart-api, dev"
        echo "Options: --monitoring (to enable monitoring services)"
        exit 1
        ;;
esac
