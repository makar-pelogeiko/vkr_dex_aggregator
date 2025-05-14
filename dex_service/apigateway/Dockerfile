FROM gradle:8.13-jdk17 AS build

WORKDIR /app

COPY . .
RUN gradle bootJar --no-daemon

FROM openjdk:17-jdk-slim

WORKDIR /app

COPY --from=build /app/build/libs/*.jar apigateway.jar

ENTRYPOINT ["java", "-jar", "apigateway.jar"]