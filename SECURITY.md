# Security Policy

## Supported Versions

We actively support the following versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of Stake Mirrors Ping seriously. If you discover a security vulnerability, please follow these steps:

### 🔒 Private Disclosure

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security issues privately:

1. **Email:** Send details to the repository owner via GitHub
2. **GitHub Security Advisories:** Use [GitHub's private vulnerability reporting](https://github.com/subkoks/stake-mirrors-ping/security/advisories/new)

### 📋 What to Include

Please include as much information as possible:

- Type of vulnerability (e.g., XSS, SQL injection, credential exposure)
- Full paths of affected source file(s)
- Location of the affected code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact assessment
- Suggested fix (if you have one)

### ⏱️ Response Timeline

- **Initial Response:** Within 48 hours
- **Status Update:** Within 7 days
- **Fix Timeline:** Depends on severity
  - Critical: 1-7 days
  - High: 7-30 days
  - Medium: 30-90 days
  - Low: 90+ days or next release

### 🎯 Security Best Practices for Users

When using this tool:

1. **Protect Your Session Token**
   - Never commit `.env` files to version control
   - Use `.env.example` as a template
   - Rotate tokens regularly

2. **Network Security**
   - Be aware that this tool makes requests to multiple domains
   - Use VPN if testing from sensitive networks
   - Review `config.yaml` before running

3. **API Keys**
   - Keep your Stake session token private
   - Don't share session tokens in screenshots or logs
   - Session tokens expire automatically

4. **Dependencies**
   - Keep dependencies updated: `pip install --upgrade -r requirements.txt`
   - Review dependency alerts on GitHub
   - Use virtual environments

### 🏆 Recognition

We appreciate responsible disclosure. Security researchers who report valid vulnerabilities will be:

- Credited in the security advisory (unless you prefer anonymity)
- Acknowledged in the CHANGELOG
- Given our sincere thanks! 🙏

## Known Security Considerations

### Session Tokens
This tool requires a Stake session token for API features. These tokens:
- Are stored in `.env` (excluded from git via `.gitignore`)
- Are transmitted over HTTPS only
- Should be kept confidential
- Expire after a period of inactivity

### Network Requests
The tool makes requests to:
- Multiple Stake mirror domains
- GeoIP lookup services
- NordVPN API (for recommendations)

All HTTPS requests use certificate verification.

### Data Storage
- SQLite database (`history.db`) stores latency history locally
- No sensitive data is stored in the database
- Database is excluded from git by default

## Questions?

For general security questions (non-vulnerabilities), open a [GitHub Discussion](https://github.com/subkoks/stake-mirrors-ping/discussions).
