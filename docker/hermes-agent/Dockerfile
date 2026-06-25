FROM nousresearch/hermes-agent:latest

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
