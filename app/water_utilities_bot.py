# Standard library imports
import logging

# Third party imports
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI

# Local imports
from app.pdf_utils import compose_and_send_form
from app.query_engine import get_query_engine
from app.query_engine import load_prompts_config
from app.utility_forms import UtilityAssistanceApplication


load_dotenv(dotenv_path=".env.local")

info_gathering_llm = ChatOpenAI(temperature=0, model="gpt-4-turbo", streaming=True)
form_extractor_llm = ChatOpenAI(temperature=0, model="gpt-4-turbo")

# Standard library imports
from enum import Enum
from typing import Dict
from typing import List

# Third party imports
from pydantic import Field
from pydantic import BaseModel
from langchain.chains import LLMChain
from langchain.chains import create_tagging_chain_pydantic
from langchain.prompts import ChatPromptTemplate


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = load_prompts_config()
first_prompt = ChatPromptTemplate.from_template(config["INFO_GATHERING_PROMPT"])


def compose_stream(dict_generator, first_message=None):
    """
    Compose a generator object with an initial message if given. This will also
    extract the `text` field from the input generator values.
    """
    if first_message is not None:
        yield first_message
    for item in dict_generator:
        yield item["text"]


class ChatState(Enum):
    GENERAL = "general"
    FORM_FILLING = "form_filling"


class WaterUtilitiesBot:

    def __init__(self):
        self.query_engine = get_query_engine()
        self.state = ChatState.GENERAL
        self.current_form = None
        self.tagging_chain = create_tagging_chain_pydantic(
            UtilityAssistanceApplication, form_extractor_llm
        )
        self.info_gathering_chain = LLMChain(
            llm=info_gathering_llm, prompt=first_prompt
        )

        # Common form-filling indicators
        self.form_triggers = [
            "submit request",
            "file request",
            "new request",
            "service request",
            "fill out form",
            "need service",
            "request form",
            "start request",
        ]

    def is_form_request(self, user_input: str) -> bool:
        """Check if user input indicates they want to fill out a form"""
        return any(
            trigger.lower() in user_input.lower() for trigger in self.form_triggers
        )

    def check_what_is_empty(self, help_form) -> List[str]:
        """Returns list of empty fields that still need to be filled"""
        ask_for = []
        # Check if fields are empty
        for field, value in help_form.model_dump().items():
            if value in [
                None,
                "",
                0,
            ]:  # You can add other 'empty' conditions as per your requirements
                ask_for.append(f"{field}")
        return ask_for

    def extract_field_info(self, user_input: str, assistant_input: str) -> Dict:
        """Extract relevant field information from user input"""
        try:
            result = self.tagging_chain.run(
                [
                    {
                        "role": "user",
                        "content": user_input,
                    },
                    {
                        "role": "assistant",
                        "content": assistant_input,
                    },
                ]
            )
            return result.model_dump(exclude_unset=True)

        except ValueError as e:
            logger.info(f"Incorrect format passed from the LLM into the form.")
            return {}


    def update_form(self, field_info: Dict):
        """Update the current form with new field information"""

        logger.debug(f"Updating w/ field info: {field_info}")
        if self.current_form is not None:
            try:
                self.current_form.update(**field_info)
                return True

            except ValueError as e:
                logger.info(f"Incorrect format given for fields: {field_info} (Error: {str(e)})")
                return False

    def send_completed_form(self, completed_form: Dict):
        try:
            compose_and_send_form(completed_form)
        except Exception as e:
            logger.info(f"Unable to send completed form. Error ({e})")

    def process_message(self, user_input: str, last_message: str = ""):
        """Process user message and return appropriate response"""
        if self.state == ChatState.GENERAL:
            if self.is_form_request(user_input):

                self.state = ChatState.FORM_FILLING
                self.current_form = UtilityAssistanceApplication()

                empty_field = self.check_what_is_empty(self.current_form)[0]
                description = self.current_form.model_fields[empty_field].description
                return compose_stream(
                    self.info_gathering_chain.stream(
                        {
                            "ask_for": empty_field,
                            "info_given": {},
                            "last_message": last_message,
                            "description": description,
                        }
                    ),
                    "I'll help you submit a service request. Let's fill out the form together.\n",
                )

            # Default to answering the users questions; returned as stream.
            return self.query_engine.query(user_input).response_gen

        elif self.state == ChatState.FORM_FILLING:

            # Extract any field information from the user's input
            field_info = self.extract_field_info(user_input, last_message)
            logger.debug(f"Received field info: {field_info}")
            valid_update = self.update_form(field_info)

            # Check what fields are still empty
            empty_fields = self.check_what_is_empty(self.current_form)
            logger.debug(f"Remaining needed field info: {empty_fields}")

            if not empty_fields:
                # Form is complete
                self.state = ChatState.GENERAL
                completed_form = self.current_form
                self.send_completed_form(completed_form)
                self.current_form = None

                # Format output as a message stream.
                return (
                    message
                    for message in [
                        "Thank you! Your service request has been submitted. We'll process it and get back to you soon. Can I help with anything else?"
                    ]
                )

            # Compose info given to help with next prompt
            info_given = str(field_info)
            if len(field_info) == 0:
                info_given += "\nNote: We weren't able to extract any information from the user."
            if not valid_update:
                info_given += "\nNote: Some of the info given was not in the correct format."

            # Form still has empty fields
            empty_field = empty_fields[0]
            description = self.current_form.model_fields[empty_field].description
            return compose_stream(
                self.info_gathering_chain.stream(
                    {
                        "ask_for": empty_field,
                        "info_given": info_given,
                        "last_message": last_message,
                        "description": description,
                    }
                )
            )


def main():

    # Set up query engine
    water_bot = WaterUtilitiesBot()

    # Interactive Q&A loop
    print("\nQ&A Bot ready! Type 'quit' to exit.")

    while True:
        user_input = input("\nEnter your user_input: ")
        if user_input.lower() == "quit":
            break

        try:
            response_gen = water_bot.process_message(user_input)
            response = "".join(response_gen)
            print("\nAnswer:", response)

        except Exception as e:
            print(f"Error processing question: {e}")


if __name__ == "__main__":
    main()
