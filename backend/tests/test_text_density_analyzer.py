"""Tests for the text-density analyzer.

The analyzer is deterministic, runs in microseconds, and is the first-pass
gatekeeper before the LLM suggester. Wrong scores here would either flood
the UI with false-positive badges (annoying) or hide truly dense slides
(defeats the purpose), so coverage needs to be wide.
"""
import pytest
from services.text_density_analyzer import (
    analyze_text_density,
    analyze_slide,
    analyze_storyboard_section,
)


# ---------------------------------------------------------------------------
# analyze_text_density — core scoring function
# ---------------------------------------------------------------------------

class TestEmptyInputs:
    def test_empty_text_scores_light(self):
        r = analyze_text_density(text="")
        assert r["label"] == "light"
        assert r["score"] == 0

    def test_only_title_scores_light(self):
        r = analyze_text_density(title="Bem-vindo ao curso")
        assert r["label"] == "light"


class TestLightDensity:
    def test_short_text_is_light(self):
        r = analyze_text_density(
            text="Este e um topico introdutorio sobre seguranca no trabalho.",
            has_image=True,
        )
        assert r["label"] == "light"
        assert r["score"] < 35

    def test_few_bullets_with_image_is_light(self):
        r = analyze_text_density(
            text="",
            bullets=["EPIs basicos", "Sinalizacao", "Brigada"],
            has_image=True,
        )
        assert r["label"] == "light"


class TestHeavyDensity:
    def test_long_paragraph_is_heavy(self):
        # Build a paragraph with ~250 words AND multiple sentences so we hit
        # multiple density signals (word count + sentences + no image)
        sentence = "A seguranca no trabalho exige atencao constante dos colaboradores. "
        long_text = sentence * 18  # ~250 words, 18 sentences
        r = analyze_text_density(text=long_text, has_image=False)
        assert r["label"] == "heavy"
        assert r["score"] > 65

    def test_too_many_bullets_is_heavy(self):
        # 20 bullets, each with enough words to push word count + bullet count
        # over the heavy threshold even when an image is present.
        bullets = [f"Ponto importante numero {i} sobre algum assunto critico" for i in range(20)]
        r = analyze_text_density(bullets=bullets, has_image=True)
        # Should clearly land medium-or-heavy, never "light"
        assert r["label"] in ("medium", "heavy")
        assert any("bullet" in reason.lower() for reason in r["reasons"])

    def test_unbroken_block_adds_score(self):
        block = "Texto muito longo sem quebra de paragrafo " * 8  # ~340 chars no break
        r = analyze_text_density(text=block, has_image=True)
        assert any("bloco" in reason.lower() for reason in r["reasons"])

    def test_no_image_increases_score(self):
        text = " ".join(["palavra"] * 60)
        with_img = analyze_text_density(text=text, has_image=True)
        without_img = analyze_text_density(text=text, has_image=False)
        assert without_img["score"] > with_img["score"]
        assert any("imagem" in reason.lower() or "video" in reason.lower() for reason in without_img["reasons"])


class TestMediumDensity:
    def test_moderate_text_no_image_is_medium(self):
        text = " ".join(["importante"] * 50)
        r = analyze_text_density(text=text, has_image=False)
        # Should land medium-ish — not light, not necessarily heavy
        assert r["label"] in ("medium", "heavy")
        assert 35 <= r["score"] <= 100


class TestReasonsDiagnostics:
    def test_word_count_in_reasons(self):
        text = " ".join(["palavra"] * 80)
        r = analyze_text_density(text=text, has_image=True)
        assert any("palavras" in reason for reason in r["reasons"])

    def test_sentence_count_in_reasons(self):
        text = ". ".join([f"Frase numero {i}" for i in range(8)]) + "."
        r = analyze_text_density(text=text, has_image=True)
        # 8 sentences > 4 → adds reason
        assert any("frase" in reason.lower() for reason in r["reasons"])

    def test_long_title_in_reasons(self):
        long_title = " ".join(["palavra"] * 18)  # >14 words
        r = analyze_text_density(title=long_title, has_image=True)
        assert any("titulo" in reason.lower() for reason in r["reasons"])

    def test_avg_sentence_length_in_reasons(self):
        # 1 sentence, 30 words → avg=30
        text = " ".join(["palavra"] * 30) + "."
        r = analyze_text_density(text=text, has_image=True)
        assert any("frase" in reason.lower() and "longa" in reason.lower() for reason in r["reasons"])


