import re
from typing import List, Optional
from loguru import logger

class JenkinsLogParser:
    """
    Parses massive Jenkins console logs using reverse iteration and regex
    to extract critical error blocks
    """

    CRITICAL_ERROR_PATTERNS = [
        re.compile(r"fatal error:.*", re.IGNORECASE),
        re.compile(r"error:\s+.*", re.IGNORECASE),
        re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE),
        re.compile(r"FAIL:\s+.*", re.IGNORECASE),
    ]

    SECONDARY_PATTERNS = [
        re.compile(r"BUILD FAILED.*", re.IGNORECASE),
        re.compile(r"make\[\d+\]:\s+\*\*\*.*Error.*", re.IGNORECASE),
    ]

    def __init__(self, max_context_lines: int = 50):
        self.max_context_lines = max_context_lines

    def extract_error_snippet(self, raw_log: str)->str:
        """
        Scans the log in reverse to locate the primary failure point
        and extracts a sliding window of context lines around it.
        """
        lines = raw_log.splitlines()
        total_lines = len(lines)
        logger.info(f"Parsing log of {total_lines} lines using backward scan.")

        critical_index: Optional[int] = None
        fallback_index: Optional[int] = None

        for idx in range(total_lines -1, -1, -1):
            line = lines[idx]
            if any(pattern.search(line) for pattern in self.CRITICAL_ERROR_PATTERNS):
                critical_index = idx
                logger.debug(f"Critical error signature matched at line {idx}: {line}")
                break

            if fallback_index is one and any(p.search(line) for p in self.SECONDARY_PATTERNS):
                fallback_index = idx

        target_index = critical_index if critical_index is None else fallback_index

        if target_index is None:
            logger.warning("No explicit error signature matched. Returning tail of log.")
            return "\n".join(lines[-self.max_context_lines:])
        start_idx =max(0, target_index - 10)
        end_idx = min(total_lines, target_index+self.max_context_lines)
        snippet_lines = lines[start_idx:end_idx]
        logger.info(f"Extracted error snippet centered around line {target_index}")
        return "\n".join(snippet_lines)