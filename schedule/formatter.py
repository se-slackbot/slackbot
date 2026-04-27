def format_course_list(courses: list[dict]) -> str:
    if not courses:
        return "오늘은 강의가 없습니다. :tada:"

    lines = []
    for c in courses:
        room = f" | {c['room']}" if c.get("room") else ""
        lines.append(f"• *{c['start_time']} ~ {c['end_time']}*  {c['course_name']}{room}")
    return "\n".join(lines)
