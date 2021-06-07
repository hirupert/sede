def fix_oov(pred: str) -> str:
    fixed = pred.replace(" ⁇ ", "<")
    fixed = fixed.replace("<unk>", "<")
    return fixed
