# Python Development Notes

## Virtual Environments

Using `uv` for fast dependency management. It's significantly faster than pip and provides better reproducibility.

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Code Quality Tools

- **Black**: Code formatting
- **Ruff**: Fast linting
- **MyPy**: Type checking

## Testing

Using pytest for testing. Write tests for core logic like chunking and retrieval.

```python
def test_chunking():
    chunker = DocumentChunker()
    doc = Document(content="test", metadata=...)
    chunks = chunker.chunk_document(doc)
    assert len(chunks) > 0
```
