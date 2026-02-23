# pii_redaction.py
"""
PII Redaction for Observability
Required for GDPR, HIPAA, SOC2 compliance
"""

import re
from typing import Dict
from dotenv import load_dotenv

load_dotenv()


class PIIRedactor:
    """Redact PII before logging to observability platform."""

    PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b(\+?61[\s.-]?)?(04\d{2}[\s.-]?\d{3}[\s.-]?\d{3}|0[2-9]\d[\s.-]?\d{4}[\s.-]?\d{4})\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    }

    def redact(self, text: str) -> str:
        """Redact all PII patterns from text."""
        result = text
        for pii_type, pattern in self.PATTERNS.items():
            result = re.sub(pattern, f"[REDACTED_{pii_type.upper()}]", result)
        return result

    def redact_dict(self, data: Dict) -> Dict:
        """Recursively redact PII from a dictionary."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.redact(value)
            elif isinstance(value, dict):
                result[key] = self.redact_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.redact(v) if isinstance(v, str) else v for v in value
                ]
            else:
                result[key] = value
        return result





if __name__ == "__main__":
    # Test with a prompt containing PII
    test_prompt = """
    Please help me with my account. My email is abc.cde@example.com
    and my phone number is +61-040000000.
    """

    print("Testing PII redaction with LLM call...")
    result = secure_llm_call(test_prompt)
    print(f"Response: {result}")
