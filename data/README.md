# Data Directory

This directory contains user configuration files for the Docker Dashboard:

## Files

- `docker_hosts.json` - Docker host configurations and connection settings
- `self_hosted_apps.json` - Self-hosted applications and their metadata

## Important Notes

- These files are automatically created when you first configure hosts or apps
- They contain sensitive information like connection details and credentials
- The files are excluded from version control via `.gitignore`
- Backup these files if you want to preserve your configurations

## File Permissions

Ensure this directory is readable/writable by the application user:
```bash
chmod 755 data/
chmod 644 data/*.json
```
