from typing import Dict, Any


def read_resume_content(resume_content: Dict[str, Any]) -> Dict[str, Any]:
    """
    读取简历完整内容

    Args:
        resume_content: 简历内容字典

    Returns:
        Dict[str, Any]: 简历完整内容
    """
    return {"content": resume_content, "message": "已成功读取简历内容"}
