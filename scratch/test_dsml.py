import re
import json
import uuid

def parse_dsml_tool_calls(text: str) -> list[dict]:
    invoke_pattern = r'<｜｜DSML｜｜invoke name="([^"]+)">([\s\S]*?)</｜｜DSML｜｜invoke>'
    param_pattern = r'<｜｜DSML｜｜parameter name="([^"]+)"[^>]*>([\s\S]*?)</｜｜DSML｜｜parameter>'
    
    tool_calls = []
    
    for match in re.finditer(invoke_pattern, text):
        tool_name = match.group(1)
        params_str = match.group(2)
        
        args = {}
        for p_match in re.finditer(param_pattern, params_str):
            param_name = p_match.group(1)
            param_value = p_match.group(2)
            
            val_clean = param_value.strip()
            if val_clean.isdigit():
                args[param_name] = int(val_clean)
            elif val_clean.lower() in ["true", "false"]:
                args[param_name] = val_clean.lower() == "true"
            else:
                args[param_name] = val_clean
                
        tool_calls.append({
            "name": tool_name,
            "args": args,
            "id": f"call_{uuid.uuid4().hex[:8]}"
        })
        
    return tool_calls

text = """
<｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="update_basic_info"> <｜｜DSML｜｜parameter name="summary" string="true">资深 AI Agent 开发工程师，10 年系统架构经验...</｜｜DSML｜｜parameter> </｜｜DSML｜｜invoke> </｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="update_experience"> <｜｜DSML｜｜parameter name="index" string="false">0</｜｜DSML｜｜parameter> <｜｜DSML｜｜parameter name="field" string="true">description</｜｜DSML｜｜parameter> <｜｜DSML｜｜parameter name="value" string="true">负责腾讯 IEG 多智能体协作平台核心模块的架构...</｜｜DSML｜｜parameter> </｜｜DSML｜｜invoke> </｜｜DSML｜｜tool_calls>
"""

print(json.dumps(parse_dsml_tool_calls(text), indent=2, ensure_ascii=False))
