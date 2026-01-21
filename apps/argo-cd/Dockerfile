FROM alpine:3.18
RUN apk add --no-cache curl bash jq
# Install kubectl (pinned version to avoid dynamic URL issues)
RUN curl -LO "https://dl.k8s.io/release/v1.29.0/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/

COPY simulate.sh /app/simulate.sh
RUN chmod +x /app/simulate.sh
WORKDIR /app
CMD ["/app/simulate.sh"]
