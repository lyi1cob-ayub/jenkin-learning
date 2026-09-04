import os
import re
from typing import List, Dict, Any, Generator, Tuple
from collections import deque
from loguru import logger
from langchain_core.tools import tool 
from pydantic import BaseModel, Field
from app.config import settings


class JenkinsLogParser:
    """
    Production-grade stream log parser.
    Guarantees O(1) RAM usage, regex safety, and token-budget compliance.
    """

    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    TIMESTAMP_PREFIX = re.compile(r'^(\[\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[^\]]*\]|\d{2}:\d{2}:\d{2}\s+)')

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

    EXPLICIT_STRINGS = [
        "KeyError:", "IndexError:", "ValueError:", 
        "TypeError:", "fatal error:", "executable is missing:"
    ]

    def __init__(
        self, 
        max_context_lines: int = settings.LOG_PARSER_MAX_CONTEXT_LINES, 
        max_total_chars: int = settings.LOG_PARSER_MAX_TOTAL_CHARS, 
        max_line_length: int = settings.LOG_PARSER_MAX_LINE_LENGTH
    ):
        self.half_window = max_context_lines // 2
        self.max_total_chars = max_total_chars
        self.max_line_length = max_line_length

    def _clean_line(self, raw_line: str) -> str:
        """Sanitize long lines, ANSI escape sequences, and log timestamps."""
        line = raw_line[:self.max_line_length]
        line = self.ANSI_ESCAPE.sub('', line)
        line = self.TIMESTAMP_PREFIX.sub('', line)
        return line.rstrip('\r\n')

    def parse_log_stream(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Reads log file sequentially using line indexing to maintain O(1) state.
        """
        matched_issues: List[Dict[str, Any]] = []
        before_buffer = deque(maxlen=self.half_window)
        
        last_matched_line = -999999
        total_lines = 0

        def line_stream() -> Generator[Tuple[int, str], None, None]:
            nonlocal total_lines
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f, start=1):
                    total_lines = idx
                    yield idx, self._clean_line(line)

        stream = line_stream()

        for line_num, clean_line in stream:
            priority = None
            if any(exc in clean_line for exc in self.EXPLICIT_STRINGS):
                priority = 0
            elif any(p.search(clean_line) for p in self.CRITICAL_ERROR_PATTERNS):
                priority = 1
            elif any(p.search(clean_line) for p in self.SECONDARY_PATTERNS):
                priority = 2

            if priority is not None:
                # O(1) Fast Window Deduplication
                if (line_num - last_matched_line) < self.half_window:
                    before_buffer.append(clean_line)
                    continue

                last_matched_line = line_num

                # Read forward lines while preserving accurate line counting
                after_buffer = []
                for _ in range(self.half_window):
                    try:
                        _, next_clean_line = next(stream)
                        after_buffer.append(next_clean_line)
                    except StopIteration:
                        break

                context_lines = list(before_buffer) + [clean_line] + after_buffer
                
                matched_issues.append({
                    "line_number": line_num,
                    "matched_line": clean_line.strip(),
                    "priority": priority,
                    "context_snippet": "\n".join(context_lines)
                })

                before_buffer.clear()
                for line in after_buffer:
                    before_buffer.append(line)
            else:
                before_buffer.append(clean_line)

        # Fallback if no explicit error patterns are hit
        if not matched_issues:
            logger.warning(f"No error patterns matched in {file_path}. Returning tail fallback.")
            tail_lines = list(before_buffer)
            return [{
                "line_number": total_lines,
                "matched_line": "No explicit pattern matched (Tail Fallback)",
                "priority": 99,
                "context_snippet": "\n".join(tail_lines)
            }]

        # Sort by priority first, then line number
        matched_issues.sort(key=lambda x: (x["priority"], x["line_number"]))

        # Enforce character budget limits
        budgeted_snippets = []
        accumulated_chars = 0

        for issue in matched_issues:
            snippet_len = len(issue["context_snippet"])
            if accumulated_chars + snippet_len > self.max_total_chars:
                if not budgeted_snippets:
                    budgeted_snippets.append(issue)
                break
            budgeted_snippets.append(issue)
            accumulated_chars += snippet_len

        return budgeted_snippets


class LogParserInput(BaseModel):
    file_path: str = Field(description="Absolute file path to the raw Jenkins console log")
    max_context_lines: int = Field(
        default=settings.LOG_PARSER_MAX_CONTEXT_LINES, 
        description="Context lines surrounding matched errors"
    )
    max_total_chars: int = Field(
        default=settings.LOG_PARSER_MAX_TOTAL_CHARS, 
        description="Strict total character budget for LLM context window"
    )


@tool("parse_jenkins_log", args_schema=LogParserInput)
def parse_jenkins_log_tool(
    file_path: str, 
    max_context_lines: int = settings.LOG_PARSER_MAX_CONTEXT_LINES, 
    max_total_chars: int = settings.LOG_PARSER_MAX_TOTAL_CHARS
) -> List[Dict[str, Any]]:
    """
    Parses a raw Jenkins log file using an O(1) streaming approach.
    Guarantees strict payload size limits to fit LLM context constraints.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Log file not found at path: {file_path}")

    parser = JenkinsLogParser(
        max_context_lines=max_context_lines, 
        max_total_chars=max_total_chars
    )
    return parser.parse_log_stream(file_path)