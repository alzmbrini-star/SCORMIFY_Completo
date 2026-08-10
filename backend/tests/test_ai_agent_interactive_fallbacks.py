from services.ai_agent import (
    _build_case_study_fallback_html,
    _build_timeline_fallback_html,
    _interactive_html_is_functional,
)


def _slide(kind):
    return {
        "type": kind,
        "title": "Evolução da energia solar",
        "moduleName": "Energia e eficiência",
        "elements": [
            {
                "type": "text",
                "content": (
                    "A tecnologia começou com aplicações experimentais. "
                    "A redução de custos ampliou o uso residencial. "
                    "Novas políticas incentivaram projetos corporativos. "
                    "Sistemas de armazenamento aumentaram a confiabilidade. "
                    "A integração à rede consolidou a adoção em larga escala."
                ),
            }
        ],
    }


def test_rejects_large_but_visually_empty_html():
    skeleton = "<!doctype html><html><head><style>" + (".x{color:red}" * 80) + "</style></head><body><div></div><script>const ready=true;</script></body></html>"
    assert not _interactive_html_is_functional(skeleton, "timeline")


def test_timeline_fallback_is_visible_and_interactive():
    result = _build_timeline_fallback_html(_slide("timeline"))
    assert "Evolução da energia solar" in result
    assert "const events=" in result
    assert "show(0)" in result
    assert _interactive_html_is_functional(result, "timeline")


def test_case_study_fallback_is_visible_and_interactive():
    result = _build_case_study_fallback_html(_slide("case_study"))
    assert "Evolução da energia solar" in result
    assert "Contexto" in result
    assert "Que decisão você tomaria" in result
    assert _interactive_html_is_functional(result, "case_study")
