import json
state = {}
try:
    s = f"{json.dumps(state.get('resume_content', {{}}))}"
    print(s)
except Exception as e:
    print("Error:", e)
