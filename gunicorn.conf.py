# Gunicorn configuration file
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
user = "www-data"
group = "www-data"
preload_app = True
enable_stdio_inheritance = True
accesslog = "/var/log/dockerpage/access.log"
errorlog = "/var/log/dockerpage/error.log"
loglevel = "info"
capture_output = True
