import pytest

from mcp_infostat.results.parser import parse_infostat_output


def test_parse_descriptivos_single_variable() -> None:
    raw_text = """
Estadisticas descriptivas
Variable: Altura
  N      : 30
  Media  : 172.30
  D.E.   : 8.50
  Minimo : 155.00
  Maximo : 191.00
  C.V.%  : 4.94
"""

    parsed = parse_infostat_output(raw_text=raw_text, analysis_type="descriptivos")

    assert parsed["tipo"] == "descriptivos"
    assert parsed["variables"] == [
        {
            "nombre": "Altura",
            "n": 30,
            "media": 172.3,
            "desvio": 8.5,
            "minimo": 155.0,
            "maximo": 191.0,
            "cv": 4.94,
        }
    ]


def test_parse_normalidad_shapiro() -> None:
    raw_text = """
Prueba de normalidad (Shapiro-Wilk)
Variable: Altura
N: 30
W: 0.974
p-valor: 0.562
"""

    parsed = parse_infostat_output(raw_text=raw_text, analysis_type="normalidad")

    assert parsed["tipo"] == "normalidad"
    assert parsed["test"] == "shapiro_wilks"
    assert parsed["resultado"] == {
        "variable": "Altura",
        "n": 30,
        "estadistico": 0.974,
        "p_valor": 0.562,
    }


def test_parse_anova_dca_table_and_metrics() -> None:
    raw_text = """
Analisis de la Varianza
F.V.          SC      gl   CM      F      p-valor
Tratamiento   450.20  3    150.07  8.54   0.0002
Error         422.60  24   17.61
Total         872.80  27
R2: 0.52
C.V.%: 9.80
"""

    parsed = parse_infostat_output(raw_text=raw_text, analysis_type="anova_dca")

    assert parsed["tipo"] == "anova_dca"
    assert parsed["anova_table"][0] == {
        "fuente": "Tratamiento",
        "sc": 450.2,
        "gl": 3,
        "cm": 150.07,
        "f": 8.54,
        "p_valor": 0.0002,
    }
    assert parsed["anova_table"][1] == {
        "fuente": "Error",
        "sc": 422.6,
        "gl": 24,
        "cm": 17.61,
    }
    assert parsed["metrics"] == {"r2": 0.52, "cv": 9.8}


def test_parse_rejects_unknown_analysis_type() -> None:
    with pytest.raises(ValueError) as exc_info:
        parse_infostat_output(raw_text="x", analysis_type="desconocido")

    assert "analysis_type invalido" in str(exc_info.value)


def test_parse_descriptivos_requires_variable_block() -> None:
    with pytest.raises(ValueError) as exc_info:
        parse_infostat_output(raw_text="Estadisticas descriptivas sin variable", analysis_type="descriptivos")

    assert "No se detectaron bloques descriptivos" in str(exc_info.value)
