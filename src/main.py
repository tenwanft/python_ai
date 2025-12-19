from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from src.api.v1.router import api_router
from src.db import init_db

# 统一成功响应封装：将所有 JSON 响应包裹为 {data, msgCode, msg}
class UnifiedJSONResponse(JSONResponse):
    def render(self, content):
        # 已经是统一结构则直接返回
        if isinstance(content, dict) and "data" in content and "msgCode" in content and "msg" in content:
            return super().render(content)
        # 对于 /docs 和 /openapi.json 等非业务接口，避免影响其格式
        # 注意：这些接口通常不会使用默认响应类，这里作为兜底逻辑保留。
        return super().render({"data": content, "msgCode": 0, "msg": ""})

# 初始化数据库
before_startup = []


def setup_app():
    # 创建应用实例（设置统一响应类）
    app = FastAPI(title="Demo API", version="1.0", default_response_class=UnifiedJSONResponse)

    # 允许跨域（前端联调必须）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 如需更严格可改为具体域名，例如 ["http://localhost:3000"]
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 添加启动事件处理器
    @app.on_event("startup")
    def on_startup():
        # 初始化数据库
        init_db()
        # 执行所有在启动前注册的回调
        for callback in before_startup:
            callback()

    # 包含API路由
    app.include_router(api_router, prefix="/api/v1")

    # 统一异常响应格式
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={
            "data": None,
            "msgCode": exc.status_code,
            "msg": detail,
        })

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={
            "data": None,
            "msgCode": 500,
            "msg": "Internal Server Error",
        })

    return app


app = setup_app()


@app.get("/")
def root():
    return {"message": "Welcome to Demo API. Visit /docs for documentation."}