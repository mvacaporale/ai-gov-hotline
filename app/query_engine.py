# Standard library imports
import os
import logging
from pathlib import Path

# Third party imports
import yaml
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.core import VectorStoreIndex
from llama_index.core import SimpleDirectoryReader
from llama_index.llms.openai import OpenAI
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding


load_dotenv(dotenv_path=".env.local")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_prompts_config():
    """
    This will load the yaml config of the initial prompts passed to the LLM.
    """

    # Get the directory containing the current file
    current_dir = Path(__file__).parent

    # Define yaml file path relative to current file
    yaml_path = current_dir / "prompts.yaml"
    logger.info("loading yaml: " + str(yaml_path))

    with open(yaml_path, "r") as file:
        config = yaml.safe_load(file)
        return config


def setup_qa_index(data_dir: str):
    """
    Create a vector store index from documents in the specified directory.

    Args:
        data_dir (str): Path to directory containing Q&A documents

    Returns:
        VectorStoreIndex: Initialized index ready for querying
    """
    # Load documents
    documents = SimpleDirectoryReader(data_dir).load_data()

    # Initialize LLM and embedding model
    llm = OpenAI(model="gpt-4o", temperature=0.1)
    embed_model = OpenAIEmbedding()

    Settings.llm = llm
    Settings.embed_model = embed_model
    Settings.node_parser = SimpleNodeParser()

    # Create and return index
    index = VectorStoreIndex.from_documents(
        documents,
    )

    return index


def setup_query_engine(index):
    """
    Set up a query engine with specific parameters for Q&A.

    Args:
        index (VectorStoreIndex): The vector store index

    Returns:
        QueryEngine: Configured query engine
    """

    # Load config with the chatbot initial prompts.
    config = load_prompts_config()

    query_engine = index.as_query_engine(
        similarity_top_k=3,  # Number of relevant chunks to retrieve
        streaming=True,
        response_mode="compact",  # For concise responses,
        # text_qa_template=text_qa_template,
        chat_history=[
            {"role": "system", "content": config["QA_SYSTEM_PROMPT"]},
            {"role": "assistant", "content": config["QA_ASSISTANT_GREETING"]},
        ],
    )

    return query_engine


def get_query_engine(data_dir="data"):

    logger.info("Setting up the vector store index.")
    index = setup_qa_index(data_dir)

    logger.info("Setting up the query engine.")
    query_engine = setup_query_engine(index)

    # This query warms us the system so the bot doesn't stall on the first question.
    query_engine.query("Thanks for offering, I could use help with some questions.")

    logger.info("Done setting the query engine.")
    return query_engine


def main():

    # Set up query engine
    query_engine = get_query_engine(data_dir="data")

    # Interactive Q&A loop
    print("\nQ&A Bot ready! Type 'quit' to exit.")

    while True:
        question = input("\nEnter your question: ")
        if question.lower() == "quit":
            break

        try:
            response_gen = query_engine.query(question).response_gen
            response = "".join(response_gen)
            print("\nAnswer:", response)
        except Exception as e:
            print(f"Error processing question: {e}")


if __name__ == "__main__":
    main()
