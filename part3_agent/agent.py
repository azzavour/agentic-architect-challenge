import re
from pathlib import Path
from google import genai
from google.genai import types

client = genai.Client()
MODEL = "gemini-3-flash-preview"

DOC_PATH = Path(__file__).parent / "sample_document.txt"
DOCUMENT_TEXT = DOC_PATH.read_text()

SYSTEM_PROMPT = f"""You are a support assistant. Answer questions ONLY using
the reference document below. If the answer is not in the document, say you
don't have that information -- do not guess or invent facts.

You also have access to a `calculator` tool. Only call it when the user's
question actually requires arithmetic. Do not call it for questions that
don't need math.

Remember details the user tells you about themselves and use them naturally
in later replies.

REFERENCE DOCUMENT:
---
{DOCUMENT_TEXT}
---
"""


def run_calculator(expression: str) -> str:
    if not re.fullmatch(r"[0-9+\-*/(). ]+", expression):
        return "Error: expression contains disallowed characters."
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error evaluating expression: {e}"


calculator_tool = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="calculator",
        description="Evaluate a basic arithmetic expression, e.g. '12 * 3 + 5'.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "expression": types.Schema(
                    type="STRING",
                    description="A math expression using +, -, *, /, and parentheses only.",
                )
            },
            required=["expression"],
        ),
    )
])


class Agent:
    def __init__(self):
        self.history: list[types.Content] = []

    def ask(self, user_message: str) -> str:
        self.history.append(
            types.Content(role="user", parts=[types.Part(text=user_message)])
        )

        response = client.models.generate_content(
            model=MODEL,
            contents=self.history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[calculator_tool],
            ),
        )

        candidate_parts = response.candidates[0].content.parts

        while any(part.function_call for part in candidate_parts):
            self.history.append(response.candidates[0].content)

            function_response_parts = []
            for part in candidate_parts:
                if part.function_call and part.function_call.name == "calculator":
                    expression = part.function_call.args["expression"]
                    result = run_calculator(expression)
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name="calculator",
                            response={"result": result},
                        )
                    )

            self.history.append(
                types.Content(role="user", parts=function_response_parts)
            )

            response = client.models.generate_content(
                model=MODEL,
                contents=self.history,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=[calculator_tool],
                ),
            )
            candidate_parts = response.candidates[0].content.parts

        self.history.append(response.candidates[0].content)
        return response.text


if __name__ == "__main__":
    agent = Agent()
    print("Agent ready. Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ("quit", "exit"):
            break
        print("Agent:", agent.ask(user_input), "\n")