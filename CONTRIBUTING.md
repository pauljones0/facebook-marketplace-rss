# Contributing to Facebook Marketplace RSS Feed Generator

Thank you for your interest in contributing! To keep things clear:

- **Installation & Setup:**  
  All common setup steps (cloning the repository, installing dependencies, creating the configuration file, initializing the database, etc.) are documented in the [README Installation section](README.md#installation). Please follow those instructions first.

## Getting Started for Contributors

1. **Fork and Clone:**  
   - Fork the repository on GitHub.
   - Clone your fork locally.

2. **Set Up Your Development Environment:**
   - Copy the configuration file:
     ```bash
     cp config.json.example config.json
     ```
   - Modify `config.json` with your settings.
   - Initialize the database:
     ```bash
     python init_db.py
     ```
   - Run the application to verify that everything works:
     ```bash
     python fb_ad_monitor.py
     ```

## Contributing Workflow

1. **Create a New Branch:**  
   Develop your feature or bug fix on its own branch.

2. **Make Your Changes:**  
   - Implement and test your changes.
   - If you introduce new configuration options, update `config.json.example` accordingly.
   - Update documentation as needed.

3. **Submit a Pull Request:**  
   Once your changes are ready and tested, submit a pull request for review.

## Docker Development

For containerized development, you can build and run the Docker container locally:
```bash
docker build -t yourusername/fb-mp-rss:latest .
docker-compose up -d
```

## CI/CD Process

Our GitHub Actions workflow will:
- Run tests on every push to the main branch.
- Build and test the application.
- Build and push a Docker image if tests pass.
- Deploy to Docker Hub.

*Please ensure your contributions pass all tests and build steps before submitting your pull request.*

## Required Secrets
If you're maintaining a fork that deploys to Docker Hub, follow the [secret setup instructions](README.md#required-secrets) in the README. Contributors don't need this unless they're maintaining their own deployment pipeline.

## Local Testing Guidelines

**Install Testing Dependencies:**
```bash
pip install -r requirements.txt
```

**Running Tests:**
1. Start the Selenium container:
   ```bash
   docker-compose up -d selenium
   ```

2. Run all tests (with verbose output):
   ```bash
   pytest -v
   ```

3. Specific test types:
   ```bash
   # Selenium tests
   pytest tests/test_selenium* -m "selenium or selenium_container"

   # Database tests
   pytest tests/test_database.py

   # Property-based tests
   pytest tests/test_property_based.py --hypothesis-show-statistics
   ```

**Important Notes:**
- The Selenium container must be running for integration tests.
- Add the `-s` flag to see print outputs.
- Run `docker-compose down` when finished testing

Happy coding!