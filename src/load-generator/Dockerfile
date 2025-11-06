# Simple Alpine Linux container with curl for load generation
FROM alpine:3.18

# Install curl and bash
RUN apk add --no-cache curl bash

# Copy the load generator script
COPY load-generator.sh /usr/local/bin/load-generator.sh

# Make script executable
RUN chmod +x /usr/local/bin/load-generator.sh

# Create non-root user
RUN addgroup -g 1001 -S loadgen
RUN adduser -S loadgen -u 1001

USER loadgen

CMD ["/usr/local/bin/load-generator.sh"]