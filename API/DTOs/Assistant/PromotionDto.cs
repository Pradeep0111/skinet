namespace API.DTOs.Assistant
{
    public class PromotionDto
    {
        public decimal SalePrice { get; set; }
        public string? Label { get; set; }
        public DateTime? StartDate { get; set; }
        public DateTime? EndDate { get; set; }
        public bool IsActive { get; set; }
    }
}
