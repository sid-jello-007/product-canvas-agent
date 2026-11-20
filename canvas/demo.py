"""Canned outputs for demo mode and tests.

Demo mode lets anyone click through the app without an API key. The sample
deliberately contains one weak story (E2-S2) so the critic and refine loop
have something to fix, which shows the self-correction step working.
"""
import re

from .schemas import Critique, ProductCanvas, ProductSpec, RefinedStories, Story, StoryReview, TicketPlan

CANVAS = {
    "product_name": "SplitEasy",
    "one_line_pitch": "Shared household bills split fairly and settled automatically.",
    "problem": "Flatmates track shared bills in chats and spreadsheets, so payments are late and someone always ends up out of pocket.",
    "target_users": [
        {"name": "Flat organiser", "needs": "One place to log bills and see who owes what without chasing people."},
        {"name": "Busy flatmate", "needs": "A reminder and a one tap way to pay their share."},
    ],
    "jobs_to_be_done": [
        "Record a shared bill in under a minute",
        "Know exactly what I owe this month",
        "Settle up without awkward conversations",
    ],
    "value_proposition": "Fair splits, automatic reminders and one tap settlement replace spreadsheets and chasing.",
    "key_features": ["Household groups", "Bill capture with custom splits", "Balances view", "Payment reminders", "Settle up via bank transfer link"],
    "success_metrics": [
        {"name": "Weekly active households", "target": "1,000 within 3 months of launch", "why": "Shows the habit is forming"},
        {"name": "Bills settled within 7 days", "target": "80%", "why": "Measures the core promise of fewer late payments"},
    ],
    "assumptions_and_risks": ["Users will invite flatmates in the first session", "Open banking payment links are available in launch markets"],
    "out_of_scope": ["Holding customer funds", "Credit or lending"],
    "open_questions": ["Do we support recurring bills at launch?", "Which payment provider for settlement links?"],
}

SPEC = {
    "overview": "SplitEasy lets a household log shared bills, splits them fairly and nudges each member to settle.",
    "goals": ["Cut late shared payments", "Make the monthly balance obvious to every member"],
    "non_goals": ["Storing money in the app", "Personal budgeting"],
    "requirements": [
        {"id": "FR-1", "title": "Create a household", "description": "A user can create a household and invite members by link.", "priority": "Must"},
        {"id": "FR-2", "title": "Add a bill", "description": "A member can add a bill with amount, payer and split method.", "priority": "Must"},
        {"id": "FR-3", "title": "View balances", "description": "Each member sees who owes whom after netting all bills.", "priority": "Must"},
        {"id": "FR-4", "title": "Reminders", "description": "Members who owe money get a reminder after 3 days.", "priority": "Should"},
        {"id": "FR-5", "title": "Settle up", "description": "A member can open a bank transfer link prefilled with the amount owed.", "priority": "Could"},
    ],
    "non_functional_requirements": ["Balances update within 2 seconds of a change", "GDPR compliant data handling"],
    "user_flows": ["Organiser creates household, invites flatmates, adds first bill", "Flatmate gets reminder, opens balance, settles"],
}

TICKETS = {
    "epics": [
        {"key": "E1", "title": "Households", "summary": "Create and join a household.", "stories": [
            {"key": "E1-S1", "title": "Create a household", "user_story": "As a flat organiser, I want to create a household, so that I can group our shared bills.",
             "acceptance_criteria": ["Given I am signed in, when I enter a household name and confirm, then the household is created and I am its admin.",
                                     "Given the name is empty, when I confirm, then I see a validation message."],
             "story_points": 3, "priority": "Highest", "requirement_ids": ["FR-1"], "labels": ["households"], "dependencies": []},
            {"key": "E1-S2", "title": "Invite members by link", "user_story": "As a flat organiser, I want to share an invite link, so that flatmates can join quickly.",
             "acceptance_criteria": ["Given I am an admin, when I tap invite, then a unique link is generated and copied.",
                                     "Given a flatmate opens a valid link, when they sign in, then they join the household."],
             "story_points": 5, "priority": "High", "requirement_ids": ["FR-1"], "labels": ["households", "growth"], "dependencies": ["E1-S1"]},
        ]},
        {"key": "E2", "title": "Bills and balances", "summary": "Capture bills and show who owes what.", "stories": [
            {"key": "E2-S1", "title": "Add a bill with a split", "user_story": "As a flatmate, I want to add a bill and choose how to split it, so that costs are shared fairly.",
             "acceptance_criteria": ["Given I am in a household, when I add an amount, payer and equal split, then each member's share is calculated.",
                                     "Given I choose a custom split, when shares do not add up to the total, then I cannot save."],
             "story_points": 5, "priority": "Highest", "requirement_ids": ["FR-2"], "labels": ["bills"], "dependencies": ["E1-S1"]},
            {"key": "E2-S2", "title": "Balances", "user_story": "Balances screen.",
             "acceptance_criteria": ["Shows balances."],
             "story_points": 4, "priority": "High", "requirement_ids": [], "labels": ["bills"], "dependencies": ["E2-S1"]},
        ]},
        {"key": "E3", "title": "Nudges and settlement", "summary": "Remind and settle.", "stories": [
            {"key": "E3-S1", "title": "Reminder after 3 days", "user_story": "As a flat organiser, I want members who owe money to be reminded, so that I do not have to chase them.",
             "acceptance_criteria": ["Given a member has owed money for 3 days, when the daily job runs, then they receive one push reminder.",
                                     "Given the member has settled, when the job runs, then no reminder is sent."],
             "story_points": 3, "priority": "Medium", "requirement_ids": ["FR-4"], "labels": ["notifications"], "dependencies": ["E2-S1"]},
        ]},
    ]
}

FIXED_E2_S2 = {
    "key": "E2-S2", "title": "View net balances", "user_story": "As a flatmate, I want to see who owes whom after all bills are netted, so that I know exactly what to pay.",
    "acceptance_criteria": ["Given bills exist in my household, when I open Balances, then I see each member's net position.",
                            "Given a bill is added or edited, when I return to Balances, then totals update within 2 seconds."],
    "story_points": 3, "priority": "High", "requirement_ids": ["FR-3"], "labels": ["bills"], "dependencies": ["E2-S1"],
}


def respond(schema, user_prompt: str):
    if schema is ProductCanvas:
        return ProductCanvas.model_validate(CANVAS)
    if schema is ProductSpec:
        return ProductSpec.model_validate(SPEC)
    if schema is TicketPlan:
        return TicketPlan.model_validate(TICKETS)
    if schema is Critique:
        keys = list(dict.fromkeys(re.findall(r'"key":\s*"(E\d+-S\d+)"', user_prompt)))
        reviews = [
            StoryReview(key=k, score=2, issues=["User story is not in 'As a..., I want..., so that...' form", "Acceptance criteria are not testable", "No linked requirement"])
            if k == "E2-S2" and '"title": "Balances"' in user_prompt else StoryReview(key=k, score=4, issues=[])
            for k in keys
        ]
        return Critique(reviews=reviews, overall_comment="Most stories are well formed; fix the weak ones.")
    if schema is RefinedStories:
        keys = re.findall(r'"key":\s*"(E\d+-S\d+)"', user_prompt)
        stories = [Story.model_validate(FIXED_E2_S2)] if "E2-S2" in keys else []
        return RefinedStories(stories=stories)
    raise ValueError(f"No demo response for {schema.__name__}")
