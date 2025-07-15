# Docker Container Dashboard

A beautiful Python Flask web application that displays all running Docker containers on a host along with their detailed attributes. The application runs in a Docker container and provides a modern, responsive web interface to monitor your Docker environment.

## ✅ Multi-Host Support - Now Available!

**Complete multi-host Docker management has been successfully implemented!** You can now:

- **Connect to Multiple Docker Hosts**: Local and remote Docker daemons
- **Switch Between Hosts**: Easy dropdown selector in the main dashboard
- **Manage Host Configurations**: Add, edit, delete, and test Docker host connections
- **Secure Connections**: Support for TLS/SSL certificates and SSH tunnels
- **Real-time Testing**: Test connectivity and view system information for each host

**Quick Setup**: After running the dashboard, visit `/hosts` to add your remote Docker servers!

## Features

- 📊 **Real-time Dashboard**: View all containers (running, stopped, paused) with live statistics
- 🔄 **Auto-refresh**: Page automatically refreshes every 30 seconds
- 📱 **Responsive Design**: Modern Bootstrap-based UI that works on all devices
- �️ **Multi-Host Support**: Connect to and switch between multiple Docker hosts (local and remote)
- 🔧 **Host Management**: Add, edit, delete, and test Docker host connections
- 🔒 **TLS Support**: Secure connections to remote Docker daemons with TLS certificates
- �🐳 **Container Details**: Display comprehensive container information including:
  - Container ID, name, and status
  - Health status indicators
  - Image information
  - Memory and CPU usage (for running containers)
  - Network configurations and IP addresses
  - Port mappings
  - Environment variables (sample)
  - Restart policies
  - Creation timestamps

- 🧹 **Resource Cleanup**: View unused Docker resources (volumes, images, networks)
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

The application supports several environment variables for configuration and performance tuning:

- `HOST_URL`: Base URL for building container links (default: `http://localhost:5000`)
- `FLASK_ENV`: Set to `production` for production deployment (default in Docker)
- `FLASK_DEBUG`: Set to `True` for development (not recommended for production)
- `SECRET_KEY`: Flask secret key for session management (default: auto-generated)

### Multi-Host Docker Management

The dashboard supports connecting to multiple Docker hosts (local and remote). Hosts are configured through the web interface at `/hosts` or via the dropdown in the main dashboard.

#### Adding Remote Docker Hosts

1. **Navigate to Host Management**: Click the server icon in the dashboard navbar or visit `/hosts`

2. **Add New Host**: Click "Add Host" and configure:
   - **Host ID**: Unique identifier (e.g., `production`, `staging`)
   - **Display Name**: Human-readable name (e.g., "Production Server")
   - **Docker Host URL**: Connection string for the Docker daemon
   - **TLS Verification**: Enable for secure connections
   - **Certificate Path**: Path to TLS certificates (if TLS enabled)
   - **Description**: Optional description

#### Docker Host URL Formats

**Local Docker Daemon:**
```
unix:///var/run/docker.sock
```

**Remote Docker over TCP (insecure):**
```
tcp://192.168.1.100:2375
```

**Remote Docker over TLS:**
```
tcp://192.168.1.100:2376
```

**SSH Tunnel:**
```
ssh://user@192.168.1.100
```

#### Setting up Remote Docker Access

**Option 1: Enable Docker TCP Socket (Insecure - for testing only)**
```bash
# On remote host
sudo systemctl edit docker.service

# Add the following:
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd -H fd:// -H tcp://0.0.0.0:2375

sudo systemctl daemon-reload
sudo systemctl restart docker
```

**Option 2: Enable Docker with TLS (Recommended)**
```bash
# On remote host - generate certificates
mkdir -p /etc/docker/certs
cd /etc/docker/certs

# Generate CA private key
openssl genrsa -aes256 -out ca-key.pem 4096

# Generate CA certificate
openssl req -new -x509 -days 365 -key ca-key.pem -sha256 -out ca.pem

# Generate server key
openssl genrsa -out server-key.pem 4096

# Generate server certificate signing request
openssl req -subj "/CN=your-server-hostname" -sha256 -new -key server-key.pem -out server.csr

# Sign the server certificate
openssl x509 -req -days 365 -sha256 -in server.csr -CA ca.pem -CAkey ca-key.pem -out server-cert.pem -CAcreateserial

# Generate client key and certificate
openssl genrsa -out key.pem 4096
openssl req -subj '/CN=client' -new -key key.pem -out client.csr
openssl x509 -req -days 365 -sha256 -in client.csr -CA ca.pem -CAkey ca-key.pem -out cert.pem -CAcreateserial

# Configure Docker daemon
sudo systemctl edit docker.service

# Add the following:
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd --tlsverify --tlscacert=/etc/docker/certs/ca.pem --tlscert=/etc/docker/certs/server-cert.pem --tlskey=/etc/docker/certs/server-key.pem -H=0.0.0.0:2376 -H fd://

sudo systemctl daemon-reload
sudo systemctl restart docker
```

Copy `ca.pem`, `cert.pem`, and `key.pem` to your dashboard host and configure the certificate path in the host settings.

**Option 3: SSH Tunnel (Simple and Secure)**
```bash
# On dashboard host, create SSH tunnel
ssh -f -N -L 2375:localhost:2375 user@remote-host

# Then add host with URL: tcp://localhost:2375
```

#### Host Configuration File

Host configurations are stored in `data/docker_hosts.json` in the application directory:

```json
{
  "hosts": {
    "local": {
      "name": "Local Docker",
      "host": "unix:///var/run/docker.sock",
      "tls_verify": false,
      "cert_path": "",
      "description": "Local Docker daemon",
      "default": true
    },
    "production": {
      "name": "Production Server",
      "host": "tcp://192.168.1.100:2376",
      "tls_verify": true,
      "cert_path": "/path/to/certs",
      "description": "Production Docker host"
    }
  },
  "current_host": "local"
}
```

#### Switching Between Hosts

- **Web Interface**: Use the dropdown in the navbar or switch buttons in host management
- **API**: POST to `/api/hosts/{host_id}/switch`

The dashboard maintains the current host selection in the user session and automatically reconnects when switching hosts.

### Performance Optimization

For environments with many containers or slower Docker APIs, the following settings can significantly improve page load times:

- `FAST_INITIAL_LOAD`: Use lightweight container formatting for faster initial load (default: `true`)
- `SKIP_INITIAL_STATS`: Skip resource-intensive stats collection on initial page load (default: `true`)
- `ENABLE_STATS`: Enable detailed CPU and memory stats collection (default: `false`)

**Performance Mode (Default)**:
```bash
FAST_INITIAL_LOAD=true
SKIP_INITIAL_STATS=true  
ENABLE_STATS=false
```

**Full Details Mode** (slower initial load, but more information):
```bash
FAST_INITIAL_LOAD=false
SKIP_INITIAL_STATS=false
ENABLE_STATS=true
```

With the default performance settings:
- Initial page loads are 5-10x faster
- Container stats are loaded asynchronously after the page renders
- Stats are refreshed every 10 seconds for running containers
- Unused resources are loaded only when the "Unused Resources" tab is clicked

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
