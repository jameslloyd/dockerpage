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
    "prod")
        echo "🚀 Starting production mode..."
        echo "Installing dependencies..."
        pip3 install -r requirements.txt
        
        # Check Docker socket permissions
        echo "🔍 Checking Docker socket permissions..."
        if [ -S /var/run/docker.sock ]; then
            echo "✅ Docker socket found"
            ls -la /var/run/docker.sock
            
            # Test Docker connection
            if python3 -c "import docker; docker.from_env().ping()" 2>/dev/null; then
                echo "✅ Docker connection successful"
            else
                echo "⚠️  Docker connection test failed - checking permissions..."
                echo "💡 Note: 'Could not adjust Docker socket permissions' messages are normal in some environments"
                
                # Try to add user to docker group
                if ! groups $USER | grep -q docker; then
                    echo "Adding $USER to docker group..."
                    sudo usermod -aG docker $USER
                    echo "⚠️  Please log out and log back in, then run this script again"
                    exit 0
                fi
            fi
        else
            echo "❌ Docker socket not found at /var/run/docker.sock"
            exit 1
        fi
        
        echo "Starting production server with gunicorn..."
        # Install gunicorn if not present
        if ! command -v gunicorn &> /dev/null; then
            echo "Installing gunicorn..."
            pip3 install gunicorn
        fi
        
        # Create logs directory in current directory if it doesn't exist
        mkdir -p logs
        
        echo "✅ Starting gunicorn server on port 5000..."
        echo "💡 Logs will be written to ./logs/ directory"
        echo "🌐 Dashboard will be available at: http://localhost:5000"
        echo "� To disable stats collection if experiencing issues: export DISABLE_STATS=true"
        echo "�🛑 Press Ctrl+C to stop the server"
        echo ""
        
        # Start gunicorn with proper logging to local directory
        gunicorn \
            --bind 0.0.0.0:5000 \
            --workers 4 \
            --timeout 120 \
            --access-logfile ./logs/access.log \
            --error-logfile ./logs/error.log \
            --log-level info \
            --capture-output \
            app:app
        ;;
    "prod-no-stats")
        echo "🚀 Starting production mode (stats disabled)..."
        echo "Installing dependencies..."
        pip3 install -r requirements.txt
        
        # Check Docker socket permissions
        echo "🔍 Checking Docker socket permissions..."
        if [ -S /var/run/docker.sock ]; then
            echo "✅ Docker socket found"
            ls -la /var/run/docker.sock
            
            # Test Docker connection
            if python3 -c "import docker; docker.from_env().ping()" 2>/dev/null; then
                echo "✅ Docker connection successful"
            else
                echo "⚠️  Docker connection test failed - checking permissions..."
                echo "💡 Note: 'Could not adjust Docker socket permissions' messages are normal in some environments"
                
                # Try to add user to docker group
                if ! groups $USER | grep -q docker; then
                    echo "Adding $USER to docker group..."
                    sudo usermod -aG docker $USER
                    echo "⚠️  Please log out and log back in, then run this script again"
                    exit 0
                fi
            fi
        else
            echo "❌ Docker socket not found at /var/run/docker.sock"
            exit 1
        fi
        
        # Create logs directory in current directory if it doesn't exist
        mkdir -p logs
        
        echo "✅ Starting gunicorn server on port 5000 (stats disabled)..."
        echo "💡 Logs will be written to ./logs/ directory"
        echo "🌐 Dashboard will be available at: http://localhost:5000"
        echo "⚡ Stats collection is disabled for better performance"
        echo "🛑 Press Ctrl+C to stop the server"
        echo ""
        
        # Start gunicorn with stats disabled
        DISABLE_STATS=true gunicorn \
            --bind 0.0.0.0:5000 \
            --workers 4 \
            --timeout 120 \
            --access-logfile ./logs/access.log \
            --error-logfile ./logs/error.log \
            --log-level info \
            --capture-output \
            app:app
        ;;
    "install")
        echo "🔧 Installing Docker Dashboard as a system service..."
        
        # Check if running as root or with sudo
        if [ "$EUID" -ne 0 ]; then
            echo "❌ This command requires root privileges. Please run with sudo:"
            echo "   sudo $0 install"
            exit 1
        fi
        
        # Install to /opt/dockerpage
        echo "📁 Installing to /opt/dockerpage..."
        mkdir -p /opt/dockerpage
        cp -r . /opt/dockerpage/
        chown -R www-data:www-data /opt/dockerpage
        
        # Create log directory
        mkdir -p /var/log/dockerpage
        chown www-data:www-data /var/log/dockerpage
        
        # Add www-data to docker group
        usermod -aG docker www-data
        
        # Install Python dependencies
        cd /opt/dockerpage
        pip3 install -r requirements.txt
        pip3 install gunicorn
        
        # Install systemd service
        cp dockerpage.service /etc/systemd/system/
        systemctl daemon-reload
        systemctl enable dockerpage
        systemctl start dockerpage
        
        echo "✅ Docker Dashboard installed as system service!"
        echo "🔧 Service commands:"
        echo "   sudo systemctl status dockerpage   # Check status"
        echo "   sudo systemctl restart dockerpage  # Restart service"
        echo "   sudo systemctl logs dockerpage     # View logs"
        echo "🌐 Dashboard available at: http://localhost:5000"
        ;;
    *)
        echo "Usage: $0 {build|compose|stop|logs|status|dev|prod|prod-no-stats|install}"
        echo ""
        echo "Commands:"
        echo "  build         - Build and run with Docker"
        echo "  compose       - Build and run with Docker Compose"
        echo "  stop          - Stop and cleanup containers"
        echo "  logs          - Show container logs"
        echo "  status        - Show current status"
        echo "  dev           - Run in development mode (local Python)"
        echo "  prod          - Run in production mode with gunicorn"
        echo "  prod-no-stats - Run in production mode with stats disabled"
        echo "  install       - Install as system service (requires sudo)"
        echo ""
        echo "Examples:"
        echo "  $0 compose         # Recommended for Docker deployment"
        echo "  $0 prod            # Recommended for server deployment"
        echo "  $0 prod-no-stats   # If experiencing stats collection issues"
        echo "  sudo $0 install    # Install as system service"
        echo "  $0 build           # Direct Docker build"
        echo "  $0 status          # Check if running"
        echo "  $0 logs            # View logs"
        echo "  $0 stop            # Stop everything"
        exit 1
        ;;
esac
