FROM nousresearch/hermes-agent:latest

# --- Path B browser runtime: real Chrome on a virtual display, driven over CDP ---
# Provides: Google Chrome (CDP via --remote-debugging-port), Xvfb (headed-on-headless),
# Node + agent-browser CLI, and Playwright (connect_over_cdp; attaches to system Chrome,
# so no bundled-browser download is needed). amd64 base; on arm64 swap google-chrome-stable
# for `chromium`.
USER root
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg xvfb xauth fonts-liberation; \
    # Google Chrome stable
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
      | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg; \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list; \
    # Node 20 (for agent-browser CLI)
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -; \
    apt-get update; \
    apt-get install -y --no-install-recommends google-chrome-stable nodejs; \
    npm install -g agent-browser; \
    # Playwright python package into the Hermes venv (uv-managed, no pip module).
    # Driver only — connect_over_cdp attaches to system Chrome, so no browser download.
    uv pip install --python /opt/hermes/.venv/bin/python --no-cache "playwright>=1.40.0"; \
    /opt/hermes/.venv/bin/python -c "from playwright.async_api import async_playwright; print('playwright ok')"; \
    apt-get clean; rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/joblandagent/profile-template
COPY agent/distribution.yaml \
     agent/SOUL.md \
     agent/AGENTS.md \
     agent/CLAUDE.md \
     agent/config.yaml \
     agent/mcp.json \
     agent/.env.EXAMPLE \
     agent/README.md \
     agent/requirements.txt \
     agent/start-chrome.sh \
     /opt/joblandagent/profile-template/
COPY agent/config/ /opt/joblandagent/profile-template/config/
COPY agent/skills/ /opt/joblandagent/profile-template/skills/
COPY agent/scripts/ /opt/joblandagent/profile-template/scripts/
COPY docker/hermes-agent/bootstrap-profile.py /opt/joblandagent/bootstrap-profile.py
COPY docker/hermes-agent/main-wrapper.sh /opt/joblandagent/main-wrapper.sh

RUN chmod +x /opt/joblandagent/bootstrap-profile.py /opt/joblandagent/main-wrapper.sh

ENTRYPOINT ["/init", "/opt/joblandagent/main-wrapper.sh"]
CMD ["gateway", "run"]
