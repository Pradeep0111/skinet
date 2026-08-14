namespace API.Services.Assistant;

public sealed class AssistantChatRequest
{
    public required string Message { get; set; }
    public required string ConversationId { get; set; }
    public AssistantCartContext Cart { get; set; } = new();
    public AssistantShopperContext Shopper { get; set; } = new();
}

public sealed class AssistantCartContext
{
    public List<CartItemContext> Items { get; set; } = [];
}

public sealed class CartItemContext
{
    public int ProductId { get; set; }
    public int Quantity { get; set; }
}

public sealed class AssistantShopperContext
{
    public bool IsAuthenticated { get; set; }
    public List<ProductPreferenceContext> Preferences { get; set; } = [];
}

public sealed class ProductPreferenceContext
{
    public int ProductId { get; set; }
    public int PurchaseCount { get; set; }
    public DateTimeOffset? LastPurchasedAt { get; set; }
}