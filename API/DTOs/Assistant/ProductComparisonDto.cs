namespace API.DTOs.Assistant
{
    public class ProductComparisonDto
    {
        public string Title { get; set; } = string.Empty;
        public List<AssistantProductDto> Products { get; set; } = [];
    }
}