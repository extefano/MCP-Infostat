from __future__ import annotations

import re
import unicodedata
from typing import Any

SUPPORTED_ANALYSIS_TYPES = {"descriptivos", "normalidad", "anova_dca"}


def parse_infostat_output(raw_text: str, analysis_type: str) -> dict[str, Any]:
    requested = analysis_type.strip().lower()
    if requested not in SUPPORTED_ANALYSIS_TYPES:
        raise ValueError(
            f"analysis_type invalido: {analysis_type}. "
            f"Permitidos: {sorted(SUPPORTED_ANALYSIS_TYPES)}"
        )

    if requested == "descriptivos":
        return _parse_descriptivos(raw_text)
    if requested == "normalidad":
        return _parse_normalidad(raw_text)
    return _parse_anova_dca(raw_text)


def _parse_descriptivos(raw_text: str) -> dict[str, Any]:
    variables: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        normalized_line = _normalize_label(line)
        if normalized_line.startswith("variable:"):
            if current is not None:
                variables.append(current)
            variable_name = line.split(":", 1)[1].strip()
            current = {"nombre": variable_name}
            continue

        if current is None or ":" not in line:
            continue

        key, value = [part.strip() for part in line.split(":", 1)]
        key_normalized = _normalize_label(key)

        if key_normalized == "n":
            parsed = _parse_int(value)
            if parsed is not None:
                current["n"] = parsed
        elif key_normalized == "media":
            parsed = _parse_float(value)
            if parsed is not None:
                current["media"] = parsed
        elif key_normalized in {"d.e.", "d.e", "de", "desvio", "desvio estandar", "desviacion estandar"}:
            parsed = _parse_float(value)
            if parsed is not None:
                current["desvio"] = parsed
        elif key_normalized == "minimo":
            parsed = _parse_float(value)
            if parsed is not None:
                current["minimo"] = parsed
        elif key_normalized == "maximo":
            parsed = _parse_float(value)
            if parsed is not None:
                current["maximo"] = parsed
        elif key_normalized.startswith("c.v") or key_normalized in {"cv", "cv%", "c.v.%"}:
            parsed = _parse_float(value)
            if parsed is not None:
                current["cv"] = parsed

    if current is not None:
        variables.append(current)

    if not variables:
        raise ValueError("No se detectaron bloques descriptivos con 'Variable:'.")

    return {"tipo": "descriptivos", "variables": variables}


def _parse_normalidad(raw_text: str) -> dict[str, Any]:
    lowered_text = _normalize_label(raw_text)
    if "shapiro" in lowered_text:
        test = "shapiro_wilks"
    elif "kolmogorov" in lowered_text:
        test = "kolmogorov_smirnov"
    else:
        raise ValueError("No se detecto el tipo de test de normalidad.")

    result: dict[str, Any] = {}

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if ":" in line:
            key, value = [part.strip() for part in line.split(":", 1)]
            key_normalized = _normalize_label(key)

            if key_normalized == "variable":
                result["variable"] = value
            elif key_normalized == "n":
                parsed = _parse_int(value)
                if parsed is not None:
                    result["n"] = parsed
            elif key_normalized in {"w", "d", "estadistico"}:
                parsed = _parse_float(value)
                if parsed is not None:
                    result["estadistico"] = parsed
            elif key_normalized in {"p", "p valor", "p-valor", "pvalue", "p-value"}:
                parsed = _parse_float(value)
                if parsed is not None:
                    result["p_valor"] = parsed
            continue

        parts = [part for part in re.split(r"\s+", line) if part]
        if len(parts) >= 3 and "estadistico" not in result and "p_valor" not in result:
            parsed_stat = _parse_float(parts[-2])
            parsed_p = _parse_float(parts[-1])
            if parsed_stat is not None and parsed_p is not None:
                result.setdefault("variable", parts[0])
                result["estadistico"] = parsed_stat
                result["p_valor"] = parsed_p

    if "estadistico" not in result and "p_valor" not in result:
        raise ValueError("No se detectaron estadisticos de normalidad.")

    return {"tipo": "normalidad", "test": test, "resultado": result}


def _parse_anova_dca(raw_text: str) -> dict[str, Any]:
    anova_rows: list[dict[str, Any]] = []
    metrics: dict[str, float] = {}
    table_started = False

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        normalized_line = _normalize_label(line)
        if "f.v." in normalized_line or normalized_line.startswith("f.v") or normalized_line.startswith("fuente de variacion"):
            table_started = True
            continue

        if ":" in line:
            key, value = [part.strip() for part in line.split(":", 1)]
            key_normalized = _normalize_label(key)

            if key_normalized.startswith("r2") or key_normalized in {"r^2", "r cuadrado"}:
                parsed = _parse_float(value)
                if parsed is not None:
                    metrics["r2"] = parsed
            elif key_normalized.startswith("c.v") or key_normalized in {"cv", "cv%", "c.v.%"}:
                parsed = _parse_float(value)
                if parsed is not None:
                    metrics["cv"] = parsed
            continue

        if not table_started:
            continue

        parsed_row = _parse_anova_row(line)
        if parsed_row is not None:
            anova_rows.append(parsed_row)

    if not anova_rows:
        raise ValueError("No se detectaron filas de tabla ANOVA DCA.")

    payload: dict[str, Any] = {"tipo": "anova_dca", "anova_table": anova_rows}
    if metrics:
        payload["metrics"] = metrics
    return payload


def _parse_anova_row(line: str) -> dict[str, Any] | None:
    match = re.match(
        r"^\s*([A-Za-z0-9_(). ]+?)\s+(-?\d+(?:[.,]\d+)?)\s+(\d+)(?:\s+(-?\d+(?:[.,]\d+)?))?(?:\s+(-?\d+(?:[.,]\d+)?))?(?:\s+(-?\d+(?:[.,]\d+)?))?\s*$",
        line,
    )
    if match is None:
        return None

    source = re.sub(r"\s+", " ", match.group(1)).strip()
    sc = _parse_float(match.group(2))
    gl = _parse_int(match.group(3))

    if sc is None or gl is None:
        return None

    row: dict[str, Any] = {"fuente": source, "sc": sc, "gl": gl}

    cm = _parse_float(match.group(4))
    f_value = _parse_float(match.group(5))
    p_value = _parse_float(match.group(6))

    if cm is not None:
        row["cm"] = cm
    if f_value is not None:
        row["f"] = f_value
    if p_value is not None:
        row["p_valor"] = p_value

    return row


def _normalize_label(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    compacted = re.sub(r"\s+", " ", without_accents.strip().lower())
    return compacted


def _extract_number_token(value: str) -> str | None:
    match = re.search(r"-?\d+(?:[.,]\d+)?", value)
    if match is None:
        return None

    token = match.group(0)
    if "," in token and "." in token:
        token = token.replace(".", "").replace(",", ".")
    elif "," in token:
        token = token.replace(",", ".")

    return token


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None

    token = _extract_number_token(value)
    if token is None:
        return None

    try:
        return float(token)
    except ValueError:
        return None


def _parse_int(value: str | None) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(parsed)
