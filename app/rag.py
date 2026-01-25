from typing import Dict, List, Tuple
import os
import requests
from typing import Dict, List, Tuple
import textwrap
from .index import Index


def call_deepseek_api(messages: List[Dict], api_key: str) -> str:
    url = "https://notebook-0gir99j66ed68064.api.tcloudbasegateway.com/v1/ai/deepseek/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "deepseek-v3.2",
        "messages": messages,
        "stream": False
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        # 注意：这里假设网关返回的格式与标准 OpenAI/DeepSeek 兼容
        # 如果网关返回格式不同，可能需要根据实际响应调整解析逻辑
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error calling DeepSeek API: {e}")
        # 尝试打印更详细的错误信息以便调试
        if 'response' in locals():
            try:
                print(f"API Response: {response.text}")
            except:
                pass
        return ""


def synthesize_answer(query: str, hits: List[Tuple[Dict, float]]) -> Dict:
    if not hits:
        return {
            "answer": "未检索到相关内容。请先摄取资料或调整问题。",
            "citations": [],
        }
    
    context_parts: List[str] = []
    citations: List[Dict] = []
    
    for rank, (chunk, score) in enumerate(hits, start=1):
        context_parts.append(f"[{rank}] {chunk['text']}")
        citations.append(
            {
                "rank": rank,
                "score": round(score, 4),
                "source_id": chunk.get("source_id"),
                "source_type": chunk.get("source_type"),
                "location": chunk.get("location"),
                "url": chunk.get("url"),
                "path": chunk.get("path"),
            }
        )
    
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if api_key:
        # 使用 LLM 生成
        system_prompt = "你是一个基于资料库的智能助手。请严格根据以下提供的【参考资料】回答用户问题。如果资料中没有答案，请直接说明。在回答中引用资料时，请使用 [x] 的形式标注来源。"
        user_prompt = f"参考资料：\n{''.join(context_parts)}\n\n用户问题：{query}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        llm_answer = call_deepseek_api(messages, api_key)
        if llm_answer:
            answer = llm_answer
        else:
            # 降级处理
            body_parts = [f"- {textwrap.shorten(c['text'], width=200, placeholder='…')}" for c, _ in hits]
            answer = "（LLM调用失败，降级为摘要）基于已摄取资料，检索到以下要点：\n" + "\n".join(body_parts)
    else:
        # 无 API Key，使用旧逻辑
        body_parts = [f"- {textwrap.shorten(c['text'], width=400, placeholder='…')}" for c, _ in hits]
        answer = "（未配置API Key，显示摘录）基于已摄取资料，检索到以下要点：\n" + "\n".join(body_parts)

    return {"answer": answer, "citations": citations}


def answer_query(query: str, index: Index, top_k: int = 6) -> Dict:
    hits = index.search(query, top_k=top_k)
    return synthesize_answer(query, hits)
