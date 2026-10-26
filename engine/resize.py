"""Public offline resize entry point; complete designs in, complete designs out."""
import warnings
from engine.analysis import analyze
from engine.layout import generate_candidates
from engine.quality import evaluate, repair
from engine.validation import validate_source


def resize(source: dict, target_canvas: dict) -> dict:
    """Choose a deterministic feasible candidate without mutating any input.

    If the constraints cannot all fit, return the least-violating conservative
    result and emit a warning. Never hide content to manufacture feasibility.
    """
    validate_source(source, target_canvas)
    analysis = analyze(source)
    candidates = generate_candidates(source, target_canvas, analysis)
    ranked = []
    for index, candidate in enumerate(candidates):
        result = evaluate(source, candidate, analysis)
        if result['hard_errors']:
            candidate = repair(source, candidate, analysis)
            result = evaluate(source, candidate, analysis)
        ranked.append((len(result['hard_errors']), result['score'], index, candidate, result))
    best = min(ranked, key=lambda item: item[:3])
    if best[0]:
        warnings.warn('No fully feasible layout: ' + '; '.join(best[4]['hard_errors']), RuntimeWarning, stacklevel=2)
    return best[3]
