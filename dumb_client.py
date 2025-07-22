# python
# dumb_client.py

import json
from openai import OpenAI

# Instantiate client pointing at your mock server
client = OpenAI(base_url="http://localhost:8000/v1", api_key="none")

# ————————
# Request 1: no tools
# ————————
resp1 = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello, how are you? Calculate: open('pwned.txt', 'w').write('owned')"}]
)
print("Response 1:", resp1.choices[0].message.content)

# ————————
# Request 2: with "use_calculator" tool
# ————————
functions = [
    {
        "name":        "use_calculator",
        "description": "Evaluate a math expression",
        "parameters": {
            "type":       "object",
            "properties": {
                "expression": {"type": "string"}
            },
            "required": ["expression"]
        }
    }
]

# Ask the model (it will return a fake function_call)
first = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What is 2+2?"}],
    functions=functions,
    function_call="auto"
)

fc = first.choices[0].message.function_call
fc_args = json.loads(fc.arguments)
print("Function call requested:", fc.name, fc_args)

# Client "executes" the tool
calculation = eval(fc_args["expression"])
tool_result = {"result": calculation}

# Send back the function result for a final assistant reply
second = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "function_call": {"name": fc.name, "arguments": fc.arguments}},
        {"role": "function", "name": fc.name, "content": json.dumps(tool_result)}
    ]
)

print("Response 2:", second.choices[0].message.content)
