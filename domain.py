"""Input validation and domain rules for FocusBoard."""
from datetime import date

PRIORITIES = {"Low", "Medium", "High"}


class ValidationError(ValueError):
    """User-provided input is invalid."""


def validate_task(payload):
    if not isinstance(payload, dict):
        raise ValidationError("Request must be a JSON object.")

    title = payload.get("title", "")
    course = payload.get("course", "")
    due_date = payload.get("due_date")
    priority = payload.get("priority", "Medium")

    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 80:
        raise ValidationError("Title must contain 1–80 characters.")
    if not isinstance(course, str) or len(course.strip()) > 40:
        raise ValidationError("Course must contain at most 40 characters.")
    if not isinstance(priority, str) or priority not in PRIORITIES:
        raise ValidationError("Priority must be Low, Medium, or High.")
    if due_date in (None, ""):
        due_date = None
    elif not isinstance(due_date, str):
        raise ValidationError("Due date must use YYYY-MM-DD.")
    else:
        try:
            parsed = date.fromisoformat(due_date)
            if parsed.isoformat() != due_date:
                raise ValueError("Incorrect format")
        except ValueError as exc:
            raise ValidationError("Due date must use YYYY-MM-DD.") from exc

    return {
        "title": title.strip(),
        "course": course.strip(),
        "due_date": due_date,
        "priority": priority,
    }


def validate_done(payload):
    if not isinstance(payload, dict) or type(payload.get("is_done")) is not bool:
        raise ValidationError("is_done must be true or false.")
    return payload["is_done"]
