#!/command/with-contenv sh
set -e

python /opt/joblandagent/bootstrap-profile.py
exec /opt/hermes/docker/main-wrapper.sh "$@"
