
FROM python:3.13-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    opencl-headers \
    ocl-icd-opencl-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
RUN pip install numpy pyopencl

# 设置工作目录
WORKDIR /app

# 复制jiami项目
COPY . .

# 安装jiami依赖
RUN pip install -r requirements.txt

CMD ["python", "main.py"]
