# пример подключения к consul кластеру при помощи локально запущенного агента для java приложения

FROM gradle:8.13-jdk17 AS build

WORKDIR /app

COPY .. .
RUN gradle bootJar --no-daemon

FROM openjdk:17-jdk-slim

# Установим curl и unzip для загрузки consul
RUN apt-get update && \
    apt-get install -y curl unzip && \
    curl -fsSL https://releases.hashicorp.com/consul/1.16.2/consul_1.16.2_linux_amd64.zip -o consul.zip && \
    unzip consul.zip && \
    mv consul /usr/local/bin/ && \
    rm -rf consul.zip && \
    apt-get remove -y curl unzip && \
    apt-get autoremove -y && \
    apt-get clean

# Создаем директории
WORKDIR /app
RUN mkdir -p /consul/data


COPY --from=build /app/build/libs/*.jar app.jar

# Конфигурация запуска
COPY start.sh /start.sh
RUN chmod +x /start.sh

ENTRYPOINT ["/start.sh"]