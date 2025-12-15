FROM opensearchproject/opensearch:2

USER root

# Copy custom entrypoint script that fixes permissions at runtime
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Environment variables for single-node setup
ENV discovery.type=single-node
ENV plugins.security.disabled=true
ENV OPENSEARCH_JAVA_OPTS="-Xms512m -Xmx512m"
ENV bootstrap.memory_lock=false

# Run as root so entrypoint can fix permissions, then it switches to opensearch user
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
