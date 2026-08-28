from pathlib import Path
from loguru import logger
from app.log_parser import JenkinsLogParser
from app.llm_client import OllamaRCAClient

def test_rca_pipeline():
    logger.info("=== STARTING MULTI-ERROR RCA PIPELINE TEST ===")

    log_path = Path("profiling_error.txt")
    if not log_path.exists():
        logger.error(f"Log file not found at {log_path}")
        return

    raw_log = log_path.read_text(encoding="utf-8")

    # 1. Extract all error snippets from the log
    parser = JenkinsLogParser(max_context_lines=30)
    error_snippets_list = parser.extract_error_snippets(raw_log)

    print("\n" + "-"*40 + f" EXTRACTED {len(error_snippets_list)} ERROR SNIPPETS " + "-"*40)
    for issue in error_snippets_list:
        print(f"-> Line {issue['line_number']} (Priority {issue['priority']}): {issue['matched_line']}")
    print("-" * 80 + "\n")

    # 2. Initialize RCA client
    rca_client = OllamaRCAClient()
    all_rca_reports = []

    logger.info("Starting sequential batch analysis of all extracted error points...")

    # 3. Iterate through every extracted error point sequentially and show its context
    for idx, issue in enumerate(error_snippets_list, start=1):
        print(f"\n" + "="*10 + f" ERROR [{idx}/{len(error_snippets_list)}] CONTEXT (Line {issue['line_number']}, Priority {issue['priority']}) " + "="*10 + "\n")
        print(issue['context_snippet'])
        print("\n" + "-" * 80 + "\n")

        logger.info(f"Analyzing error [{idx}/{len(error_snippets_list)}] at Line {issue['line_number']} (Priority {issue['priority']})")
        
        # Enrich context with the absolute log line number for the local model
        file_context = f"This error snippet originates from absolute log Line {issue['line_number']} with Priority {issue['priority']}."

        # Call the LLM client
        json_response = rca_client.analyze_failure(
            error_snippet=issue['context_snippet'], 
            file_context=file_context
        )

        # Force-assign the exact parser-tracked line number and priority to guarantee absolute metadata accuracy
        json_response['line_number'] = issue['line_number']
        json_response['priority'] = issue['priority']

        all_rca_reports.append(json_response)

    # 4. Output the final aggregated batch report
    print("\n" + "="*30 + " AGGREGATED BATCH RCA JSON REPORT " + "="*30)
    for report in all_rca_reports:
        print(report)
    print("=" * 80 + "\n")
    logger.info(f"Batch RCA analysis complete. Successfully processed {len(all_rca_reports)} issues.")

if __name__ == "__main__":
    test_rca_pipeline()