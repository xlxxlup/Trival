from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uvicorn
import os
import logging

from api.trival import trival_route
from logging_config import setup_logging
from utils.mcp_manager import initialize_mcp_manager

# 初始化日志系统
setup_logging()

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    应用生命周期管理器
    """
    # 启动时执行
    logger.info("=" * 80)
    logger.info("【应用启动】开始初始化...")
    logger.info("=" * 80)

    # 初始化MCP管理器（连接MCP服务器并创建子Agent）
    logger.info("正在初始化MCP工具和子Agent...")
    success = await initialize_mcp_manager(timeout=30)

    if success:
        logger.info("✅ MCP初始化成功")
    else:
        logger.warning("⚠️ MCP初始化失败，系统将在无MCP工具的情况下运行")

    logger.info("=" * 80)
    logger.info("【应用启动】初始化完成，服务已就绪")
    logger.info("=" * 80)

    yield  # 应用运行期间

    # 关闭时执行（如果需要清理资源）
    logger.info("应用关闭中...")

app = FastAPI(title="旅游助手", lifespan=lifespan)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有域名请求，生产环境建议指定域名，例如 ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有请求方法，如 GET、POST、PUT、DELETE
    allow_headers=["*"],  # 允许所有请求头
)

# 注册API路由
app.include_router(trival_route)

@app.get("/api")
def read_root():
    return {"message": "旅游助手 API 正常运行中"}

# 检查是否有构建好的前端文件
frontend_dist = os.path.join(os.path.dirname(__file__), "../fronted/dist")
if os.path.exists(frontend_dist):
    # 如果前端已构建，服务静态文件
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/")
    async def serve_frontend():
        """服务前端index.html"""
        index_path = os.path.join(frontend_dist, "index.html")
        return FileResponse(index_path)

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA路由，所有未匹配的路径返回index.html"""
        # 如果是API请求，跳过
        if full_path.startswith("api/") or full_path.startswith("travel") or full_path.startswith("resume"):
            return {"error": "Not found"}

        # 检查是否是静态文件
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # 否则返回index.html（SPA路由）
        index_path = os.path.join(frontend_dist, "index.html")
        return FileResponse(index_path)
else:
    @app.get("/")
    def read_root_dev():
        return {
            "message": "旅游助手 API 正常运行中",
            "note": "请在开发环境下单独启动前端: cd fronted && npm run dev",
            "frontend_url": "http://localhost:5173"
        }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
