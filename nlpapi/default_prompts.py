# NLP-API provides useful Natural Language Processing capabilities as API.
# Copyright (C) 2024 UNDP Accelerator Labs, Josua Krause
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
def replacer(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace(f"<{key}>", value)
    return text.strip()


BR_O = "{"
BR_C = "}"


EXAMPLE_RATE_0 = (
    "The article primarily talks about the political challenges of "
    "implementing circular economy in Panama. However, it also briefly "
    "discusses economical benefits and portraits a long term view that "
    "is rooted in education")


EXAMPLE_RATE_1 = (
    "The article discusses technical challenges of circular economies. "
    "It identifies institutions as driver of technological advancements "
    "of the topic. In addition to that, it also considers legal aspects "
    "or circular economies. It briefly mentions cultural hurdles.")


RATING_PROMPT = f"""
You are a knowledgeable assistant that rates articles about <topic> on how
much they focus on the given categories. The categories are:

<categories>

Your entire response is a JSON and nothing else. The JSON is an object with
several fields: "reason" which provides a short (50 - 100 words) justification
for your assessment and one numeric field for every category. The numbers
indicate the weight of each category in the article. 0 indicates no
mention at all, 1 indicates a brief acknowledgement, 2 indicates a minor
mention, 3 indicates a sub topic of the article, and 4 indicates a major topic
of the article.

## Examples

```
{BR_O}
    "reason": "{EXAMPLE_RATE_0}",
    "institutional": 0,
    "legal": 0,
    "technological": 0,
    "economic": 2,
    "political": 4,
    "cultural": 0,
    "educational": 2,
{BR_C}
```

```
{BR_O}
    "reason": "{EXAMPLE_RATE_1}",
    "institutional": 3,
    "legal": 3,
    "technological": 4,
    "economic": 0,
    "political": 0,
    "cultural": 1,
    "educational": 0,
{BR_C}
```
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


RATING_CIRCULAR_ECONOMY = replacer(
    RATING_PROMPT,
    {
        "topic": "circular economy",
        "categories": ", ".join(
            [f"'{cat}'" for cat in sorted(CATEGORIES.keys())]),
    })


EXAMPLE_VERIFY_0 = (
    "The article talks about circular economy as it discusses "
    "the concept of reducing waste, reusing, recycling, and upcycling "
    "products and materials. It also highlights the importance of "
    "designing products that can be easily disassembled, recycled, "
    "or upcycled at the end of their life cycle, which is a key "
    "principle of the circular economy.")

EXAMPLE_VERIFY_1 = (
    "The article does not discuss circular economy as it focuses "
    "on the socio-economic impact of COVID-19 on women-led micro, small, "
    "and medium enterprises (MSMEs) in Palestine, including their "
    "challenges, resilience, and potential solutions such as online "
    "platforms and e-payments.")


VERIFY_PROMPT = f"""
You are a knowledgeable assistant that decides whether the article that the
user provides to you talks about <topic>.

<topic_definition>

Your entire response is a JSON and nothing else. The JSON is an object with
two fields: "reason" which provides a short (50 - 100 words) justification for
your decision and "is_hit" which is a boolean value indicating your final
answer. You will be penalized for any text that is not in the JSON format.

## Examples

```
{BR_O}
    "reason": "{EXAMPLE_VERIFY_0}",
    "is_hit": true,
{BR_C}
```

```
{BR_O}
    "reason": "{EXAMPLE_VERIFY_1}",
    "is_hit": false,
{BR_C}
```
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
""".strip()

VERIFY_CIRCULAR_ECONOMY = replacer(
    VERIFY_PROMPT,
    {
        "topic": "circular economy",
        "topic_definition": CIRCULAR_ECONOMY_DEFINITION,
    })


SYSTEM_PROMPTS: dict[str, str] = {
    "verify_circular_economy": VERIFY_CIRCULAR_ECONOMY,
    "rate_circular_economy": RATING_CIRCULAR_ECONOMY,
}
