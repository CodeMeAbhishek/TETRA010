from typing import List, Dict
from models import MissingInvestigation

def aggregate_missing_investigations(engine_responses: List['EngineResponse']) -> List[dict]:
    """
    Aggregates and deduplicates missing investigations from all engines.
    """
    aggregated: Dict[str, dict] = {}
    
    for response in engine_responses:
        for missing in response.missing_inputs:
            # Simple deduplication by test name
            test_name = missing.test_name
            if test_name not in aggregated:
                aggregated[test_name] = {
                    "test_name": test_name,
                    "reasons": [missing.reason],
                    "guideline_citations": [missing.guideline_citation]
                }
            else:
                if missing.reason not in aggregated[test_name]["reasons"]:
                    aggregated[test_name]["reasons"].append(missing.reason)
                if missing.guideline_citation not in aggregated[test_name]["guideline_citations"]:
                    aggregated[test_name]["guideline_citations"].append(missing.guideline_citation)
                    
    # Format to list
    return list(aggregated.values())
