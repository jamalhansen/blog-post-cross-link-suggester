"""LLM prompt builders for cross-link suggestion."""

SUMMARY_SYSTEM = """You are a technical blog post analyst. Extract structured metadata from this blog post.

Return ONLY a JSON object with these fields:
- title: the post title (string)
- main_topic: one-sentence description of what the post teaches (string)
- key_concepts: 3-5 short concept names covered in this post (array of strings)
- audience_stage: the target level — "beginner", "intermediate", or "advanced" (string)"""


AUDIT_SYSTEM = """You are a technical editor finding internal linking opportunities in a blog series.

Given a target post and summaries of other posts in the series, identify 2-4 posts the target should link to.

Return ONLY a JSON array where each item has:
- target_slug: slug of the post to link to (string)
- placement: where in the post the link fits — "intro", "body", or "closing" (string)
- reason: one sentence explaining why this link adds value (string)

Rules:
- Do not suggest linking to the post itself.
- Only suggest posts that are genuinely relevant, not just tangentially related.
- Return an empty array [] if no strong opportunities exist."""


DRAFT_SYSTEM = """You are a technical editor suggesting internal links for a blog post in a series.

Given a paragraph from a draft and summaries of published posts, suggest which published posts this paragraph should link to.

Return ONLY a JSON array (empty [] if no good matches) where each item has:
- target_slug: slug of the post to link to (string)
- suggested_anchor_text: 1-5 words from the paragraph that would be the link text (string)
- placement_hint: brief note on exactly where in the paragraph to place the link (string)"""


def build_summary_prompt(content: str) -> str:
    """Build the user prompt for post summarization. Cap at 4000 chars."""
    return content[:4000]


def build_audit_prompt(
    target_slug: str,
    target_title: str,
    target_content: str,
    all_summaries: list[dict],
) -> str:
    """Build the user prompt for finding cross-link opportunities."""
    other_posts = "\n".join(
        f"- {s['slug']}: {s['title']} — {s['main_topic']}"
        f" (concepts: {', '.join(s['key_concepts'][:3])})"
        for s in all_summaries
        if s["slug"] != target_slug
    )
    return (
        f"Target post: {target_title} (slug: {target_slug})\n\n"
        f"Post opening:\n{target_content[:800]}\n\n"
        f"Other posts in the series:\n{other_posts}"
    )


def build_draft_prompt(paragraph: str, all_summaries: list[dict]) -> str:
    """Build the user prompt for suggesting links in a draft paragraph."""
    posts_list = "\n".join(
        f"- {s['slug']}: {s['title']} — {s['main_topic']}"
        f" (concepts: {', '.join(s['key_concepts'][:3])})"
        for s in all_summaries
    )
    return (
        f"Draft paragraph:\n{paragraph}\n\n"
        f"Published posts in the series:\n{posts_list}"
    )
