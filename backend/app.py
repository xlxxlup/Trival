from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="旅游助手")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有域名请求，生产环境建议指定域名，例如 ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有请求方法，如 GET、POST、PUT、DELETE
    allow_headers=["*"],  # 允许所有请求头
)

@app.get("/")
def read_root():
    return {"message": "旅游助手 API 正常运行中"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
