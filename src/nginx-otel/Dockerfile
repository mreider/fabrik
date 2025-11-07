# Simplified NGINX with OpenTelemetry - for now use standard nginx
# TODO: Build custom image with OpenTelemetry module when CI resources allow
FROM nginx:1.25-alpine

# Copy configuration files (OpenTelemetry directives will be ignored without module)
COPY nginx.conf /etc/nginx/nginx.conf
COPY opentelemetry.toml /etc/nginx/opentelemetry.toml

# Create log directory
RUN mkdir -p /var/log/nginx

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]