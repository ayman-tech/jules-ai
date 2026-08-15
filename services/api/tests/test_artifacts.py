import json
import zipfile
from types import SimpleNamespace

import httpx
import pytest

from app import artifacts as artifacts_module
from app import research as research_module
from app.artifacts import ArtifactBlock, ArtifactPage, ArtifactSpec, content_quality_issues, plan_artifact, render_docx, render_pptx
from app.research import ChartSeries, CitationStreamNormalizer, artifact_profile, build_evidence_registry, normalize_citations


def test_research_profile_and_unified_citation_normalization():
    request = "Prepare a complete market analysis for an ashwagandha company in North America."
    assert artifact_profile(request) == "deep-research"
    assert artifact_profile("Create a short meeting agenda") == "standard"

    normalized = normalize_citations(
        "Company policy [Company source 2]; market evidence [Web source 1] and [Web content 2].",
        company_count=2,
        web_count=2,
    )
    assert normalized.text == "Company policy [2]; market evidence [3] and [4]."
    assert normalized.invalid_markers == ()

    registry = build_evidence_registry(
        company_sources=[{"title": "Internal policy", "document_id": "doc-1"}],
        web_sources=[{"title": "Public research", "url": "https://example.com"}],
    )
    assert [(item.ordinal, item.source_type) for item in registry] == [(1, "company"), (2, "web")]

    stream = CitationStreamNormalizer(company_count=2, web_count=1)
    assert stream.feed("Evidence [Web ") == "Evidence "
    assert stream.feed("source 1] supports this.") == "[3] supports this."
    assert stream.flush() == ""


def test_deep_research_content_gate_rejects_shallow_market_overview():
    spec = ArtifactSpec(
        title="North American Ashwagandha Market",
        profile="deep-research",
        pages=[ArtifactPage(title="Overview", blocks=[ArtifactBlock(text="The market grew 12% [1].")])],
    )
    issues = content_quality_issues(
        spec,
        instructions="Prepare a complete market analysis for ashwagandha in North America",
        citations=({"ordinal": 1, "source_type": "web", "url": "https://example.com"},),
    )
    assert any("seven substantive sections" in issue for issue in issues)
    assert any("TAM/SAM/SOM" in issue for issue in issues)
    assert any("chart" in issue for issue in issues)


@pytest.mark.asyncio
async def test_deep_research_quality_issues_are_non_fatal_after_one_correction(monkeypatch):
    shallow = json.dumps({
        "title": "Ashwagandha market overview",
        "pages": [{"title": "Overview", "blocks": [{"text": "A directional estimate is available [99]."}]}],
    })

    class FakeModels:
        def __init__(self):
            self.calls = 0

        async def generate_content(self, **_kwargs):
            self.calls += 1
            return SimpleNamespace(text=shallow)

    fake_models = FakeModels()
    fake_client = SimpleNamespace(aio=SimpleNamespace(models=fake_models))
    monkeypatch.setattr(artifacts_module.settings, "google_api_key", "test-key")

    from google import genai
    monkeypatch.setattr(genai, "Client", lambda **_kwargs: fake_client)

    result = await plan_artifact(
        format_name="docx",
        model="gemini-test",
        effort="high",
        instructions="Create market research for an ashwagandha supplement",
        research_request=None,
        template_id="general-document",
        internal_context="",
        web_search_enabled=False,
        attachment_payloads=(),
        previous_spec=None,
    )

    assert fake_models.calls == 2
    assert result.profile == "deep-research"
    assert result.quality_retry_count == 1
    assert result.quality_issues
    assert result.invalid_citation_count == 1
    assert "[99]" not in result.spec.pages[0].blocks[0].text


@pytest.mark.asyncio
async def test_grounding_url_resolution_is_allowlisted_and_public(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def head(self, _url):
            if "vertexaisearch" in _url:
                return SimpleNamespace(status_code=302, headers={"location": "https://example.com/canonical"})
            return SimpleNamespace(status_code=200, headers={})

        async def get(self, _url, **_kwargs):
            raise AssertionError("GET fallback should not be needed")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    monkeypatch.setattr(research_module, "_host_is_public", lambda host: host == "example.com")
    grounding = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/example"
    assert await research_module.canonicalize_grounding_url(grounding) == "https://example.com/canonical"
    assert await research_module.canonicalize_grounding_url("https://example.org/direct") == "https://example.org/direct"

    class PrivateClient(FakeClient):
        async def head(self, _url):
            return SimpleNamespace(status_code=302, headers={"location": "http://127.0.0.1/private"})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: PrivateClient())
    assert await research_module.canonicalize_grounding_url(grounding) == grounding


