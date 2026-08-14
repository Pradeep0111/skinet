import asyncio
import re
from collections.abc import Sequence
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.models import AssistantProduct, ChatResponse, ProductComparison, ProposedAction
from app.tools import CatalogTools, InsufficientStockError

AgentIntent = Literal[
    "search",
    "details",
    "stock",
    "compare",
    "substitute",
    "propose_add",
    "clarify",
]

_CONTEXT_ORDINALS = {
    "first": 0,
    "1st": 0,
    "second": 1,
    "2nd": 1,
    "third": 2,
    "3rd": 2,
    "fourth": 3,
    "4th": 3,
    "fifth": 4,
    "5th": 4,
    "sixth": 5,
    "6th": 5,
    "seventh": 6,
    "7th": 6,
    "eighth": 7,
    "8th": 7,
    "ninth": 8,
    "9th": 8,
    "tenth": 9,
    "10th": 9,
    "last": -1,
}
_CONTEXT_REFERENCE_PATTERN = re.compile(
    r"\b(?:these|those|them|both)\b|"
    r"\b(?:this|that|the)\s+(?:one|ones|products?|items?|results?|options?)\b|"
    r"\b(?:first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|"
    r"sixth|6th|seventh|7th|eighth|8th|ninth|9th|tenth|10th|last)"
    r"\s+(?:one|ones|products?|items?|results?|options?)\b",
    re.I,
)
_CONTEXT_ORDINAL_PATTERN = re.compile(
    r"\b(?:first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|"
    r"sixth|6th|seventh|7th|eighth|8th|ninth|9th|tenth|10th|last)\b",
    re.I,
)


class ShoppingAgentState(TypedDict, total=False):
    message: str
    conversation_id: str
    context_product_ids: list[int]
    intent: AgentIntent
    query: str
    product_ids: list[int]
    quantity: int
    clarification: str
    response_message: str
    products: list[AssistantProduct]
    comparisons: list[ProductComparison]
    proposed_actions: list[ProposedAction]
    suggested_prompts: list[str]


