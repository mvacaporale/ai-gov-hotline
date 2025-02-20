# Standard library imports
import os
import json
import logging

# Third party imports
from flask import Flask
from flask import Response
from flask import Blueprint
from flask import request
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv(dotenv_path=".env.local")
# Standard library imports
import time

# Local imports
from app.water_utilities_bot import WaterUtilitiesBot


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# client = OpenAI(
#   # This is the default and can be omitted
#   api_key=os.environ.get("OPENAI_API_KEY"),
# )

assistance_bot = WaterUtilitiesBot()


def format_streaming_response(response_stream):
    """
    Format the response to match OpenAI's chat completion structure when
    streaming is on.
    """
    timestamp = int(time.time())
    for text in response_stream:
        json_data = json.dumps(
            {"created": timestamp, "choices": [{"delta": {"content": text}}]}
        )
        logger.debug(f"Returning streaming chunk: {json.dumps(json_data)}")
        yield f"data: {json_data}\n\n"


def format_nonstreaming_response(response_stream):
    """
    Format the response to match OpenAI's chat completion structure when
    streaming is off.
    """
    timestamp = int(time.time())

    # Merge the stream of content into one string
    composed_text = "".join(response_stream)

    return json.dumps(
        {
            "created": timestamp,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": composed_text,
                    },
                }
            ],
        }
    )


@app.route("/chat/completions", methods=["POST"])
def openai_advanced_custom_llm_route():
    request_data = request.get_json()

    streaming = request_data.get("stream", False)
    logger.info(
        f"Received incoming request with data (stream={streaming}): {json.dumps(request_data, indent=2)}"
    )

    last_message = request_data["messages"][-1]

    if streaming:
        # Simulate a non-streaming response
        chat_completion = assistance_bot.process_message(last_message["content"])
        return Response(
            format_streaming_response(chat_completion),
            content_type="text/event-stream",
        )

    else:
        # Simulate a non-streaming response nonstreaming
        chat_completion = assistance_bot.process_message(last_message["content"])
        return Response(
            format_nonstreaming_response(chat_completion),
            content_type="application/json",
        )


if __name__ == "__main__":
    app.run(debug=True, port=5000)  # You can adjust the port if needed
