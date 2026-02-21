# Contributing to Stake Mirrors Ping

Thank you for your interest in contributing! 🎉

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/stake-mirrors-ping.git
   cd stake-mirrors-ping
   ```
3. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Development Workflow

1. Create a new branch for your feature/fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes
3. Test your changes:
   ```bash
   python -m src.main
   ```
4. Commit with clear messages:
   ```bash
   git commit -m "feat: add support for new mirror"
   ```
5. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
6. Open a Pull Request

## Code Style

- Follow PEP 8 style guidelines
- Use type hints where applicable
- Keep functions focused and modular
- Add docstrings for new functions

## Adding New Mirrors

To add a new Stake mirror, edit [config.yaml](config.yaml):

```yaml
mirrors:
  - domain: newmirror.com
    https: true
    port: 443
```

## Pull Request Guidelines

- Keep PRs focused on a single feature/fix
- Update README.md if adding new features
- Include test results in PR description
- Reference any related issues

## Reporting Issues

- Use GitHub Issues
- Include your Python version, OS, and error messages
- Provide steps to reproduce the bug

## Questions?

Open an issue or start a discussion!
