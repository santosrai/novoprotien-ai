import re


ALLOWED_CALLS = {
    "builder.loadStructure",
    "builder.addCartoonRepresentation",
    "builder.addBallAndStickRepresentation",
    "builder.addSurfaceRepresentation",
    "builder.addWaterRepresentation",
    "builder.highlightLigands",
    "builder.focusView",
    "builder.clearStructure",
}


def violates_whitelist(code: str) -> bool:
    # A very conservative check: ensure every builder.<method>( occurrence is in the whitelist
    method_calls = re.findall(r"builder\.[a-zA-Z0-9_]+\s*\(", code or "")
    for call in method_calls:
        method = call.strip().rstrip("(")
        if method not in ALLOWED_CALLS:
            return True
    return False


def infer_loaded_pdb(code: str) -> str | None:
    if not code:
        return None
    m = re.search(r"builder\.loadStructure\s*\(\s*['\"]([A-Za-z0-9]{4})['\"]\s*\)", code)
    if m:
        return m.group(1).upper()
    return None


def ensure_clear_on_change(current_code: str | None, new_code: str) -> str:
    """If new_code loads a different PDB than current_code, inject a clearStructure() call at the top of try-block.
    Heuristic, non-invasive.
    """
    if not new_code:
        return new_code
    prev = infer_loaded_pdb(current_code or "")
    new = infer_loaded_pdb(new_code)
    if prev and new and prev != new:
        # Insert after first try { or at the beginning
        inserted = new_code
        try:
            inserted = re.sub(
                r"try\s*\{",
                "try {\n  await builder.clearStructure();",
                new_code,
                count=1,
            )
        except Exception:
            inserted = new_code
        if inserted == new_code:
            inserted = "await builder.clearStructure();\n" + new_code
        return inserted
    return new_code

