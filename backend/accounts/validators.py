import re

from django.core.exceptions import ValidationError

SPECIAL = re.compile(r"[^A-Za-z0-9]")


def password_problems(password: str) -> list[str]:
    """Brightloop policy: more than 8 characters, an uppercase, a lowercase and a special character."""
    problems = []
    if len(password) <= 8:
        problems.append("Password must be more than 8 characters.")
    if not re.search(r"[A-Z]", password):
        problems.append("Password must contain an uppercase letter.")
    if not re.search(r"[a-z]", password):
        problems.append("Password must contain a lowercase letter.")
    if not SPECIAL.search(password):
        problems.append("Password must contain a special character.")
    return problems


class BrightloopPasswordValidator:
    def validate(self, password, user=None):
        problems = password_problems(password)
        if problems:
            raise ValidationError(problems)

    def get_help_text(self):
        return "More than 8 characters with an uppercase letter, a lowercase letter and a special character."
