namespace API.DTOs.Assistant
{
    public sealed class PromotionDto
    {
        public decimal SalePrice { get; set; }
        public required string Label { get; set; }
        public DateTimeOffset? StartsAt { get; set; }
        public DateTimeOffset? EndsAt { get; set; }
    }
}
