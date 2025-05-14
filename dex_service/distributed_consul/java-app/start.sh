#!/bin/bash

# пример подключения к consul кластеру при помощи локально запущенного агента для java приложения
# Запускаем Consul agent в фоне
consul agent \
  -data-dir=/consul/data \
  -node=$(hostname) \
  -retry-join=consul1 \
  -retry-join=consul2 \
  -retry-join=consul3 \
  -client=0.0.0.0 &

# Ждём немного, чтобы Consul стартовал
sleep 5


exec java -jar /app/app.jar