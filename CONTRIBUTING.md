# Contributing to Facebook Marketplace RSS Feed Generator

## Development Setup

1. Fork and clone the repository
2. Create your config file: `cp config.json.example config.json`
3. Modify config.json with your settings
4. Initialize the database: `python init_db.py`
5. Run the application: `python fb_ad_monitor.py`

## Making Changes

1. Create a new branch for your feature
2. Make your changes
3. Update config.json.example if you've added new configuration options
4. Update documentation as needed
5. Submit a pull request

## Docker Development

To build and test locally:

```bash
docker build -t yourusername/fb-mp-rss:latest .
docker-compose up -d
```
## CI/CD Process

The GitHub Actions workflow will:
1. Run on push to main branch
2. Build and test the application
3. Build and push Docker image if tests pass
4. Deploy to Docker Hub

Required secrets for CI/CD:
- DOCKERHUB_USERNAME
- DOCKERHUB_TOKEN