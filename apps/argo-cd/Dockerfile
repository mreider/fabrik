FROM alpine:3.18
RUN apk add --no-cache curl bash jq
# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/

COPY simulate.sh /app/simulate.sh
RUN chmod +x /app/simulate.sh
WORKDIR /app
CMD ["/app/simulate.sh"]
