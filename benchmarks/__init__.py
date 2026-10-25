"""Optional benchmark tools; imports never initialize models or live judges."""
from importlib import import_module

_EXPORTS = {
    "dataset": ["EvalDataset"],
    "evaluator": ["PipelineEvaluator", "RetrievalEvaluator"],
    "metrics": ["compute_metrics"],
    "pipeline_adapter": ["BaseRetrieverAdapter", "RAGPipelineAdapter", "QdrantDirectAdapter", "get_retriever_adapter", "list_available_adapters"],
    "results": ["EvalResult", "load_results", "save_results"],
    "deepeval_config": ["deepeval_config", "setup_gemini_for_deepeval"],
    "deepeval_dataset": ["QnADataset", "load_and_generate"],
    "deepeval_evaluator": ["DeepEvalEvaluator", "DeepEvalResult", "get_available_metrics"],
}
__all__ = [name for names in _EXPORTS.values() for name in names]
__all__ += ["run_deepeval_evaluation", "print_deepeval_summary"]


def __getattr__(name):
    if name in {"run_deepeval_evaluation", "print_deepeval_summary"}:
        module = import_module(f"{__name__}.deepeval_evaluator")
        return getattr(module, "run_evaluation" if name == "run_deepeval_evaluation" else "print_summary")
    for module, names in _EXPORTS.items():
        if name in names:
            return getattr(import_module(f"{__name__}.{module}"), name)
    raise AttributeError(name)
