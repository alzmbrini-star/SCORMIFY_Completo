"""Read canvas dimensions without altering the saved slide or course."""
import math

def video_slide_dimensions(slide, course):
    def positive(value, fallback):
        try:
            result = float(value)
            return result if result > 0 and math.isfinite(result) else fallback
        except (TypeError, ValueError):
            return fallback
    return (
        positive(slide.get('width'), positive(course.get('width'), 1920)),
        positive(slide.get('height'), positive(course.get('height'), 820)),
    )
