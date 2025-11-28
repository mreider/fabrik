FROM maven:3.8.5-openjdk-17 AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn clean package -DskipTests

FROM openjdk:17-slim
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v1.32.1/opentelemetry-javaagent.jar /app/opentelemetry-javaagent.jar
ENTRYPOINT ["java", "-jar", "app.jar"]