class ShoppingAgent:
    """Deterministic LangGraph workflow over an explicit read-only tool allowlist."""

    def __init__(self, tools: CatalogTools) -> None:
        self._tools = tools
        builder = StateGraph(ShoppingAgentState)
        builder.add_node("route", self._route)
        builder.add_node("search", self._search)
        builder.add_node("details", self._details)
        builder.add_node("stock", self._stock)
        builder.add_node("compare", self._compare)
        builder.add_node("substitute", self._substitute)
        builder.add_node("propose_add", self._propose_add)
        builder.add_node("clarify", self._clarify)
        builder.add_edge(START, "route")
        builder.add_conditional_edges(
            "route",
            self._selected_intent,
            {
                "search": "search",
                "details": "details",
                "stock": "stock",
                "compare": "compare",
                "substitute": "substitute",
                "propose_add": "propose_add",
                "clarify": "clarify",
            },
        )
        for node in (
            "search",
            "details",
            "stock",
            "compare",
            "substitute",
            "propose_add",
            "clarify",
        ):
            builder.add_edge(node, END)
        self.graph = builder.compile()

    async def run(
        self,
        *,
        message: str,
        conversation_id: str,
        context_product_ids: Sequence[int] = (),
    ) -> ChatResponse:
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("message cannot be empty")
        if not conversation_id.strip():
            raise ValueError("conversation_id cannot be empty")
        normalized_context = self._normalize_context_product_ids(context_product_ids)

        result = await self.graph.ainvoke(
            {
                "message": normalized_message,
                "conversation_id": conversation_id,
                "context_product_ids": normalized_context,
                "products": [],
                "comparisons": [],
                "proposed_actions": [],
                "suggested_prompts": [],
            }
        )
        return ChatResponse(
            conversation_id=conversation_id,
            message=result["response_message"],
            products=result.get("products", []),
            comparisons=result.get("comparisons", []),
            proposed_actions=result.get("proposed_actions", []),
            suggested_prompts=result.get("suggested_prompts", []),
        )

    def _route(self, state: ShoppingAgentState) -> ShoppingAgentState:
        message = state["message"]
        explicit_product_ids = self._extract_product_ids(message)
        has_context_reference = self._has_context_reference(message)
        product_ids = explicit_product_ids
        if not product_ids and has_context_reference:
            product_ids = self._resolve_contextual_product_ids(
                message,
                state.get("context_product_ids", []),
            )
        quantity = self._extract_quantity(message)
        query = self._extract_search_query(message)
        clarification: str | None = None

        if not 1 <= quantity <= 99:
            return {
                "intent": "clarify",
                "product_ids": product_ids[:4],
                "quantity": quantity,
                "query": query,
                "clarification": "Quantity must be between 1 and 99.",
            }

        if re.search(r"\b(?:compare|comparison)\b", message, re.I):
            if 2 <= len(product_ids) <= 4:
                intent: AgentIntent = "compare"
            else:
                intent = "clarify"
                clarification = "Please choose between two and four product IDs to compare."
        elif re.search(r"\b(?:substitutes?|alternatives?|similar)\b", message, re.I):
            if len(product_ids) == 1:
                intent = "substitute"
            else:
                intent = "clarify"
                clarification = "Please choose exactly one product ID for alternatives."
        elif re.search(r"\badd\b", message, re.I) and (
            re.search(r"\bcart\b", message, re.I)
            or explicit_product_ids
            or has_context_reference
        ):
            if len(product_ids) == 1:
                intent = "propose_add"
            else:
                intent = "clarify"
                clarification = "Please choose exactly one product ID to add to the cart."
        elif re.search(
            r"\b(?:stock|available|availability|unavailable)\b",
            message,
            re.I,
        ):
            if len(product_ids) == 1:
                intent = "stock"
            else:
                intent = "clarify"
                clarification = "Please choose exactly one product ID for a stock check."
        elif re.search(r"\bdetails?\b|\btell me about\b", message, re.I):
            if len(product_ids) == 1:
                intent = "details"
            else:
                intent = "clarify"
                clarification = "Please choose exactly one product ID for details."
        elif has_context_reference:
            if len(product_ids) == 1:
                intent = "details"
            else:
                intent = "clarify"
                clarification = "Please choose exactly one product from the previous results."
        else:
            intent = "search"

        result: ShoppingAgentState = {
            "intent": intent,
            "product_ids": product_ids[:4],
            "quantity": quantity,
            "query": query,
        }
        if clarification:
            result["clarification"] = clarification
        return result

    @staticmethod
    def _selected_intent(state: ShoppingAgentState) -> AgentIntent:
        return state["intent"]

    async def _search(self, state: ShoppingAgentState) -> ShoppingAgentState:
        products = await self._tools.search_products(state["query"], limit=10)
        if products:
            message = f"I found {len(products)} matching product(s)."
        else:
            message = "I could not find a matching in-stock product."
        if len(products) >= 2:
            suggested_prompts = [
                f"Compare product {products[0].id} and product {products[1].id}"
            ]
        elif products:
            suggested_prompts = [f"Tell me about product {products[0].id}"]
        else:
            suggested_prompts = ["Try a different product name"]
        return {
            "response_message": message,
            "products": products,
            "suggested_prompts": suggested_prompts,
        }

    async def _details(self, state: ShoppingAgentState) -> ShoppingAgentState:
        product = await self._tools.get_product_details(state["product_ids"][0])
        return {
            "response_message": f"Here are the current details for {product.name}.",
            "products": [product],
            "suggested_prompts": [f"Check stock for product {product.id}"],
        }

    async def _stock(self, state: ShoppingAgentState) -> ShoppingAgentState:
        product_id = state["product_ids"][0]
        product, stock = await asyncio.gather(
            self._tools.get_product_details(product_id),
            self._tools.check_stock(product_id, requested_quantity=state["quantity"]),
        )
        availability = "available" if stock.available else "not available"
        return {
            "response_message": (
                f"{product.name} is {availability} for quantity {stock.requested_quantity}; "
                f"current stock is {stock.quantity_in_stock}."
            ),
            "products": [product],
            "suggested_prompts": [f"Show alternatives to product {product.id}"],
        }

    async def _compare(self, state: ShoppingAgentState) -> ShoppingAgentState:
        products, comparison = await self._tools.compare_products(
            tuple(state["product_ids"])
        )
        return {
            "response_message": "Here is a current catalog comparison.",
            "products": products,
            "comparisons": [comparison],
            "suggested_prompts": [f"Show alternatives to product {products[0].id}"],
        }

    async def _substitute(self, state: ShoppingAgentState) -> ShoppingAgentState:
        product_id = state["product_ids"][0]
        products = await self._tools.find_substitutes(product_id)
        message = (
            f"I found {len(products)} in-stock substitute(s)."
            if products
            else "I could not find an in-stock substitute in the same group."
        )
        return {
            "response_message": message,
            "products": products,
            "suggested_prompts": ["Search for another product"],
        }

    async def _propose_add(self, state: ShoppingAgentState) -> ShoppingAgentState:
        try:
            product, action = await self._tools.propose_add_to_cart(
                state["product_ids"][0],
                quantity=state["quantity"],
            )
        except InsufficientStockError as exc:
            return {
                "response_message": str(exc),
                "suggested_prompts": ["Show me an alternative"],
            }
        return {
            "response_message": (
                "Review this proposed action and confirm it in the website before anything "
                "is added to your cart."
            ),
            "products": [product],
            "proposed_actions": [action],
            "suggested_prompts": [f"Check stock for product {product.id}"],
        }

    @staticmethod
    def _clarify(state: ShoppingAgentState) -> ShoppingAgentState:
        message = state.get(
            "clarification",
            "Please include between one and four product IDs needed for that request.",
        )
        return {
            "response_message": message,
            "suggested_prompts": ["Show me boots"],
        }

    @staticmethod
    def _extract_product_ids(message: str) -> list[int]:
        explicit_ids = [
            int(value)
            for value in re.findall(
                r"\b(?:product|item)\s*#?\s*([1-9]\d*)(?![\d.])",
                message,
                re.I,
            )
        ]
        return list(dict.fromkeys(explicit_ids))

    @staticmethod
    def _extract_quantity(message: str) -> int:
        number = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
        match = re.search(
            rf"\b(?:quantity|qty)\b\s*[:=]?\s*({number})",
            message,
            re.I,
        )
        if match:
            return int(match.group(1)) if match.group(1).isdigit() else 0
        match = re.search(
            rf"\badd\s+({number})\s+(?:of\s+)?(?:product|item)\b",
            message,
            re.I,
        )
        if match:
            return int(match.group(1)) if match.group(1).isdigit() else 0
        match = re.search(
            rf"\badd\s+({number})\s+(?:of\s+)?(?:the\s+)?"
            r"(?:this|that|it|these|those|first|1st|second|2nd|third|3rd|"
            r"fourth|4th|fifth|5th|sixth|6th|seventh|7th|eighth|8th|"
            r"ninth|9th|tenth|10th|last|one|ones)\b",
            message,
            re.I,
        )
        if match:
            return int(match.group(1)) if match.group(1).isdigit() else 0
        return 1

    @staticmethod
    def _normalize_context_product_ids(product_ids: Sequence[int]) -> list[int]:
        if len(product_ids) > 10:
            raise ValueError("context_product_ids cannot exceed 10 products")
        normalized: list[int] = []
        for product_id in product_ids:
            if type(product_id) is not int or product_id <= 0:
                raise ValueError("context_product_ids must contain positive integers")
            if product_id not in normalized:
                normalized.append(product_id)
        return normalized

    @staticmethod
    def _has_context_reference(message: str) -> bool:
        if _CONTEXT_REFERENCE_PATTERN.search(message):
            return True
        return bool(
            re.search(r"\b(?:it|this|that)\b", message, re.I)
            and re.search(
                r"\b(?:add|compare|stock|available|availability|unavailable|"
                r"substitutes?|alternatives?|similar|details?)\b|\btell me about\b",
                message,
                re.I,
            )
        )

    @staticmethod
    def _resolve_contextual_product_ids(
        message: str,
        context_product_ids: Sequence[int],
    ) -> list[int]:
        if not context_product_ids:
            return []

        ordinal_matches = _CONTEXT_ORDINAL_PATTERN.findall(message)
        if ordinal_matches:
            resolved: list[int] = []
            for value in ordinal_matches:
                index = _CONTEXT_ORDINALS[value.casefold()]
                if index == -1:
                    product_id = context_product_ids[-1]
                elif index >= len(context_product_ids):
                    return []
                else:
                    product_id = context_product_ids[index]
                if product_id not in resolved:
                    resolved.append(product_id)
            return resolved

        if re.search(r"\b(?:these|those|them|both)\b", message, re.I):
            return list(context_product_ids)
        if len(context_product_ids) == 1 and re.search(
            r"\b(?:this|that|it|one)\b",
            message,
            re.I,
        ):
            return list(context_product_ids)
        return []

    @staticmethod
    def _extract_search_query(message: str) -> str:
        query = re.sub(
            r"^\s*(?:please\s+)?(?:show|find|search(?:\s+for)?|recommend|i\s+need)\s+",
            "",
            message,
            flags=re.I,
        )
        query = re.sub(r"^me\s+", "", query, flags=re.I).strip(" .?!")
        return query or message.strip()
