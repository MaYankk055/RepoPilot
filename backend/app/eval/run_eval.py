"""
RAGAS evaluation runner — runs the eval dataset through the agent and scores
faithfulness, answer relevancy, and context precision.
"""

import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.agent.graph import get_agent
from app.agent.state import GraphState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EVAL_DATASET_PATH = Path(__file__).parent / "dataset.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_eval_dataset() -> list[dict]:
    """Load the evaluation dataset."""
    with open(EVAL_DATASET_PATH) as f:
        return json.load(f)


def run_agent_on_question(question: str) -> dict:
    """Run the agent on a single question and collect outputs."""
    agent = get_agent()

    initial_state: GraphState = {
        "question": question,
        "documents": [],
        "generation": "",
        "web_search_needed": False,
        "confidence_score": 0.0,
        "citations": [],
        "trace_events": [],
        "retry_count": 0,
        "route_decision": "",
        "session_id": str(uuid.uuid4()),
        "escalated": False,
        "issue_url": "",
    }

    result = agent.invoke(initial_state)

    return {
        "answer": result.get("generation", ""),
        "contexts": [doc.page_content for doc in result.get("documents", [])],
        "confidence": result.get("confidence_score", 0.0),
        "route_decision": result.get("route_decision", ""),
    }


def run_evaluation():
    """
    Run the full evaluation pipeline:
    1. Load the eval dataset
    2. Run each question through the agent
    3. Score with RAGAS metrics
    4. Save results
    """
    dataset = load_eval_dataset()
    logger.info(f"Loaded {len(dataset)} eval questions")

    # ── Step 1: Run agent on each question ───────────────
    agent_results = []
    for i, entry in enumerate(dataset):
        question = entry["question"]
        category = entry["category"]
        logger.info(f"[{i+1}/{len(dataset)}] ({category}) {question}")

        try:
            result = run_agent_on_question(question)
            agent_results.append(
                {
                    "question": question,
                    "ground_truth": entry.get("ground_truth", ""),
                    "category": category,
                    "answer": result["answer"],
                    "contexts": result["contexts"],
                    "confidence": result["confidence"],
                    "route_decision": result["route_decision"],
                }
            )
            logger.info(
                f"  → confidence={result['confidence']:.2f}, "
                f"route={result['route_decision']}, "
                f"contexts={len(result['contexts'])}"
            )
        except Exception as e:
            logger.error(f"  → FAILED: {e}")
            agent_results.append(
                {
                    "question": question,
                    "ground_truth": entry.get("ground_truth", ""),
                    "category": category,
                    "answer": f"ERROR: {e}",
                    "contexts": [],
                    "confidence": 0.0,
                    "route_decision": "error",
                }
            )

    # ── Step 2: Run RAGAS evaluation ─────────────────────
    ragas_scores = {}
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision
        from datasets import Dataset

        # Filter to only questions that got actual answers (not errors/guardrails)
        scorable = [
            r
            for r in agent_results
            if r["category"] in ("answerable_from_docs", "answerable_from_web")
            and not r["answer"].startswith("ERROR")
            and r["contexts"]
        ]

        if scorable:
            ragas_dataset = Dataset.from_list(
                [
                    {
                        "question": r["question"],
                        "answer": r["answer"],
                        "contexts": r["contexts"],
                        "ground_truth": r["ground_truth"],
                    }
                    for r in scorable
                ]
            )

            ragas_results = evaluate(
                dataset=ragas_dataset,
                metrics=[faithfulness, answer_relevancy, context_precision],
            )

            ragas_scores = {
                "avg_faithfulness": float(ragas_results.get("faithfulness", 0)),
                "avg_answer_relevancy": float(
                    ragas_results.get("answer_relevancy", 0)
                ),
                "avg_context_precision": float(
                    ragas_results.get("context_precision", 0)
                ),
            }

            logger.info("\n" + "=" * 60)
            logger.info("RAGAS EVALUATION RESULTS")
            logger.info("=" * 60)
            for metric, score in ragas_scores.items():
                logger.info(f"  {metric}: {score:.4f}")
            logger.info("=" * 60)
        else:
            logger.warning("No scorable results for RAGAS evaluation")

    except ImportError:
        logger.warning(
            "RAGAS not installed — skipping metric evaluation. "
            "Install with: pip install ragas datasets"
        )
    except Exception as e:
        logger.error(f"RAGAS evaluation failed: {e}")

    # ── Step 3: Save results ─────────────────────────────
    run_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()

    eval_run = {
        "run_id": run_id,
        "timestamp": timestamp,
        "provider": settings.embedding_provider,
        "total_questions": len(agent_results),
        **ragas_scores,
        "results": agent_results,
    }

    # Save to file
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = RESULTS_DIR / f"eval_{run_id}.json"
    with open(results_file, "w") as f:
        json.dump(eval_run, f, indent=2, default=str)
    logger.info(f"Results saved to {results_file}")

    # Save to MongoDB (if available)
    try:
        from pymongo import MongoClient

        client = MongoClient(settings.mongodb_url)
        db = client[settings.mongodb_db]
        db["eval_results"].insert_one(eval_run)
        logger.info("Results saved to MongoDB")
    except Exception as e:
        logger.warning(f"Could not save to MongoDB: {e}")

    # ── Print summary table ──────────────────────────────
    print("\n" + "=" * 80)
    print(f"EVALUATION SUMMARY — Run {run_id}")
    print("=" * 80)
    print(f"{'Category':<25} {'Count':<8} {'Avg Confidence':<15}")
    print("-" * 48)

    for category in ["answerable_from_docs", "answerable_from_web", "genuinely_unknown", "out_of_scope"]:
        cat_results = [r for r in agent_results if r["category"] == category]
        if cat_results:
            avg_conf = sum(r["confidence"] for r in cat_results) / len(cat_results)
            print(f"{category:<25} {len(cat_results):<8} {avg_conf:.3f}")

    print("=" * 80)
    if ragas_scores:
        print(f"Faithfulness:      {ragas_scores.get('avg_faithfulness', 0):.4f}")
        print(f"Answer Relevancy:  {ragas_scores.get('avg_answer_relevancy', 0):.4f}")
        print(f"Context Precision: {ragas_scores.get('avg_context_precision', 0):.4f}")
    print("=" * 80)

    return eval_run


if __name__ == "__main__":
    run_evaluation()
