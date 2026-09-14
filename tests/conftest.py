class _FakeStructuredLLM:
    def __init__(self, results):
        self._results = list(results)

    def invoke(self, prompt):
        if len(self._results) > 1:
            return self._results.pop(0)
        return self._results[0]


class FakeLLM:
    """Stand-in for langchain_google_genai.ChatGoogleGenerativeAI's `.with_structured_output(...).invoke(...)` interface.

    `results` is either:
      - a single pydantic model or list of models (returned regardless of
        requested schema) - for tests exercising one node in isolation, or
      - a dict of {schema: model_or_list} - for graph-level tests where
        generate_queries and score share the same `state["llm"]` and each
        node requests a different output schema.

    A list is consumed one-per-call, so tests can simulate different
    responses across the refine loop's repeated node calls.
    """

    def __init__(self, results):
        self._by_schema = results if isinstance(results, dict) else None
        self._flat = None if self._by_schema else (results if isinstance(results, list) else [results])

    def with_structured_output(self, schema):
        if self._by_schema is not None:
            result = self._by_schema[schema]
            return _FakeStructuredLLM(result if isinstance(result, list) else [result])
        return _FakeStructuredLLM(self._flat)
