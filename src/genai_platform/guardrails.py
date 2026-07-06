from genai_platform.config import Settings
from genai_platform.domain.guardrail_rules import check_prompt_injection, check_toxicity
from genai_platform.domain.models import GuardrailResult

__all__ = ["GuardrailResult", "InputGuardrails", "OutputGuardrails"]


class InputGuardrails:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.toxicity_threshold = settings.guardrails_toxicity_threshold

    async def validate(self, text: str) -> GuardrailResult:
        triggered: list[str] = []

        injection = self._check_prompt_injection(text)
        if injection:
            return GuardrailResult(
                blocked=True,
                reason=injection,
                triggered_rules=[injection],
            )

        toxicity = self._check_toxicity(text)
        if toxicity:
            return GuardrailResult(
                blocked=True,
                reason=toxicity,
                triggered_rules=[toxicity],
            )

        pii_result = await self._sanitize_pii(text)
        if pii_result.triggered_rules:
            triggered.extend(pii_result.triggered_rules)

        sanitized = pii_result.sanitized_text or text

        return GuardrailResult(
            blocked=False,
            sanitized_text=sanitized,
            triggered_rules=triggered,
        )

    def _check_prompt_injection(self, text: str) -> str | None:
        return check_prompt_injection(text)

    def _check_toxicity(self, text: str) -> str | None:
        return check_toxicity(text)

    async def _sanitize_pii(self, text: str) -> GuardrailResult:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            from presidio_anonymizer.entities import OperatorConfig

            analyzer = AnalyzerEngine()
            anonymizer = AnonymizerEngine()

            results = analyzer.analyze(
                text=text,
                entities=self.settings.guardrails_pii_entities,
                language="fr",
                score_threshold=0.6,
            )

            if not results:
                return GuardrailResult(blocked=False)

            anonymized = anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators={
                    "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
                },
            )

            return GuardrailResult(
                blocked=False,
                sanitized_text=anonymized.text,
                triggered_rules=[f"pii:{r.entity_type}" for r in results],
            )
        except ImportError:
            return GuardrailResult(blocked=False)


class OutputGuardrails:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def validate(self, text: str) -> GuardrailResult:
        triggered: list[str] = []

        pii_result = await self._check_pii_leakage(text)
        if pii_result.triggered_rules:
            triggered.extend(pii_result.triggered_rules)

        return GuardrailResult(
            blocked=False,
            sanitized_text=pii_result.sanitized_text or text,
            triggered_rules=triggered,
        )

    async def _check_pii_leakage(self, text: str) -> GuardrailResult:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            from presidio_anonymizer.entities import OperatorConfig

            analyzer = AnalyzerEngine()
            anonymizer = AnonymizerEngine()

            results = analyzer.analyze(
                text=text,
                entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "SSN"],
                language="fr",
                score_threshold=0.6,
            )

            if not results:
                return GuardrailResult(blocked=False)

            anonymized = anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators={
                    "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
                },
            )

            return GuardrailResult(
                blocked=False,
                sanitized_text=anonymized.text,
                triggered_rules=[f"pii_output:{r.entity_type}" for r in results],
            )
        except ImportError:
            return GuardrailResult(blocked=False)
