"""
Utility functions for the Docker dashboard application.
"""

def get_host_url_for_containers(current_host):
    """Get the appropriate host URL for building container links based on current Docker host."""
    import os
    
    # If we're connected to a remote TCP host, use its IP address
    if current_host and current_host.get('host', '').startswith('tcp://'):
        tcp_host = current_host.get('host', '')
        try:
            # Extract IP address from tcp://ip:port format
            ip_address = tcp_host.split('://')[1].split(':')[0]
            return ip_address
        except (IndexError, AttributeError):
            pass
    
    # Fall back to HOST_URL environment variable for local or invalid configs
    host_url = os.getenv('HOST_URL', 'localhost')
    # Remove protocol if present, we'll add http://
    if host_url.startswith(('http://', 'https://')):
        host_url = host_url.split('://', 1)[1]
    return host_url
