# Standard library imports
import json
import time
import logging
import unittest

# Local imports
from run import app  # This import will work thanks to conftest.py


class TestChatCompletions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Configure logging to show all levels
        logging.basicConfig(
            level=logging.DEBUG,  # Set to DEBUG to see all messages
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

        # Create a logger for this test class
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def test_chat_completion_non_streaming(self):
        # Test payload
        payload = {
            "messages": [{"content": "I need help paying my water bill."}],
            "stream": False,
        }

        # Make request
        self.logger.info("Sending chat completions with `stream=False`")
        response = self.client.post(
            "/chat/completions", json=payload, content_type="application/json"
        )

        # Assert response status and content type
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")

        # Parse response
        data = json.loads(response.data)

        # Assert response structure
        self.assertIn("created", data)
        self.assertIsInstance(data["created"], int)
        self.assertLess(
            time.time() - data["created"], 60
        )  # Created timestamp should be recent

        self.assertIn("choices", data)
        self.assertEqual(len(data["choices"]), 1)
        self.assertIn("message", data["choices"][0])
        self.assertIn("role", data["choices"][0]["message"])
        self.assertIn("content", data["choices"][0]["message"])
        self.assertEqual(data["choices"][0]["message"]["role"], "assistant")
        self.assertIsInstance(data["choices"][0]["message"]["content"], str)
        self.assertGreater(len(data["choices"][0]["message"]["content"]), 0)

    def test_chat_completion_streaming(self):
        # Test payload
        payload = {
            "messages": [{"content": "I need help paying my water bill."}],
            "stream": True,
        }

        # Make request
        self.logger.info("Sending chat completions with `stream=True`")
        response = self.client.post(
            "/chat/completions", json=payload, content_type="application/json"
        )

        # Assert response status and content type
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "text/event-stream")

        # Process the streaming response
        chunks = []
        for chunk in response.response:  # Flask's response.response is the iterator
            if chunk:
                # Decode bytes to string and strip 'data: ' prefix if present
                chunk_str = chunk.decode("utf-8")
                if chunk_str.startswith("data: "):
                    chunk_str = chunk_str[6:]
                chunks.append(json.loads(chunk_str))

        # Assert each chunk structure
        for chunk in chunks:
            self.assertIn("created", chunk)
            self.assertIsInstance(chunk["created"], int)
            self.assertLess(time.time() - chunk["created"], 60)

            self.assertIn("choices", chunk)
            self.assertEqual(len(chunk["choices"]), 1)
            self.assertIn("delta", chunk["choices"][0])
            self.assertIn("content", chunk["choices"][0]["delta"])
            self.assertIsInstance(chunk["choices"][0]["delta"]["content"], str)

        # Assert we received at least one chunk
        self.assertGreater(len(chunks), 0)

        # Combine all chunks to verify complete response
        complete_response = "".join(
            chunk["choices"][0]["delta"]["content"] for chunk in chunks
        )
        self.assertGreater(len(complete_response), 0)


if __name__ == "__main__":
    unittest.main()
