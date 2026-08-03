from __future__ import annotations

import json

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Conversation,
    Membership,
    Message,
    ModelConfiguration,
    Organization,
    OrganizationModelPolicy,
    Prompt,
    PromptFavorite,
    PromptVersion,
    User,
    UserSettings,
)
from .model_catalog import DEFAULT_MODEL_ID, LEGACY_MODEL_MAP, MODEL_CATALOG, MODEL_IDS, PRO_MODEL_ID


async def sync_model_catalog(db: AsyncSession) -> None:
    existing = {row.id: row for row in (await db.scalars(select(ModelConfiguration))).all()}
    for item in MODEL_CATALOG:
        row = existing.get(item["id"])
        if row:
            row.display_name = item["display_name"]
            row.supports_effort = item["supports_effort"]
            row.supports_files = item["supports_files"]
            row.enabled = True
        else:
            db.add(ModelConfiguration(**item))

    for legacy_id, replacement_id in LEGACY_MODEL_MAP.items():
        await db.execute(update(Conversation).where(Conversation.model == legacy_id).values(model=replacement_id))
        await db.execute(update(UserSettings).where(UserSettings.default_model == legacy_id).values(default_model=replacement_id))

    policies = (await db.scalars(select(OrganizationModelPolicy))).all()
    for policy in policies:
        policy.default_model = LEGACY_MODEL_MAP.get(policy.default_model, policy.default_model)
        if policy.default_model not in MODEL_IDS:
            policy.default_model = DEFAULT_MODEL_ID
        policy.allowed_models_json = json.dumps([item["id"] for item in MODEL_CATALOG])

    await db.execute(delete(ModelConfiguration).where(ModelConfiguration.id.in_(LEGACY_MODEL_MAP)))
    await db.commit()


async def seed_development_data(db: AsyncSession) -> None:
    if await db.scalar(select(User.id).limit(1)):
        await sync_model_catalog(db)
        return

    user = User(id="user-ayman", email="ayman@northstaradvisory.com", display_name="Ayman")
    maya = User(id="user-maya", email="maya@northstaradvisory.com", display_name="Maya Chen")
    jon = User(id="user-jon", email="jon@northstaradvisory.com", display_name="Jon Bell")
    priya = User(id="user-priya", email="priya@northstaradvisory.com", display_name="Priya Shah")
    org = Organization(id="org-northstar", name="Northstar Advisory", slug="northstar-advisory")
    db.add_all([
        user,
        maya,
        jon,
        priya,
        org,
        Membership(id="membership-ayman", organization_id=org.id, user_id=user.id, role="owner"),
        Membership(id="membership-maya", organization_id=org.id, user_id=maya.id, role="admin"),
        Membership(id="membership-jon", organization_id=org.id, user_id=jon.id, role="member"),
        UserSettings(organization_id=org.id, user_id=user.id, custom_instructions="Write for a business audience and make next actions explicit.", web_search_default=True),
        *(ModelConfiguration(**item) for item in MODEL_CATALOG),
        OrganizationModelPolicy(organization_id=org.id, allowed_models_json=json.dumps([item["id"] for item in MODEL_CATALOG]), default_model=DEFAULT_MODEL_ID, maximum_effort="high"),
    ])

    conversation = Conversation(id="conversation-quarterly", organization_id=org.id, user_id=user.id, title="Quarterly planning brief", model=PRO_MODEL_ID, effort="high", pinned=True)
    db.add(conversation)
    db.add_all([
        Message(organization_id=org.id, user_id=user.id, conversation_id=conversation.id, role="user", content="Summarize the top three priorities for Q3 from our operating plan."),
        Message(organization_id=org.id, user_id=user.id, conversation_id=conversation.id, role="assistant", content="### Q3 priorities\n\n1. **Drive revenue growth in core segments.** Focus investment on the strongest professional-services and technology-advisory opportunities.\n2. **Improve operating efficiency.** Standardize repeatable workflows and make ownership visible.\n3. **Strengthen risk and compliance.** Tighten vendor oversight and data-governance readiness."),
    ])

    prompt_specs = [
        ("Executive summary", "Turn a long business document into a concise leadership brief.", "Act as a strategy advisor. Review the material for {{company_name}} during {{reporting_period}} and create a concise executive summary for senior leaders. Highlight trends, risks, opportunities, and recommendations.", ["Strategy", "Leadership"]),
        ("Competitor analysis", "Compare competitors using a consistent decision framework.", "Analyze the named competitors across positioning, strengths, weaknesses, pricing, and strategic risk. End with three recommended moves.", ["Research"]),
        ("Meeting follow-up", "Convert meeting notes into decisions and accountable actions.", "Turn these meeting notes into decisions, open questions, action items, owners, and deadlines.", ["Operations"]),
        ("Risk register review", "Challenge a risk register and identify missing controls.", "Review the risk register. Flag material gaps, ambiguous owners, weak controls, and overdue mitigations. Prioritize the top five changes.", ["Risk"]),
    ]
    for index, (title, description, body, tags) in enumerate(prompt_specs, start=1):
        prompt = Prompt(id=f"prompt-{index}", organization_id=org.id, title=title, description=description, body=body, tags_json=json.dumps(tags), creator_id=user.id, last_editor_id=user.id)
        db.add(prompt)
        db.add(PromptVersion(organization_id=org.id, prompt_id=prompt.id, version_number=1, title=title, description=description, body=body, tags_json=json.dumps(tags), edited_by=user.id))
        if index == 1:
            db.add(PromptFavorite(organization_id=org.id, prompt_id=prompt.id, user_id=user.id))
    await db.commit()
