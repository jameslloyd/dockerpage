# Docker Container Dashboard

A beautiful Python Flask web application that displays all running Docker containers on a host along with their detailed attributes. The application runs in a Docker container and provides a modern, responsive web interface to monitor your Docker environment.

## Features

- 📊 **Real-time Dashboard**: View all containers (running, stopped, paused) with live statistics
- 🔄 **Auto-refresh**: Page automatically refreshes every 30 seconds
- 📱 **Responsive Design**: Modern Bootstrap-based UI that works on all devices
- 🐳 **Container Details**: Display comprehensive container information including:
  - Container ID, name, and status
  - Image information
  - Memory and CPU usage (for running containers)
  - Network configurations and IP addresses
  - Port mappings
  - Environment variables (sample)
  - Restart policies
  - Creation timestamps

- 🔌 **REST API**: JSON API endpoint for programmatic access
- 💊 **Health Checks**: Built-in health monitoring
- 🛡️ **Security**: Runs as non-root user in container

## Screenshots

The dashboard provides:
- Summary statistics cards showing total containers, running containers, images, and Docker version
- Grid layout of container cards with detailed information
- Color-coded status indicators
- Responsive design for desktop and mobile

## Quick Start

### Using Docker Compose (Recommended)

1. Clone or download the application:
```bash
git clone <your-repo> dockerpage
cd dockerpage
```

2. Build and run with Docker Compose:
```bash
docker-compose up -d
```

3. Open your browser and navigate to:
```
http://localhost:5000
```

### Using Docker Build

1. Build the Docker image:
```bash
docker build -t dockerpage .
```

2. Run the container:
```bash
docker run -d \
  --name docker-dashboard \
  -p 5000:5000 \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  dockerpage
```

### Local Development

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask application:
```bash
python app.py
```

**Note**: For local development, ensure your user has access to the Docker socket or run with appropriate permissions.

## Configuration

### Environment Variables

- `FLASK_ENV`: Set to `production` for production deployment (default in Docker)
- `FLASK_DEBUG`: Set to `True` for development (not recommended for production)

### Docker Socket Access

The application requires access to the Docker socket to communicate with the Docker daemon. This is achieved by mounting the socket as a volume:

```bash
-v /var/run/docker.sock:/var/run/docker.sock:ro
```

**Security Note**: Mounting the Docker socket gives the container access to the Docker daemon. Ensure you trust the application and run it in a secure environment.

## API Endpoints

### GET /
Main dashboard page displaying the web interface.

### GET /api/containers
Returns JSON array of all containers with their attributes.

Example response:
```json
[
  {
    "id": "abc123def456",
    "name": "web-server",
    "image": "nginx:latest",
    "status": "running",
    "created": "2025-07-14 10:30:00",
    "state": "running",
    "memory_usage": "45.2 MB",
    "memory_limit": "512.0 MB",
    "cpu_percent": "2.3%",
    "networks": [
      {
        "name": "bridge",
        "ip": "172.17.0.2"
      }
    ],
    "ports": ["80/tcp", "443/tcp"],
    "restart_policy": "unless-stopped"
  }
]
```

### GET /health
Health check endpoint returning application status.

## Deployment Considerations

### Production Deployment

1. **Reverse Proxy**: Consider using nginx or another reverse proxy for production
2. **HTTPS**: Implement SSL/TLS termination
3. **Authentication**: Add authentication if exposing to public networks
4. **Resource Limits**: Set appropriate memory and CPU limits for the container
5. **Monitoring**: Monitor the application logs and health endpoint

### Docker Swarm / Kubernetes

The application can be deployed in orchestrated environments. Ensure:
- Docker socket access is properly configured
- Service discovery is set up correctly
- Load balancing is configured if running multiple replicas

## Troubleshooting

### Common Issues

1. **"Unable to connect to Docker daemon"**
   - Ensure Docker is running
   - Check Docker socket permissions
   - Verify the socket is properly mounted in the container

2. **Permission denied accessing Docker socket**
   - Add the user to the docker group: `sudo usermod -aG docker $USER`
   - Restart the shell or container

3. **Container not showing statistics**
   - Some statistics require the container to be running
   - Check if the Docker API version is compatible

### Logs

View application logs:
```bash
docker logs docker-dashboard
```

View logs with Docker Compose:
```bash
docker-compose logs -f dockerpage
```

## Development

### Project Structure
```
dockerpage/
├── app.py                 # Main Flask application
├── templates/
│   ├── dashboard.html     # Main dashboard template
│   └── error.html         # Error page template
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container build instructions
├── docker-compose.yml    # Compose configuration
└── README.md            # This file
```

### Adding Features

The application is designed to be easily extensible:
- Add new routes in `app.py`
- Create new templates in `templates/`
- Modify the container information formatting in `format_container_info()`
- Add new API endpoints following the existing pattern

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the MIT License.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Docker and Flask documentation
3. Open an issue in the repository
