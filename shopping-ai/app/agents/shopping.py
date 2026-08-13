import asyncio
import re
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


class ShoppingAgentState(TypedDict, total=False):
    message: str
    conversation_id: str
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

    async def run(self, *, message: str, conversation_id: str) -> ChatResponse:
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("message cannot be empty")
        if not conversation_id.strip():
            raise ValueError("conversation_id cannot be empty")

        result = await self.graph.ainvoke(
            {
                "message": normalized_message,
                "conversation_id": conversation_id,
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
        lowered = message.casefold()
        product_ids = self._extract_product_ids(message)
        quantity = self._extract_quantity(message)
        query = self._extract_search_query(message)

        if not 1 <= quantity <= 99:
            return {
                "intent": "clarify",
                "product_ids": product_ids[:4],
                "quantity": quantity,
                "query": query,
                "clarification": "Quantity must be between 1 and 99.",
            }

        if "compare" in lowered:
            intent: AgentIntent = (
                "compare" if 2 <= len(product_ids) <= 4 else "clarify"
            )
        elif any(word in lowered for word in ("substitute", "alternative", "similar")):
            intent = "substitute" if product_ids else "clarify"
        elif any(word in lowered for word in ("stock", "available", "availability")):
            intent = "stock" if product_ids else "clarify"
        elif "add" in lowered and "cart" in lowered:
            intent = "propose_add" if product_ids else "clarify"
        elif any(phrase in lowered for phrase in ("details", "detail", "tell me about")):
            intent = "details" if product_ids else "clarify"
        else:
            intent = "search"

        return {
            "intent": intent,
            "product_ids": product_ids[:4],
            "quantity": quantity,
            "query": query,
        }

    @staticmethod
    def _selected_intent(state: ShoppingAgentState) -> AgentIntent:
        return state["intent"]

    async def _search(self, state: ShoppingAgentState) -> ShoppingAgentState:
        products = await self._tools.search_products(state["query"], limit=10)
        if products:
            message = f"I found {len(products)} matching product(s)."
        else:
            message = "I could not find a matching in-stock product."
        return {
            "response_message": message,
            "products": products,
            "suggested_prompts": ["Compare product 1 and product 2"],
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
            "suggested_prompts": ["Show me fresh fruit"],
        }

    @staticmethod
    def _extract_product_ids(message: str) -> list[int]:
        explicit_ids = [
            int(value)
            for value in re.findall(r"\b(?:product|item)\s*#?\s*(\d+)\b", message, re.I)
        ]
        if explicit_ids:
            return list(dict.fromkeys(explicit_ids))
        if "compare" in message.casefold():
            return list(
                dict.fromkeys(
                    int(value) for value in re.findall(r"\b([1-9]\d*)\b", message)
                )
            )
        return []

    @staticmethod
    def _extract_quantity(message: str) -> int:
        match = re.search(r"\b(?:quantity|qty)\s*[:=]?\s*(\d+)\b", message, re.I)
        if match:
            return int(match.group(1))
        match = re.search(r"\badd\s+(\d+)\s+(?:of\s+)?(?:product|item)\b", message, re.I)
        if match:
            return int(match.group(1))
        return 1

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
