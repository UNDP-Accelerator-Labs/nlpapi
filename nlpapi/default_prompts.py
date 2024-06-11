def replacer(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace(f"<{key}>", value)
    return text.strip()


RATING_PROMPT = """
"""

CATEGORIES = {
    "institutional": (
        "Institutional (system integration):\nFrom mapping litter to a "
        "circular economy portfolio"),
    "legal": (
        "Legal (Reducing plastic waste):\nTransforming informal "
        "waste-centered businesses to a recycling industry"),
    "technological": (
        "Technological (Data and Knowledge):\nGeo-referenced knowledge base "
        "and pilots"),
    "economic": (
        "Economic (waste to livelihoods):\nPrototyping products from "
        "recycled waste"),
    "political": (
        "Political (Reducing food waste):\nPreventing or upcycling "
        "food waste"),
    "cultural": (
        "Social/Cultural (Responsible consumption):\nChanging public demand "
        "for less packaging"),
    "educational": (
        "Educational (BI & Citizen Science):\nDriving responsible "
        "consumption"),
}


VERIFY_PROMPT = """
You are a knowledgeable assistant that decides whether the content that the
user provides to you talks about <topic>.

<topic_definition>

You only respond with a short (50 - 100 words) justification for your decicion
and after that with a single `yes` or `no` on its own line.
"""

CIRCULAR_ECONOMY_DEFINITION = """
Circular economy is a concept that aims to reduce waste and the consumption of
resources by promoting the reuse, recycling, and upcycling of products and
materials. It's an alternative to the traditional linear economy, where
resources are extracted, used, and then discarded.

In a circular economy, the goal is to design products and systems that are
restorative and regenerative by design. This means designing products that can
be easily disassembled, recycled, or upcycled at the end of their life cycle,
reducing waste and the need for new raw materials. The idea is to close the
loops of production and consumption, keeping resources in use for as long as
possible, and recovering materials from products that are no longer needed.
This approach can help reduce greenhouse gas emissions, conserve natural
resources, and mitigate climate change.

For example, a company might design a product with modular components that can
be easily replaced or updated, reducing electronic waste and the need for new
raw materials. Or, they might develop a business model where products are
designed to be recycled or upcycled at the end of their life cycle, rather than
being discarded in landfills.

Circular economy is still an evolving concept, but it has the potential to
transform the way we produce, consume, and interact with goods and services.
"""

VERIFY_CIRCULAR_ECONOMY = replacer(
    VERIFY_PROMPT,
    {
        "topic": "circular economy",
        "topic_definition": CIRCULAR_ECONOMY_DEFINITION,
    })


SYSTEM_PROMPTS: dict[str, str] = {
    "verify_circular_economy": VERIFY_CIRCULAR_ECONOMY,
}
