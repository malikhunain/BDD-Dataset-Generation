import re

def _extract_blocks(raw: str):
    gherkin_pattern = re.compile(
        r"```(?:gherkin|feature|cucumber)\s*\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    python_pattern = re.compile(
        r"```(?:python|py)\s*\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )

    gherkin_matches = gherkin_pattern.findall(raw)
    python_matches  = python_pattern.findall(raw)

    if gherkin_matches and python_matches:
        return gherkin_matches[0].strip(), python_matches[0].strip()

    any_block = re.compile(r"```\w*\s*\n(.*?)```", re.DOTALL)
    all_blocks = any_block.findall(raw)
    if len(all_blocks) >= 2:
        feature, steps = None, None
        for block in all_blocks[:4]:
            b = block.strip()
            if feature is None and ("Feature:" in b or "Scenario:" in b):
                feature = b
            elif steps is None and ("def " in b or "from behave" in b or "@given" in b.lower()):
                steps = b
        if feature and steps:
            return feature, steps

    feature_section = re.search(
        r"### FEATURE FILE.*?```\w*\s*\n(.*?)```",
        raw, re.DOTALL | re.IGNORECASE,
    )
    steps_section = re.search(
        r"### STEP DEFINITIONS.*?```\w*\s*\n(.*?)```",
        raw, re.DOTALL | re.IGNORECASE,
    )
    if feature_section and steps_section:
        return feature_section.group(1).strip(), steps_section.group(1).strip()

    return None, None