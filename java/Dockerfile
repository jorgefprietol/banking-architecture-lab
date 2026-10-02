FROM maven:3-eclipse-temurin-24 AS build
WORKDIR /src
COPY java/pom.xml .
COPY java/src/ src/
RUN --mount=type=cache,target=/root/.m2 mvn -B -ntp verify
RUN --mount=type=cache,target=/root/.m2 mvn -B -ntp dependency:copy -Dartifact=io.opentelemetry.javaagent:opentelemetry-javaagent:2.31.1 -DoutputDirectory=/agent

FROM eclipse-temurin:25-jre-alpine
WORKDIR /app
RUN addgroup -S banking && adduser -S banking -G banking
COPY --from=build /src/target/banking-lab-1.0.0.jar app.jar
COPY --from=build /agent/opentelemetry-javaagent-2.31.1.jar /app/otel-agent.jar
USER banking
EXPOSE 8080
ENTRYPOINT ["java", "-javaagent:/app/otel-agent.jar", "-XX:MaxRAMPercentage=70", "-jar", "/app/app.jar"]
