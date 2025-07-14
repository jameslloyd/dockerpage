#!/bin/bash
# Docker Dashboard Deployment Script

set -e

echo "🐳 Docker Container Dashboard Deployment"
echo "========================================"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Error: Docker is not running or not accessible"
    echo "Please start Docker and try again"
    exit 1
fi

echo "✅ Docker is running"

# Function to build and run
build_and_run() {
    echo "🏗️  Building Docker image..."
    docker build -t dockerpage .
    
    echo "🚀 Starting container..."
    docker run -d \
        --name docker-dashboard \
        -p 5000:5000 \
        -v /var/run/docker.sock:/var/run/docker.sock:ro \
        --restart unless-stopped \
        dockerpage
    
    echo "✅ Container started successfully!"
    echo "🌐 Dashboard available at: http://localhost:5000"
}

# Function to use docker-compose
compose_run() {
    echo "🏗️  Building and starting with Docker Compose..."
    docker-compose up -d --build
    
    echo "✅ Services started successfully!"
    echo "🌐 Dashboard available at: http://localhost:5000"
}

# Function to stop and cleanup
cleanup() {
    echo "🧹 Cleaning up..."
    
    # Stop and remove container
    if docker ps -q -f name=docker-dashboard | grep -q .; then
        docker stop docker-dashboard
        docker rm docker-dashboard
    fi
    
    # Or stop compose services
    if [ -f docker-compose.yml ]; then
        docker-compose down
    fi
    
    echo "✅ Cleanup complete"
}

# Function to show logs
show_logs() {
    if docker ps -q -f name=docker-dashboard | grep -q .; then
        echo "📋 Container logs:"
        docker logs -f docker-dashboard
    elif [ -f docker-compose.yml ]; then
        echo "📋 Service logs:"
        docker-compose logs -f
    else
        echo "❌ No running containers found"
    fi
}

# Function to show status
show_status() {
    echo "📊 Current Status:"
    echo "=================="
    
    if docker ps -q -f name=docker-dashboard | grep -q .; then
        echo "✅ Container is running"
        docker ps -f name=docker-dashboard --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        echo "❌ Container is not running"
    fi
    
    echo ""
    echo "🌐 Test connection:"
    if curl -s http://localhost:5000/health >/dev/null 2>&1; then
        echo "✅ Dashboard is accessible at http://localhost:5000"
    else
        echo "❌ Dashboard is not accessible"
    fi
}

# Parse command line arguments
case "${1:-}" in
    "build")
        cleanup
        build_and_run
        ;;
    "compose")
        cleanup
        compose_run
        ;;
    "stop")
        cleanup
        ;;
    "logs")
        show_logs
        ;;
    "status")
        show_status
        ;;
    "dev")
        echo "🔧 Starting development mode..."
        echo "Installing dependencies..."
        pip install -r requirements.txt
        echo "Starting Flask development server..."
        python app.py
        ;;
    *)
        echo "Usage: $0 {build|compose|stop|logs|status|dev}"
        echo ""
        echo "Commands:"
        echo "  build    - Build and run with Docker"
        echo "  compose  - Build and run with Docker Compose"
        echo "  stop     - Stop and cleanup containers"
        echo "  logs     - Show container logs"
        echo "  status   - Show current status"
        echo "  dev      - Run in development mode (local Python)"
        echo ""
        echo "Examples:"
        echo "  $0 compose  # Recommended for most users"
        echo "  $0 build    # Direct Docker build"
        echo "  $0 status   # Check if running"
        echo "  $0 logs     # View logs"
        echo "  $0 stop     # Stop everything"
        exit 1
        ;;
esac
