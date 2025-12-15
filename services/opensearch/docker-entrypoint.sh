#!/bin/bash
set -e

# Fix permissions on the data directory at runtime
# This is needed because Railway mounts volumes after the container starts
chown -R opensearch:opensearch /usr/share/opensearch/data

# Switch to opensearch user and run OpenSearch using gosu
exec gosu opensearch /usr/share/opensearch/opensearch-docker-entrypoint.sh
