def read_keyword(keyword: str, l: list, result: list[str]) -> list[str]:
    """Read the `keyword` in a content `l` of some AST, appending new results to `result`."""

    if isinstance(l, list):
        if len(l) >= 3 and l[0] == keyword:
            result.append((l[1], l[2]))
            l = l[3:]

        for el in l:
            result = read_keyword(keyword, el, result)

    elif isinstance(l, dict):
        for el in l.values():
            result = read_keyword(keyword, el, result)

    return result

def list_dependencies(ast: dict) -> list[str]:
    """List all dependencies present in some AST."""
    expr = ast["v"]["expr"]
    raw_dependencies = read_keyword("Ser_Qualid", expr, [])

    dependencies = []
    for dir_path, name in raw_dependencies:
        dependencies.append(".".join(map(lambda w: w[1], dir_path[1] + [name])))

    return [dependency for i, dependency in enumerate(dependencies) if not dependency in dependencies[:i]]
