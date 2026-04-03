"""Pydantic models for cross-link suggestions."""

from pydantic import BaseModel, Field


class PostSummary(BaseModel):
    title: str
    series_slug: str | None = None
    main_topic: str = Field(description="One-sentence description of what the post teaches")
    key_concepts: list[str] = Field(description="3-5 short concept names covered in this post")
    audience_stage: str = Field(description="beginner | intermediate | advanced")


class LinkSuggestion(BaseModel):
    target_slug: str = Field(description="Slug of the post to link to")
    anchor_text: str = Field(description="The specific phrase from the post content to use as anchor text for the link")
    context_phrase: str = Field(description="The full sentence containing the anchor text to ensure unique replacement")
    placement: str = Field(description="intro | body | closing")
    reason: str = Field(description="One sentence explaining why this link adds value")


class DraftLinkSuggestion(BaseModel):
    target_slug: str = Field(description="Slug of the post to link to")
    suggested_anchor_text: str = Field(description="1-5 words from the paragraph to use as anchor text")
    placement_hint: str = Field(description="Brief note on where to insert the link")
