from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TARGET_FILES = [
    ROOT / 'eacis' / 'app.py',
    ROOT / 'eacis' / 'config.py',
]

# Patterns that often indicate sensitive log leakage.
DENY_PATTERNS = [
    re.compile(r'request\.form', re.IGNORECASE),
    re.compile(r'password', re.IGNORECASE),
    re.compile(r'authorization', re.IGNORECASE),
    re.compile(r'secret_key', re.IGNORECASE),
    re.compile(r'tools/login_error\.log', re.IGNORECASE),
]


def line_is_logging_context(line: str) -> bool:
    lowered = line.lower()
    return any(token in lowered for token in ['logger', 'log', 'print(', 'traceback'])


def run_check() -> int:
    findings = []

    for file_path in TARGET_FILES:
        if not file_path.exists():
            continue
        lines = file_path.read_text(encoding='utf-8').splitlines()
        for idx, line in enumerate(lines, start=1):
            if not line_is_logging_context(line):
                continue
            for pattern in DENY_PATTERNS:
                if pattern.search(line):
                    findings.append(f'{file_path.name}:{idx}: {line.strip()}')

    if findings:
        print('FAIL sensitive logging patterns found:')
        for finding in findings:
            print(finding)
        return 1

    print('PASS no sensitive logging patterns found in logging contexts')
    return 0


if __name__ == '__main__':
    raise SystemExit(run_check())