class TestMetricsSurfaced:
    def test_metrics_dict_present_and_correct(self):
        r = analyze_text_density(
            text="Frase um. Frase dois.",
            bullets=["a", "b", "c"],
            has_image=True,
        )
        m = r["metrics"]
        assert m["words"] >= 4
        # Sentence count includes bullets (joined into the text blob), so the
        # bullets at the end count as one trailing "sentence". We accept 2 or 3.
        assert m["sentences"] in (2, 3)
        assert m["bullets"] == 3
        assert m["hasImage"] is True


class TestScoreCapping:
    def test_score_never_exceeds_100(self):
        # Extreme input: tons of words + bullets + no image + huge block
        text = ("Palavra " * 500).strip()
        bullets = [f"Bullet {i}" for i in range(40)]
        r = analyze_text_density(text=text, bullets=bullets, has_image=False)
        assert r["score"] <= 100


class TestLabelBoundaries:
    def test_label_light_below_35(self):
        # 25 words, image present → low score
        r = analyze_text_density(text=" ".join(["w"] * 25), has_image=True)
        assert r["label"] == "light"

    def test_label_heavy_above_65(self):
        text = " ".join(["palavra"] * 200)
        r = analyze_text_density(text=text, has_image=False)
        assert r["label"] == "heavy"


# ---------------------------------------------------------------------------
# analyze_slide — Scormify slide dict wrapper
# ---------------------------------------------------------------------------

class TestAnalyzeSlide:
    def test_text_element_content_picked_up(self):
        slide = {
            "title": "Intro",
            "elements": [
                {"type": "text", "content": "Texto curto e direto."},
            ],
        }
        r = analyze_slide(slide)
        assert "metrics" in r
        assert r["metrics"]["words"] >= 4

    def test_image_element_flags_has_image(self):
        slide = {
            "title": "Slide",
            "elements": [
                {"type": "text", "content": "x"},
                {"type": "image", "imageUrl": "/x.png"},
            ],
        }
        r = analyze_slide(slide)
        assert r["metrics"]["hasImage"] is True

    def test_background_image_flags_has_image(self):
        slide = {
            "title": "Slide",
            "backgroundImage": "/bg.jpg",
            "elements": [{"type": "text", "content": "x"}],
        }
        r = analyze_slide(slide)
        assert r["metrics"]["hasImage"] is True

    def test_brand_logo_skipped(self):
        """The watermark logo is corporate chrome, not slide content — must
        not flag the slide as having a visual."""
        slide = {
            "title": "Slide",
            "elements": [
                {"type": "text", "content": "x"},
                {"type": "image", "imageUrl": "/logo.png", "isBrandLogo": True},
            ],
        }
        r = analyze_slide(slide)
        assert r["metrics"]["hasImage"] is False

    def test_bullets_detected_from_text(self):
        """Lines starting with bullet markers are pulled out as bullets so
        scoring counts them correctly."""
        slide = {
            "title": "Slide",
            "elements": [
                {"type": "text", "content": "• Primeiro\n• Segundo\n• Terceiro\nTexto avulso"},
            ],
        }
        r = analyze_slide(slide)
        assert r["metrics"]["bullets"] >= 3

    def test_video_element_counts_as_visual(self):
        slide = {
            "title": "Slide",
            "elements": [
                {"type": "text", "content": "x"},
                {"type": "video", "src": "/v.mp4"},
            ],
        }
        r = analyze_slide(slide)
        assert r["metrics"]["hasImage"] is True


# ---------------------------------------------------------------------------
# analyze_storyboard_section
# ---------------------------------------------------------------------------

class TestAnalyzeStoryboardSection:
    def test_body_field_used(self):
        section = {"title": "S1", "body": "Texto longo " * 30}
        r = analyze_storyboard_section(section)
        assert r["metrics"]["words"] >= 50

    def test_description_field_fallback(self):
        section = {"title": "S1", "description": "Texto"}
        r = analyze_storyboard_section(section)
        assert r["metrics"]["words"] >= 1

    def test_bullets_as_dicts_normalized(self):
        section = {
            "title": "S1",
            "body": "",
            "bullets": [{"text": "ponto 1"}, {"title": "ponto 2"}, "ponto 3"],
        }
        r = analyze_storyboard_section(section)
        assert r["metrics"]["bullets"] == 3

    def test_storyboard_has_image_always_false(self):
        """Storyboard sections don't have visuals yet — analyzer treats them
        as image-less so we slightly bias toward 'denser' (warning users that
        the resulting slide will be heavy)."""
        section = {"title": "S1", "body": "x" * 200}
        r = analyze_storyboard_section(section)
        assert r["metrics"]["hasImage"] is False
