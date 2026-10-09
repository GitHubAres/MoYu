# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""Mock OpenAI 兼容接口：返回固定的 chat/completions 响应，用于验证 audit 解析。"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

ISSUES = (
    '[{"type":"矛盾","severity":"high","entity":"青玉佩",'
    '"issue":"第一章顾风随身携带的是青玉佩，第二章却变成赤玉佩，与设定库「青玉佩」不符。",'
    '"quote":"腰间挂着一枚赤玉佩","chapter_title":"第二章 古剑"},'
    '{"type":"时间线","severity":"medium","entity":"",'
    '"issue":"第一章顾风十六岁下山，十年后应为二十六岁，第二章却写十八岁。",'
    '"quote":"他今年不过十八岁","chapter_title":"第二章 古剑"}]'
)


@app.post("/v1/chat/completions")
async def chat():
    return JSONResponse({
        "id": "mock-1",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": ISSUES},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168},
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8398)
