namespace API.DTOs.Assistant
{
    public sealed class ProductComparisonDto
    {
        public string Title { get; set; } = string.Empty;
        public List<int> ProductIds { get; set; } = [];
        public string Summary { get; set; } = string.Empty;
    }
}