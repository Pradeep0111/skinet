namespace API.DTOs.Assistant
{
    public sealed class ProposedActionDto
    {
        public string ActionId { get; set; } = string.Empty;
        public string ActionType { get; set; } = string.Empty;
        public int ProductId { get; set; }
        public int Quantity { get; set; }
        public string Label { get; set; } = string.Empty;
        public bool RequiresConfirmation { get; set; }
    }

}