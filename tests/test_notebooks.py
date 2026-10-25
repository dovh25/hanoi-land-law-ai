import ast
from pathlib import Path
import nbformat

ROOT = Path(__file__).resolve().parents[1]


def test_notebook_format_syntax_and_cleared_outputs():
    notebook = nbformat.read(ROOT / "notebooks/embedding_batch.ipynb", as_version=4)
    nbformat.validate(notebook)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            ast.parse(cell.source)
            assert not cell.outputs
            assert cell.execution_count is None
            assert "load_dotenv" not in cell.source
            assert "GEMINI_API_KEY" not in cell.source


def test_notebook_synthetic_cell_executes_on_cpu_without_models(tmp_path):
    notebook = nbformat.read(ROOT / "notebooks/embedding_batch.ipynb", as_version=4)
    scope = {"SMOKE_ONLY": True, "WORK": tmp_path}
    for cell in notebook.cells:
        if "synthetic-smoke" in cell.metadata.get("tags", []):
            exec(compile(cell.source, "embedding_batch.ipynb", "exec"), scope)
    assert scope["result"].processed_records == 5


def test_notebook_defaults_require_explicit_gpu_and_install_consent(tmp_path):
    notebook = nbformat.read(ROOT / "notebooks/embedding_batch.ipynb", as_version=4)
    parameters = next(cell for cell in notebook.cells if "parameters" in cell.metadata.get("tags", []))
    # Parse defaults without executing a remote-runtime path creation.
    assignments = {node.targets[0].id: ast.literal_eval(node.value) for node in ast.parse(parameters.source).body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Constant)}
    assert assignments["SMOKE_ONLY"] is True
    assert assignments["ALLOW_PACKAGE_INSTALL"] is False
    assert assignments["ALLOW_MODEL_DOWNLOADS"] is False
    assert assignments["ALLOW_CPU_FALLBACK"] is False
