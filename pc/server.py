"""电脑端服务入口：python server.py（在 pc/ 目录下运行）。

环境变量：
- ABM_HOST 默认 0.0.0.0
- ABM_PORT 默认 8600
- ABM_DB   默认 pc/data/abm.db
"""

import os

import uvicorn

from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("ABM_HOST", "0.0.0.0"),
        port=int(os.environ.get("ABM_PORT", "8600")),
    )
