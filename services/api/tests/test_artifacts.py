import zipfile

from app.artifacts import ArtifactBlock, ArtifactPage, ArtifactSpec, render_pptx


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
