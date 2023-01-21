#!/bin/bash
docker run --restart unless-stopped --name=douyin-downloader -v /var/services/homes/dbj/docker/douyin-downloader:/ --dns 202.96.128.86 -p 8081:8080 -d douyin-downloader