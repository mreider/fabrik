# Multi-stage build for NGINX with OpenTelemetry
FROM nginx:1.25-alpine AS base

# Install build dependencies
FROM base AS builder
RUN apk add --no-cache \
    git \
    cmake \
    make \
    g++ \
    pcre2-dev \
    zlib-dev \
    openssl-dev \
    curl-dev \
    protobuf-dev \
    c-ares-dev \
    re2-dev \
    yaml-cpp-dev

# Install gRPC
WORKDIR /tmp
RUN git clone --recurse-submodules -b v1.60.0 --depth 1 --shallow-submodules https://github.com/grpc/grpc /tmp/grpc
WORKDIR /tmp/grpc
RUN mkdir -p cmake/build && cd cmake/build && \
    cmake -DgRPC_INSTALL=ON -DgRPC_BUILD_TESTS=OFF -DCMAKE_INSTALL_PREFIX=/usr/local ../.. && \
    make -j$(nproc) && make install

# Install OpenTelemetry C++
WORKDIR /tmp
RUN git clone --recurse-submodules -b v1.14.2 --depth 1 --shallow-submodules https://github.com/open-telemetry/opentelemetry-cpp.git
WORKDIR /tmp/opentelemetry-cpp
RUN mkdir -p build && cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release \
          -DWITH_OTLP_GRPC=ON \
          -DWITH_OTLP_HTTP=ON \
          -DCMAKE_INSTALL_PREFIX=/usr/local \
          -DCMAKE_POSITION_INDEPENDENT_CODE=ON .. && \
    make -j$(nproc) && make install

# Build NGINX OpenTelemetry module
WORKDIR /tmp
RUN git clone https://github.com/open-telemetry/opentelemetry-cpp-contrib.git
WORKDIR /tmp/opentelemetry-cpp-contrib/instrumentation/nginx

# Get NGINX source for module compilation
RUN NGINX_VERSION=$(nginx -v 2>&1 | grep -oP 'nginx/\K[0-9.]+') && \
    wget http://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz && \
    tar zxf nginx-${NGINX_VERSION}.tar.gz

# Configure and build the module
RUN cd nginx-* && \
    ./configure --with-compat --add-dynamic-module=/tmp/opentelemetry-cpp-contrib/instrumentation/nginx && \
    make modules

# Production stage
FROM nginx:1.25-alpine

# Install runtime dependencies
RUN apk add --no-cache \
    protobuf \
    c-ares \
    re2 \
    yaml-cpp

# Copy gRPC libraries
COPY --from=builder /usr/local/lib/libgrpc* /usr/local/lib/
COPY --from=builder /usr/local/lib/libupb* /usr/local/lib/
COPY --from=builder /usr/local/lib/libaddress_sorting* /usr/local/lib/
COPY --from=builder /usr/local/lib/libgpr* /usr/local/lib/
COPY --from=builder /usr/local/lib/libabsl* /usr/local/lib/

# Copy OpenTelemetry libraries
COPY --from=builder /usr/local/lib/libopentelemetry* /usr/local/lib/

# Copy the compiled module
COPY --from=builder /tmp/opentelemetry-cpp-contrib/instrumentation/nginx/nginx-*/objs/ngx_http_opentelemetry_module.so /etc/nginx/modules/

# Update library cache
RUN ldconfig /usr/local/lib

# Copy configuration files
COPY nginx.conf /etc/nginx/nginx.conf
COPY opentelemetry.toml /etc/nginx/opentelemetry.toml

# Create log directory
RUN mkdir -p /var/log/nginx

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]