def test_docx_renderer_adds_metadata_links_toc_chart_and_editable_data(tmp_path):
    destination = tmp_path / "research-report.docx"
    spec = ArtifactSpec(
        title="Market analysis",
        subtitle="Decision-ready brief",
        profile="deep-research",
        pages=[
            ArtifactPage(
                title="Market trajectory",
                blocks=[
                    ArtifactBlock(text="The estimate increases from 10 to 12 [1]."),
                    ArtifactBlock(
                        kind="chart",
                        heading="Illustrative market estimate",
                        chart_type="line",
                        categories=["2025", "2026"],
                        series=[ChartSeries(name="USD millions", values=[10, 12])],
                        unit="USD millions",
                        period="2025–2026",
                        alt_text="Line chart showing an increase from 10 to 12 million dollars.",
                        source_ordinals=[1],
                    ),
                ],
            )
        ],
    )
    render_docx(spec, destination, [{
        "ordinal": 1,
        "source_type": "web",
        "title": "Example market research",
        "publisher": "Example Publisher",
        "url": "https://example.com/research",
        "retrieved_at": "2026-08-10",
    }], version_number=3)

    with zipfile.ZipFile(destination) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        core_xml = archive.read("docProps/core.xml").decode("utf-8")
        relationships = archive.read("word/_rels/document.xml.rels").decode("utf-8")
        assert "Market analysis" in core_xml
        assert "Version 3" in document_xml
        assert "TOC" in document_xml
        assert "w:tblHeader" in document_xml
        assert "Line chart showing an increase" in document_xml
        assert "https://example.com/research" in relationships
        assert "Web source" not in document_xml
        assert any(name.startswith("word/media/") for name in archive.namelist())


def test_pptx_renderer_embeds_editable_content_and_source_notes(tmp_path):
    destination = tmp_path / "cited-deck.pptx"
    spec = ArtifactSpec(
        title="Quarterly plan",
        subtitle="Editable presentation",
        pages=[
            ArtifactPage(
                title="Priorities",
                blocks=[ArtifactBlock(kind="bullets", items=["Retain customers", "Improve activation"])],
                speaker_notes="Explain how the priorities connect to the annual plan.",
            )
        ],
    )
    citations = [
        {
            "ordinal": 1,
            "source_type": "web",
            "title": "Example research",
            "publisher": "Example Publisher",
            "url": "https://example.com/research",
        }
    ]

    render_pptx(spec, destination, {}, citations, tmp_path)

    with zipfile.ZipFile(destination) as archive:
        names = archive.namelist()
        assert "ppt/presentation.xml" in names
        assert len([name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")]) == 3
        note_names = [name for name in names if name.startswith("ppt/notesSlides/notesSlide") and name.endswith(".xml")]
        assert note_names
        note_text = "\n".join(archive.read(name).decode("utf-8") for name in note_names)
        assert "Example research" in note_text
        assert "https://example.com/research" in note_text
        relationships = "\n".join(archive.read(name).decode("utf-8") for name in names if name.startswith("ppt/slides/_rels/"))
        assert "https://example.com/research" in relationships


def test_pptx_renderer_supports_sourced_chart_blocks(tmp_path):
    destination = tmp_path / "chart-deck.pptx"
    spec = ArtifactSpec(
        title="Market trajectory",
        pages=[ArtifactPage(title="Forecast", blocks=[ArtifactBlock(
            kind="chart",
            chart_type="bar",
            categories=["2025", "2026"],
            series=[ChartSeries(name="USD millions", values=[10, 12])],
            unit="USD millions",
            period="2025–2026",
            source_ordinals=[1],
        )])],
    )
    render_pptx(spec, destination, {}, [{"ordinal": 1, "source_type": "web", "title": "Forecast", "url": "https://example.com"}], tmp_path)
    with zipfile.ZipFile(destination) as archive:
        assert any(name.startswith("ppt/charts/chart") and name.endswith(".xml") for name in archive.namelist())
        slide_text = archive.read("ppt/slides/slide2.xml").decode("utf-8")
        assert "Sources: [1]" in slide_text
