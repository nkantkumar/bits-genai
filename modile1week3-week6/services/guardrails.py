import re


class GuardrailResult:

    def __init__(
        self,
        passed: bool,
        reason: str = ""
    ):
        self.passed = passed
        self.reason = reason


class EditorialGuardrail:

    def __init__(self):

        self.profanity_words = {
            "shit",
            "bullshit",
            "damn",
            "bitch"
        }

        self.harmful_patterns = [
            r"\bhow to make a bomb\b",
            r"\bhow to build a bomb\b",
            r"\bkill someone\b",
            r"\bhow to poison\b"
        ]

        self.informal_patterns = [
            r"\byoooo\b",
            r"\bwtf\b",
            r"\blol\b",
            r"\bomg\b",
            r"\bain't\b"
        ]


    def check_profanity(self, text: str):

        words = re.findall(
            r"\b\w+\b",
            text.lower()
        )

        for word in words:

            if word in self.profanity_words:

                return GuardrailResult(
                    False,
                    "Profanity detected."
                )

        return GuardrailResult(True)


    def check_harmful_content(self, text: str):

        text_lower = text.lower()

        for pattern in self.harmful_patterns:

            if re.search(
                pattern,
                text_lower
            ):

                return GuardrailResult(
                    False,
                    "Potentially harmful content detected."
                )

        return GuardrailResult(True)


    def check_professional_tone(self, text: str):

        text_lower = text.lower()

        for pattern in self.informal_patterns:

            if re.search(
                pattern,
                text_lower
            ):

                return GuardrailResult(
                    False,
                    "Professional tone requirement violated."
                )

        return GuardrailResult(True)


    def validate_input(self, text: str):

        if not text or not text.strip():

            return GuardrailResult(
                False,
                "Input cannot be empty."
            )


        harmful = self.check_harmful_content(text)

        if not harmful.passed:
            return harmful


        return GuardrailResult(
            True,
            "Input passed guardrails."
        )


    def validate_output(self, text: str):

        profanity = self.check_profanity(text)

        if not profanity.passed:
            return profanity


        harmful = self.check_harmful_content(text)

        if not harmful.passed:
            return harmful


        tone = self.check_professional_tone(text)

        if not tone.passed:
            return tone


        return GuardrailResult(
            True,
            "Output passed editorial guardrails."
        )