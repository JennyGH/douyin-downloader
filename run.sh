#!/bin/bash
docker stop douyin-downloader
docker rm douyin-downloader
docker run \
--restart unless-stopped \
--name=douyin-downloader \
--dns 202.96.128.86 \
--memory 2G \
-e TZ=Asia/Shanghai \
-v /var/services/homes/dbj/docker/douyin-downloader/cache:/cache \
-p 8081:8080 \
-d douyin-downloader