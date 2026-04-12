# sindris Docker 部署配置
# ============================================================
# 基础镜像: python:3.11-slim
# 构建方式（从 workspace 根目录执行）:
#   docker build -f skills/sindris/Dockerfile -t sindris:latest .
#
# 或从任意位置指定 build context:
#   docker build -f ~/.openclaw/skills/sindris/Dockerfile \
#     --build-arg SINDIS_PATH=$HOME/.openclaw/skills/sindris \
#     --build-arg ZHONG_SHU_PATH=$HOME/.openclaw/skills/织界中枢 \
#     -t sindris:latest \
#     $HOME/.openclaw
# ============================================================

FROM python:3.11-slim

# ============================================================
# 元数据
# ============================================================
LABEL maintainer="sindris"
LABEL description="织界统一协调系统 (Sindri's) - 多Agent协作执行引擎"
LABEL version="1.0"

# ============================================================
# 构建参数（支持从外部传入）
# ============================================================
ARG SINDIS_HOST_PATH=/home/rayliu/.openclaw/skills/sindris
ARG ZHONG_SHU_HOST_PATH=/home/rayliu/.openclaw/skills/织界中枢

# ============================================================
# 环境变量
# ============================================================
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # PYTHONPATH 包含 sindris 和织界中枢，使模块可相互导入
    PYTHONPATH=/app/sindris/scripts:/app/织界中枢/scripts

# ============================================================
# 系统依赖
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # tmux - sindris_tmux_manager 依赖
    tmux \
    # git - 源码管理
    git \
    # openssh-client - SSH 操作
    openssh-client \
    # curl - 健康检查
    curl \
    # procps - 进程查看工具（ps, pgrep 等）
    procps \
    # vim - 调试编辑
    vim-tiny \
    # 清理 apt 缓存
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# 工作目录
# ============================================================
WORKDIR /app

# ============================================================
# 复制 sindris 代码
# ============================================================
# 构建时从 Host 复制（通过 build context）
COPY ${SINDIS_HOST_PATH}/sindris_executor.py /app/sindris/
COPY ${SINDIS_HOST_PATH}/scripts/               /app/sindris/scripts/
COPY ${SINDIS_HOST_PATH}/SKILL.md              /app/sindris/
COPY ${SINDIS_HOST_PATH}/tests/                /app/sindris/tests/

# ============================================================
# 复制织界中枢模块（sindris 依赖 consensus_officer, worktree_officer, monitor 等）
# ============================================================
COPY ${ZHONG_SHU_HOST_PATH}/scripts/ /app/织界中枢/scripts/

# ============================================================
# 验证关键文件存在
# ============================================================
RUN echo "=== 验证 sindris 文件 ===" && \
    ls /app/sindris/sindris_executor.py && \
    ls /app/sindris/scripts/*.py | wc -l && \
    echo "=== 验证织界中枢文件 ===" && \
    ls /app/织界中枢/scripts/consensus_officer.py && \
    ls /app/织界中枢/scripts/worktree_officer.py && \
    ls /app/织界中枢/scripts/monitor.py && \
    echo "=== 验证 Python 模块导入 ===" && \
    python -c "import sys; sys.path.insert(0, '/app/sindris/scripts'); sys.path.insert(0, '/app/织界中枢/scripts'); print('PYTHONPATH OK')"

# ============================================================
# 入口点
# ============================================================
# 默认入口：直接运行 sindris_executor.py（交互模式）
ENTRYPOINT ["python", "/app/sindris/sindris_executor.py"]

# 默认参数（可覆盖，--help 查看可用选项）
CMD ["--help"]
