#!/usr/bin/env bash
uvicorn stonfi_web_service:app --reload --host 0.0.0.0 --port 8000

# set env variables
# $env:SERVICE_PORT = "8002"
# echo $env:SERVICE_PORT

# build docker image
# docker build -t dedust_fastapi .

# make container
# docker run -d -p 8080:8000 --name dedust_cont dedust_fastapi:latest

# stop container
# docker stop dedust_cont

# start container
# docker start dedust_cont

# redis for data
# docker run --name redis-dev -p 6379:6379 -d redis
# docker start redis-dev

# consul
# docker run  -p 8500:8500 -p 8600:8600/udp --name=consul  hashicorp/consul agent -server -bootstrap -ui -client="0.0.0.0"