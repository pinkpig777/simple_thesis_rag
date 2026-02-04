from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import OpenAI


class OpenAIEmbedder:
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        client: "OpenAI | None" = None,
    ) -> None:
        self.model = model
        self._client: Any = client

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI()
        return self._client

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model, input=text)
        return response.data[0].embedding
