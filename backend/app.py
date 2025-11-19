from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os

from api.trival import trival_route

app = FastAPI(title="旅游助手")

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
