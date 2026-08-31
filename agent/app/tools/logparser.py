import os
import re
from typing import List, Optional,Any , Dict
from loguru import logger
from langchain_core.tools import tool 
from pydantic import BaseModel,Field

class JenkinsLogParser:
    """
    Parses massive Jenkins console logs using a global top-to-bottom scan 
    to extract all critical error blocks and failure points.
    """

    CRITICAL_ERROR_PATTERNS = [
        re.compile(r"fatal error:.*", re.IGNORECASE),
        re.compile(r"error:\s+.*", re.IGNORECASE),
        re.compile(r"KeyError:.*", re.IGNORECASE),          
        re.compile(r"ValueError:.*", re.IGNORECASE),
        re.compile(r"TypeError:.*", re.IGNORECASE),
        re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE),
        re.compile(r"FAIL:\s+.*", re.IGNORECASE),
        re.compile(r"skipped due to", re.IGNORECASE),
        re.compile(r"exit code [1-9]", re.IGNORECASE),
    ]

    SECONDARY_PATTERNS = [
        re.compile(r"BUILD FAILED.*", re.IGNORECASE),
        re.compile(r"ERROR: Error cloning remote repo.*", re.IGNORECASE),
        re.compile(r"make\[\d+\]:\s+\*\*\*.*Error.*", re.IGNORECASE),
    ]

    def __init__(self, max_context_lines: int = 50):
        self.half_window = max_context_lines // 2 

    def extract_error_snippets(self, raw_log: str) -> List[Dict[str, Any]]:
        """
        Scans the entire log from top to bottom, finding ALL matching error points 
        and extracting context snippets for each.
        """
        lines = raw_log.splitlines()
        total_lines = len(lines)
        logger.info(f"Scanning entire log of {total_lines} lines globally.")

        matched_issues = []
        seen_indices = set()

        # Global top-to-bottom scan
        for idx, line in enumerate(lines):
            priority = None
            
            # Check high priority python-style exceptions first
            if any(exc in line for exc in ["KeyError:", "IndexError:", "ValueError:", "TypeError:", "fatal error:", "executable is missing:"]):
                priority = 0
            elif any(p.search(line) for p in self.CRITICAL_ERROR_PATTERNS):
                priority = 1
            elif any(p.search(line) for p in self.SECONDARY_PATTERNS):
                priority = 2

            if priority is not None:
                # Prevent overlapping context windows for lines right next to each other
                if any(abs(idx - existing_idx) < self.half_window for existing_idx in seen_indices):
                    continue

                seen_indices.add(idx)
                
                # Extract sliding window around the matched line
                start_id = max(0, idx - self.half_window)
                end_idx = min(total_lines, idx + self.half_window + 1)
                snippet = "\n".join(lines[start_id:end_idx])

                matched_issues.append({
                    "line_number": idx + 1,
                    "matched_line": line.strip(),
                    "priority": priority,
                    "context_snippet": snippet
                })
        matched_issues.sort(key=lambda x: (x["priority"], x["line_number"]))
        if not matched_issues:
            logger.warning("No explicit error patterns matched globally. Returning tail of log.")
            fallback_snippet = "\n".join(lines[-self.half_window * 2:])
            return [{
                "line_number": total_lines,
                "matched_line": "No pattern matched (Tail Fallback)",
                "priority": 99,
                "context_snippet": fallback_snippet
            }]

        logger.info(f"Global scan complete. Found {len(matched_issues)} distinct failure/error points.")
        return matched_issues

class LogParserInput(BaseModel):
    file_path: str = Field(description="Absolute file path to the raw Jenkins console log on disk")
    max_context_lines: int = Field(default=50, description="Number of context lines surrounding the matched error")

@tool("parse_jenkins_log",args_schema=LogParserInput)
def parse_jenkins_log_tool(file_path: str, max_context_lines:int=50)->List[Dict[str,any]]:
    """
    Reads a raw Jenkins log file from disk and parses all critical error signatures, 
    returning context snippets for Root Cause Analysis.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Log file not found at path: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        raw_log_content = file.read()

    parser = JenkinsLogParser(max_context_lines=max_context_lines)
    return parser.extract_error_snippets(raw_log=raw_log_content)