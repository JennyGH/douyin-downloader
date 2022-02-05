### 以 python 来作为基础镜像
FROM python:latest
### 创建工作目录
### 将 python 项目复制到工作目录下
COPY . /
### 设置工作目录
WORKDIR /
### 下载 python 项目的依赖库
# RUN python -m pip install --upgrade pip
RUN pip3 install -r requirements.txt
EXPOSE 8080
### 在创建个爬取的数据存放的目录，这个需要根据自己代码里面设置的目录来创建，例如：
### VOLUME /data
### 最后一步，运行docker镜像时运行自己的python项目
### 可以多个参数： CMD ["python3","a","main.py"]
ENTRYPOINT ["python3"]
CMD ["src/main.py"]