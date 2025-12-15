FROM opensearchproject/opensearch:2

USER root

# Fix permissions for the data directory
# Railway volumes are mounted with root ownership, but OpenSearch runs as non-root user
RUN chown -R opensearch:opensearch /usr/share/opensearch/data

USER opensearch

ENV discovery.type=single-node
ENV plugins.security.disabled=true
ENV OPENSEARCH_JAVA_OPTS="-Xms512m -Xmx512m"
ENV bootstrap.memory_lock=false
