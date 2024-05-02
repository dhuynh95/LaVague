from llama_index.core.base.llms.base import BaseLLM
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core import PromptTemplate
from .extractors import BaseExtractor
from .retrievers import BaseHtmlRetriever

class ActionContext:
    """Set the context which will be used thourough the action generation pipeline."""

    def __init__(
        self,
        llm: BaseLLM,
        embedding: BaseEmbedding,
        retriever: BaseHtmlRetriever,
        prompt_template: PromptTemplate,
        extractor: BaseExtractor,
    ):
        self.llm = llm
        self.embedding = embedding
        self.retriever = retriever
        self.prompt_template = prompt_template
        self.extractor = extractor
