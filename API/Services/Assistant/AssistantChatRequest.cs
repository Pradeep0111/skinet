namespace API.Services.Assistant;

public class AssistantChatRequest
{
    public string Message { get; set; } = string.Empty;
    public string ConversationId { get; set; } = string.Empty;
    public List<CartItemContext> CartItems { get; set; } = [];
    public List<PurchaseHistoryContext> PurchaseHistory { get; set; } = [];
}

public class CartItemContext
{
    public int ProductId { get; set; }
    public int Quantity { get; set; }
}

public class PurchaseHistoryContext
{
    public int ProductId { get; set; }
    public int TotalQuantity { get; set; }
    public int PurchaseCount { get; set; }
    public DateTime LastPurchased { get; set; }
}