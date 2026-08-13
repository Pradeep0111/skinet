namespace API.DTOs.Assistant
{
    public class ProposedActionDto
    {
        public string Type { get; set; } = string.Empty;
        public int ProductId { get; set; }
        public int Quantity { get; set; }
    }
}